"""
Simple Indian Language Translator
Uses smart hybrid language detection
"""

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from lang_indicators import SmartLanguageDetector

class SimpleIndicTranslator:
    def __init__(self):
        print("🚀 Initializing Simple Indic Translator...")
        
        # Initialize smart language detector
        self.detector = SmartLanguageDetector()
        
        # Initialize IndicTrans2 model
        print("📥 Loading IndicTrans2 model...")
        self.model_name = "ai4bharat/indictrans2-indic-en-1B"
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, 
            trust_remote_code=True
        )
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            self.model_name,
            trust_remote_code=True,
            torch_dtype=torch.float16,
            device_map="auto"
        )
        print("✅ IndicTrans2 model loaded successfully!")
    
    def translate(self, text, target_lang="eng_Latn"):
        """Simple translation with smart language detection"""
        if not text or not text.strip():
            return "No text provided", "unknown", {}
        
        # Detect source language using smart detector
        src_lang = self.detector.detect_language(text)
        detection_info = self.detector.get_detection_method(text)
        
        # Format input for IndicTrans2
        formatted_text = f"{src_lang} {target_lang} {text}"
        
        try:
            # Tokenize and translate
            inputs = self.tokenizer(
                [formatted_text], 
                return_tensors="pt", 
                truncation=True, 
                max_length=512,
                padding=True
            )
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=512,
                    num_beams=4,
                    early_stopping=True,
                    no_repeat_ngram_size=2
                )
            
            # Decode result
            translation = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            return translation, src_lang, detection_info
            
        except Exception as e:
            return f"Translation error: {str(e)}", src_lang, detection_info

def test_smart_detection():
    """Test the smart hybrid detection"""
    translator = SimpleIndicTranslator()
    
    print("\n" + "="*70)
    print("🧪 SMART HYBRID DETECTION TEST")
    print("="*70)
    
    test_cases = [
        # Devanagari languages (custom detection)
        ("Hindi", "नमस्ते, आप कैसे हैं? क्या आप खाना खा चुके हैं?"),
        ("Marathi", "नमस्कार, तुम्ही कसे आहात? तुमचे काम झाले का?"),
        ("Gujarati", "નમસ્તે, તમે કેમ છો? તમે ખોરાક ખાધો છે?"),
        
        # Non-Devanagari languages (langdetect)
        ("Bengali", "নমস্কার, আপনি কেমন আছেন? আপনি কি খাবার খেয়েছেন?"),
        ("Tamil", "வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்?"),
        ("Telugu", "నమస్కారం, మీరు ఎలా ఉన్నారు?"),
        ("Malayalam", "നമസ്കാരം, നിങ്ങൾ എങ്ങനെയിരിക്കുന്നു?"),
        ("Kannada", "ನಮಸ್ಕಾರ, ನೀವು ಹೇಗಿದ್ದೀರಿ?"),
        ("Punjabi", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ, ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?"),
        
        # English
        ("English", "Hello, how are you? Have you eaten?"),
    ]
    
    print(f"\n📊 Testing {len(test_cases)} samples with hybrid detection...\n")
    
    for title, text in test_cases:
        print(f"\n🔤 {title}:")
        print(f"   Input: {text}")
        
        translation, detected_lang, detection_info = translator.translate(text)
        
        print(f"   🔍 Method: {detection_info['method']}")
        print(f"   🌐 Detected: {detected_lang}")
        print(f"   📝 Translation: {translation}")
        print("   " + "-" * 50)

def main():
    """Main application"""
    translator = SimpleIndicTranslator()
    
    print("\n" + "="*70)
    print("🤖 SIMPLE INDIAN LANGUAGE TRANSLATOR")
    print("="*70)
    print("Smart Features:")
    print("  • langdetect for Bengali, Tamil, Telugu, etc.")
    print("  • Custom detection for Hindi/Marathi/Gujarati")
    print("  • Fast and accurate")
    
    # Interactive mode
    print("\n💬 INTERACTIVE MODE")
    print("Type any Indian language text to translate!")
    
    while True:
        user_input = input("\n📝 Enter text: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("🎯 Thank you for using the translator!")
            break
        elif user_input.lower() == 'test':
            test_smart_detection()
            continue
        elif not user_input:
            continue
        
        # Translate with smart detection
        translation, detected_lang, detection_info = translator.translate(user_input)
        
        print(f"🔍 Detection: {detection_info['method']}")
        print(f"🌐 Language: {detected_lang}")
        print(f"📝 Translation: {translation}")

if __name__ == "__main__":
    main()