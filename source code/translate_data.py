import json
import os
import re
import torch  # Add this import
from typing import List, Dict, Any, Optional, Tuple

# Import the language detector and translator classes
try:
    from lang_indicators import SmartLanguageDetector 
    from detect_lang import SimpleIndicTranslator
except ImportError as e:
    print(f"FATAL ERROR: Could not import required modules. Make sure 'lang_indicators.py' and 'detect_lang.py' are in the same directory.")
    print(f"Error details: {e}")
    exit(1)

def contains_non_english(text: str) -> bool:
    """Check if text contains non-English characters"""
    # Pattern to match non-ASCII characters (including Indic scripts)
    non_english_pattern = re.compile(r'[^\x00-\x7F]+')
    return bool(non_english_pattern.search(text))

def extract_non_english_sentences(text: str) -> List[str]:
    """Extract sentences that contain non-English words"""
    # Pattern to extract sentences containing non-English words
    sentence_pattern = re.compile(r'[^.!?]*[^\x00-\x7F]+[^.!?]*[.!?]', re.UNICODE)
    sentences = sentence_pattern.findall(text)
    
    # Also check for non-English content without sentence endings
    remaining_text = sentence_pattern.sub('', text)
    if contains_non_english(remaining_text):
        sentences.append(remaining_text.strip())
    
    return sentences

def translate_text(translator, text: str, fallback_lang: str = None) -> Tuple[str, str, Dict]:
    """Translate text and return translation, detected language, and detection info"""
    try:
        print(f"🔄 Translating text: {text[:50]}...")  # Log the text being translated
        
        # Check if text is too long and truncate if necessary
        max_length = 400  # Leave some room for special tokens
        if len(text) > max_length:
            text = text[:max_length]
            print(f"   Text truncated to {max_length} characters")
        
        # Detect language first
        src_lang = translator.detector.detect_language(text)
        detection_info = translator.detector.get_detection_method(text)
        
        print(f"   Detected language: {src_lang}")
        print(f"   Detection method: {detection_info.get('method', 'unknown')}")
        
        # Format input for IndicTrans2
        formatted_text = f"{src_lang} eng_Latn {text}"
        
        # Tokenize and translate
        inputs = translator.tokenizer(
            [formatted_text], 
            return_tensors="pt", 
            truncation=True, 
            max_length=512,
            padding=True
        )
        
        # Check if inputs are valid
        if not inputs or not inputs.get('input_ids') is not None:
            raise ValueError("Invalid tokenizer output")
            
        # Move inputs to the model's device
        inputs = {k: v.to(translator.model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = translator.model.generate(
                **inputs,
                max_length=512,
                num_beams=4,
                early_stopping=True,
                no_repeat_ngram_size=2
            )
        
        # Decode result
        translation = translator.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        print(f"✅ Translation successful: {translation[:100]}...")
        
        return translation, src_lang, detection_info
        
    except Exception as e:
        print(f"❌ Translation error: {e}")
        
        # If translation fails and we have a fallback language, try with that
        if fallback_lang:
            try:
                print(f"🔄 Trying fallback language: {fallback_lang}")
                
                # Format input with fallback language
                formatted_text = f"{fallback_lang} eng_Latn {text}"
                
                # Tokenize and translate
                inputs = translator.tokenizer(
                    [formatted_text], 
                    return_tensors="pt", 
                    truncation=True, 
                    max_length=512,
                    padding=True
                )
                
                # Check if inputs are valid
                if not inputs or not inputs.get('input_ids') is not None:
                    raise ValueError("Invalid tokenizer output in fallback")
                    
                # Move inputs to the model's device
                inputs = {k: v.to(translator.model.device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    outputs = translator.model.generate(
                        **inputs,
                        max_length=512,
                        num_beams=4,
                        early_stopping=True,
                        no_repeat_ngram_size=2
                    )
                
                # Decode result
                translation = translator.tokenizer.decode(outputs[0], skip_special_tokens=True)
                
                print(f"✅ Fallback translation successful: {translation[:100]}...")
                return translation, fallback_lang, {"method": "fallback", "confidence": "medium"}
            
            except Exception as fallback_error:
                print(f"❌ Fallback translation also failed: {fallback_error}")
        
        # If all translation attempts fail, return a basic translation or the original text
        return text, "unknown", {"method": "error", "error": str(e)}

def process_text(detector, translator, text: str) -> Dict[str, Any]:
    """Process a single text and return translation information"""
    print(f"\n📝 Processing text: {text[:100]}...")
    
    if not text or not text.strip():
        print("   Empty text, skipping")
        return {
            'original_text': text,
            'translated_text': text,
            'detected_language': 'en',
            'translation_method': 'empty',
            'non_english_sentences': [],
            'translation_details': {}
        }
    
    # Check if text contains non-English content
    if not contains_non_english(text):
        print("   No non-English content detected")
        return {
            'original_text': text,
            'translated_text': text,
            'detected_language': 'en',
            'translation_method': 'none_needed',
            'non_english_sentences': [],
            'translation_details': {}
        }
    
    print("   Non-English content detected")
    
    # Try to detect if the text is predominantly in one language
    overall_lang = detector.detect_language(text)
    print(f"   Overall detected language: {overall_lang}")
    
    # For mixed text, try to extract and translate non-English parts
    non_english_sentences = extract_non_english_sentences(text)
    print(f"   Extracted {len(non_english_sentences)} non-English sentences")
    
    if not non_english_sentences:
        # If no sentences extracted but contains non-English, translate the whole text
        print("   No sentences extracted, translating whole text")
        translation, detected_lang, detection_info = translate_text(translator, text)
        return {
            'original_text': text,
            'translated_text': translation,
            'detected_language': detected_lang,
            'translation_method': 'full_text',
            'non_english_sentences': [text],
            'translation_details': {
                'detection_method': detection_info.get('method', 'unknown'),
                'confidence': detection_info.get('confidence', 'low')
            }
        }
    
    # For each non-English sentence, try to translate it
    translated_sentences = []
    translation_details = {}
    
    for i, sentence in enumerate(non_english_sentences):
        if sentence.strip():
            print(f"   Translating sentence {i+1}/{len(non_english_sentences)}: {sentence[:50]}...")
            # Use Marathi as fallback for Devanagari text
            fallback_lang = "mar_Deva" if detector.is_devanagari_script(sentence) else None
            translation, detected_lang, detection_info = translate_text(translator, sentence.strip(), fallback_lang)
            translated_sentences.append(translation)
            translation_details[sentence] = {
                'translation': translation,
                'detected_lang': detected_lang,
                'detection_method': detection_info.get('method', 'unknown'),
                'confidence': detection_info.get('confidence', 'low')
            }
    
    # Replace non-English sentences with translations
    translated_text = text
    for i, original_sentence in enumerate(non_english_sentences):
        if i < len(translated_sentences):
            print(f"   Replacing sentence {i+1}: {original_sentence[:30]}... -> {translated_sentences[i][:30]}...")
            translated_text = translated_text.replace(original_sentence, translated_sentences[i], 1)
    
    return {
        'original_text': text,
        'translated_text': translated_text,
        'detected_language': overall_lang,
        'translation_method': 'sentence_level',
        'non_english_sentences': non_english_sentences,
        'translation_details': translation_details
    }

def translate_json_data(input_filepath: str, output_filepath: str) -> None:
    """
    Loads a JSON file with URL and original_text, performs language detection,
    translates non-English content, and saves the results to a new JSON file.
    """
    if not os.path.exists(input_filepath):
        print(f"Error: Input file not found at {input_filepath}")
        return

    print(f"Translating data from: {input_filepath}...")
    
    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from {input_filepath}")
        return
    except Exception as e:
        print(f"An unexpected error occurred while reading the file: {e}")
        return

    if not isinstance(data, list):
        print("Warning: Expected a list of records in the JSON file. Stopping processing.")
        return

    # Initialize the language detector and translator
    print("🔧 Initializing language detector and translator...")
    detector = SmartLanguageDetector()
    translator = SimpleIndicTranslator()
    
    translated_data = []
    
    for i, record in enumerate(data):
        if isinstance(record, dict):
            url = record.get('url')
            original_text = record.get('original_text')
            
            if not url or not original_text:
                continue
            
            print(f"\n{'='*50}")
            print(f"Processing record {i+1}/{len(data)}")
            print(f"URL: {url}")
            
            # Process the text to detect non-English content and translate it
            processed_text = process_text(detector, translator, original_text)
            
            # Create output record with translation information
            output_record = {
                'url': url,
                'original_text': processed_text['original_text'],
                'translated_text': processed_text['translated_text'],
                'detected_language': processed_text['detected_language'],
                'translation_method': processed_text['translation_method'],
                'non_english_sentences_count': len(processed_text['non_english_sentences']),
                'translation_details': processed_text['translation_details']
            }
            
            translated_data.append(output_record)
            
            print(f"✅ Record processed - Language: {processed_text['detected_language']}")
            print(f"   Method: {processed_text['translation_method']}")
            print(f"   Non-English sentences: {len(processed_text['non_english_sentences'])}")
            print(f"   Original text: {original_text[:100]}...")
            print(f"   Translated text: {processed_text['translated_text'][:100]}...")

    print(f"\n{'='*50}")
    print(f"Translated {len(translated_data)} records.")

    # Save the translated data to the output JSON file
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(translated_data, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved translated data to: {output_filepath}")
    except Exception as e:
        print(f"Error saving file: {e}")

if __name__ == "__main__":
    # For direct execution, use default paths
    INPUT_FILE = "./extracted_reddit_data.json"
    OUTPUT_FILE = "./translated_reddit_data.json"
    
    translate_json_data(INPUT_FILE, OUTPUT_FILE)
