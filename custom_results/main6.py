import json
import os
import logging
from datetime import datetime
import tiktoken
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fact_check_gemini.log"),
        logging.StreamHandler()
    ]
)

# File paths
RESULTS_FILE_PATH = "/home/abhi/Pictures/custom_results/fact_check_results.json"
OUTPUT_FILE_PATH = "/home/abhi/Pictures/custom_results/fact_check_classification_results.json"

# API Configuration
GEMINI_API_KEY = "AIzaSyBB0vIV00XW0ybBri2vj4xHm4N5XznwyGg"
MODEL_NAME = "gemini-2.5-flash"  # Using Gemini 2.5 Flash

# Token limits - Optimized for maximum article content
MAX_TOKENS = 8192  # 8k token context window
PROMPT_TOKENS = 300
CLAIM_EXPLANATION_TOKENS = 200
RESPONSE_TOKENS = 1000  # Increased to 1k tokens
ARTICLE_TOKENS = MAX_TOKENS - PROMPT_TOKENS - CLAIM_EXPLANATION_TOKENS - RESPONSE_TOKENS  # ~6692 tokens

# More explicit and structured classification prompt
CLASSIFICATION_PROMPT = """
IMPORTANT: You are a fact-checking AI assistant. Your task is to analyze a claim and determine if it is TRUE or FALSE.

CRITICAL INSTRUCTIONS:
1. First verify if the articles themselves are reliable sources
2. Check if the articles contain factual information or misinformation
3. Only use the articles as evidence if they appear to be from reliable sources
4. If the articles seem to contain misinformation or are from unreliable sources, classify the claim as "UNVERIFIABLE"

CLAIM TO VERIFY: {claim}

ARTICLES FOR REFERENCE:
{articles}

INSTRUCTIONS:
1. Read the claim carefully
2. Review the articles for evidence and reliability
3. Decide if the claim is supported (TRUE), contradicted (FALSE), or if the articles are unreliable (UNVERIFIABLE)
4. Provide your answer in this EXACT format:
   LABEL: [TRUE, FALSE, or UNVERIFIABLE]
   EXPLANATION: [2-3 sentences explaining your decision]

YOUR RESPONSE (must follow the exact format above):
"""

def initialize_gemini():
    """
    Initialize the Gemini API with the specified model.
    
    Returns:
        genai.GenerativeModel: Initialized Gemini model
    """
    try:
        # Configure the API key
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Create the model with safety settings
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        
        logging.info(f"Successfully initialized Gemini model: {MODEL_NAME}")
        return model
    except Exception as e:
        logging.error(f"Error initializing Gemini model: {str(e)}")
        return None

def load_json_data(file_path):
    """
    Load JSON data from the specified file path.
    
    Args:
        file_path (str): Path to the JSON file
        
    Returns:
        dict: Loaded JSON data
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logging.info(f"Successfully loaded data from {file_path}")
        return data
    except FileNotFoundError:
        logging.error(f"Error: File not found at {file_path}")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Error: Invalid JSON format in {file_path}: {str(e)}")
        return {}

def count_tokens(text):
    """
    Count the number of tokens in a text string using a more accurate method.
    
    Args:
        text (str): Text to count tokens for
        
    Returns:
        int: Number of tokens
    """
    try:
        # For Gemini, we'll use a more accurate approximation
        # Gemini uses a similar tokenizer to GPT-3.5/4, so we'll use that as a reference
        # This is still an approximation but should be more accurate
        # Rough estimate: 1 token ≈ 4 characters for English text
        return len(text) // 4
    except Exception as e:
        logging.error(f"Error counting tokens: {str(e)}")
        # Fallback: approximate token count (1 token ≈ 4 characters)
        return len(text) // 4

def truncate_text_to_tokens(text, max_tokens):
    """
    Truncate text to fit within the specified token limit.
    
    Args:
        text (str): Text to truncate
        max_tokens (int): Maximum number of tokens
        
    Returns:
        str: Truncated text
    """
    try:
        # More accurate character-based truncation
        max_chars = max_tokens * 4  # Approximate 4 characters per token
        if len(text) <= max_chars:
            return text
        else:
            return text[:max_chars]
    except Exception as e:
        logging.error(f"Error truncating text: {str(e)}")
        # Fallback: approximate character limit (1 token ≈ 4 characters)
        max_chars = max_tokens * 4
        return text[:max_chars]

def extract_article_content(articles, max_tokens):
    """
    Extract and concatenate article content within the token limit.
    Modified to include more content from each article and source reliability information.
    
    Args:
        articles (list): List of article dictionaries
        max_tokens (int): Maximum number of tokens for all articles combined
        
    Returns:
        str: Concatenated article content
    """
    if not articles:
        return "No articles available for comparison."
    
    content = ""
    remaining_tokens = max_tokens
    
    for i, article in enumerate(articles):
        if remaining_tokens <= 0:
            break
            
        # Extract more content from each article, including source reliability
        article_parts = [
            f"\n\nArticle {i+1}:",
            f"Title: {article.get('title', '')}",
            f"Source: {article.get('source', '')}",
            f"Published Date: {article.get('published_date', '')}",
            f"URL: {article.get('url', '')}",
            f"Summary: {article.get('description', '')}",
        ]
        
        # Add the full content if available
        if 'content' in article and article['content']:
            article_parts.append(f"Content: {article['content']}")
        elif 'body' in article and article['body']:
            article_parts.append(f"Content: {article['body']}")
        
        article_text = "\n".join(article_parts)
        article_tokens = count_tokens(article_text)
        
        if article_tokens <= remaining_tokens:
            content += article_text
            remaining_tokens -= article_tokens
        else:
            # Truncate this article to fit the remaining tokens
            truncated_content = truncate_text_to_tokens(article_text, remaining_tokens)
            content += truncated_content
            remaining_tokens = 0
    
    return content

def ensure_token_limit(prompt, max_tokens):
    """
    Ensure the prompt fits within the token limit.
    
    Args:
        prompt (str): The prompt to check
        max_tokens (int): Maximum number of tokens
        
    Returns:
        str: Prompt that fits within the token limit
    """
    tokens = count_tokens(prompt)
    
    if tokens <= max_tokens:
        return prompt
    
    # If the prompt is too long, truncate it
    logging.warning(f"Prompt exceeds token limit ({tokens} > {max_tokens}). Truncating...")
    return truncate_text_to_tokens(prompt, max_tokens)

def classify_claim_with_gemini(claim, explanation, articles, model):
    """
    Classify a claim using the Gemini API.
    Modified to provide better error handling and safety filter detection.
    
    Args:
        claim (str): The claim to classify
        explanation (str): Explanation of why the claim needs verification
        articles (list): List of article dictionaries
        model: Initialized Gemini model
        
    Returns:
        dict: Classification result with label and explanation
    """
    # Handle the case with no articles
    if not articles:
        return {
            "label": "unverifiable",
            "explanation": "No articles available to verify this claim.",
            "full_response": "No articles available for comparison."
        }
    
    # Extract article content within the token limit
    article_content = extract_article_content(articles, ARTICLE_TOKENS)
    article_tokens = count_tokens(article_content)
    
    # Format the prompt with the claim and articles
    formatted_prompt = CLASSIFICATION_PROMPT.format(
        claim=claim,
        articles=article_content
    )
    
    # Ensure the prompt fits within the token limit
    formatted_prompt = ensure_token_limit(formatted_prompt, MAX_TOKENS - RESPONSE_TOKENS)
    total_tokens = count_tokens(formatted_prompt)
    
    logging.info(f"Sending prompt to Gemini:")
    logging.info(f"  - Article content: ~{article_tokens} tokens")
    logging.info(f"  - Total prompt: ~{total_tokens} tokens (limit: {MAX_TOKENS - RESPONSE_TOKENS})")
    
    # Generate a response from the model
    try:
        print("Processing claim... ", end="", flush=True)
        
        # First try without streaming to see if it works
        response = model.generate_content(
            formatted_prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=RESPONSE_TOKENS,
                temperature=0.1,
                top_p=0.9,
            )
        )
        
        # Check if the response was blocked
        if response.candidates and response.candidates[0].finish_reason:
            finish_reason = response.candidates[0].finish_reason
            logging.warning(f"Response finished with reason: {finish_reason}")
            
            # Handle safety filter block
            if finish_reason == 2:  # SAFETY
                logging.warning("Response was blocked due to safety concerns")
                return {
                    "label": "error",
                    "explanation": "Response was blocked due to safety concerns. This may be due to sensitive content in the claim or articles.",
                    "full_response": "Response blocked by safety filters."
                }
        
        # Try to get the text
        try:
            result_text = response.text
        except ValueError as e:
            logging.error(f"Error accessing response text: {str(e)}")
            return {
                "label": "error",
                "explanation": f"Error accessing response text: {str(e)}",
                "full_response": ""
            }
        
        print(" Done!")
        
    except Exception as e:
        logging.error(f"Error generating response from Gemini: {str(e)}")
        
        # Try with streaming as a fallback
        try:
            logging.info("Attempting to use streaming as fallback...")
            response = model.generate_content(
                formatted_prompt,
                stream=True,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=RESPONSE_TOKENS,
                    temperature=0.1,
                    top_p=0.9,
                )
            )
            
            # Collect the streamed response
            result_text = ""
            for chunk in response:
                if chunk.text:
                    result_text += chunk.text
                    # Optional: Print a dot to show progress
                    print(".", end="", flush=True)
            
            print(" Done with streaming!")
        except Exception as e2:
            logging.error(f"Error with streaming as well: {str(e2)}")
            return {
                "label": "error",
                "explanation": f"Error generating response: {str(e)}; Streaming error: {str(e2)}",
                "full_response": ""
            }
    
    # Try to extract the label and explanation from the response
    label = "unknown"
    explanation = ""
    
    # Try to extract the label
    if "LABEL: TRUE" in result_text.upper():
        label = "true"
    elif "LABEL: FALSE" in result_text.upper():
        label = "false"
    elif "LABEL: UNVERIFIABLE" in result_text.upper():
        label = "unverifiable"
    
    # Try to extract the explanation
    if "EXPLANATION:" in result_text.upper():
        explanation_start = result_text.upper().find("EXPLANATION:") + len("EXPLANATION:")
        explanation_end = result_text.find("\n\n", explanation_start)
        if explanation_end == -1:
            explanation_end = len(result_text)
        explanation = result_text[explanation_start:explanation_end].strip()
    
    return {
        "label": label,
        "explanation": explanation,
        "full_response": result_text,
        "tokens_used": {
            "articles": article_tokens,
            "total": total_tokens
        }
    }

def process_claims_with_gemini(data):
    """
    Process all claims using the Gemini API.
    
    Args:
        data (dict): Loaded JSON data containing claims
        
    Returns:
        dict: Results with classifications
    """
    # Initialize the Gemini model
    model = initialize_gemini()
    if not model:
        logging.error("Failed to initialize Gemini model. Exiting.")
        return {}
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "model_used": MODEL_NAME,
        "max_tokens": MAX_TOKENS,
        "classifications": []
    }
    
    claims = data.get("verified_claims", [])
    total_claims = len(claims)
    
    logging.info(f"Processing {total_claims} claims with Gemini using {MAX_TOKENS} token context window")
    
    for i, claim_data in enumerate(claims, 1):
        logging.info(f"Processing claim {i}/{total_claims}")
        
        claim = claim_data.get("claim", "")
        explanation = claim_data.get("explanation", "")
        articles = claim_data.get("articles", [])
        
        if not claim:
            logging.warning(f"Skipping claim due to missing claim text")
            continue
        
        classification = classify_claim_with_gemini(claim, explanation, articles, model)
        
        result = {
            "claim": claim,
            "original_claim": claim_data.get("original_claim", ""),
            "search_query": claim_data.get("search_query", ""),
            "category": claim_data.get("category", ""),
            "label": classification["label"],
            "explanation": classification["explanation"],
            "llm_response": classification["full_response"],
            "articles_used": len(articles),
            "total_tokens": claim_data.get("total_tokens", 0),
            "tokens_used": classification.get("tokens_used", {})
        }
        
        results["classifications"].append(result)
        logging.info(f"Classified claim as '{classification['label']}'")
    
    return results

def save_results_to_file(results, filename):
    """
    Save the results to a JSON file.
    
    Args:
        results (dict): The results to save
        filename (str): The filename to save to
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logging.info(f"Results saved to {filename}")
        print(f"\nClassification results have been saved to {filename}")
    except Exception as e:
        logging.error(f"Error saving results to file: {str(e)}")

def print_results(results):
    """
    Print the results to the terminal with additional analysis.
    
    Args:
        results (dict): The results to print
    """
    print("\n" + "="*80)
    print("FACT-CHECKING CLASSIFICATION RESULTS")
    print("="*80)
    
    classifications = results.get("classifications", [])
    
    # Count the different labels
    label_counts = {"true": 0, "false": 0, "unverifiable": 0, "error": 0, "unknown": 0}
    
    for i, result in enumerate(classifications, 1):
        label = result.get("label", "unknown")
        label_counts[label] = label_counts.get(label, 0) + 1
        
        print(f"\n{i}. Claim: {result['claim']}")
        print(f"   Label: {label.upper()}")
        print(f"   Explanation: {result['explanation']}")
        print(f"   Articles Used: {result['articles_used']}")
        
        # Print token usage
        tokens_used = result.get('tokens_used', {})
        if tokens_used:
            print(f"   Tokens Used: ~{tokens_used.get('articles', 'N/A')} for articles, ~{tokens_used.get('total', 'N/A')} total")
        
        print(f"   Total Tokens: {result['total_tokens']}")
        
        # Print the LLM response for debugging
        print("\n   Gemini Response (first 500 characters):")
        print("   " + "-"*78)
        response_preview = result.get('llm_response', '')[:500]
        print(f"   {response_preview}")
        print("   " + "-"*78)
    
    # Print summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print(f"Total Claims Processed: {len(classifications)}")
    print(f"True: {label_counts['true']}")
    print(f"False: {label_counts['false']}")
    print(f"Unverifiable: {label_counts['unverifiable']}")
    print(f"Error: {label_counts['error']}")
    print(f"Unknown: {label_counts['unknown']}")
    
    # Calculate average token usage
    total_article_tokens = 0
    total_prompt_tokens = 0
    claims_with_tokens = 0
    
    for result in classifications:
        tokens_used = result.get('tokens_used', {})
        if tokens_used:
            total_article_tokens += tokens_used.get('articles', 0)
            total_prompt_tokens += tokens_used.get('total', 0)
            claims_with_tokens += 1
    
    if claims_with_tokens > 0:
        print(f"\nAverage Article Tokens: {total_article_tokens / claims_with_tokens:.0f}")
        print(f"Average Total Prompt Tokens: {total_prompt_tokens / claims_with_tokens:.0f}")

# Main execution
if __name__ == "__main__":
    logging.info("Starting fact-checking classification script with Gemini API")
    
    # Check if the results file exists
    if not os.path.exists(RESULTS_FILE_PATH):
        logging.error(f"Results file not found at {RESULTS_FILE_PATH}")
        exit(1)
    
    # Check if the API key is set
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        logging.error("Please set your Gemini API key in the GEMINI_API_KEY variable")
        exit(1)
    
    # Load the results data
    results_data = load_json_data(RESULTS_FILE_PATH)
    
    if not results_data:
        logging.error("No data to process. Exiting.")
        exit(1)
    
    # Process the claims with Gemini
    classification_results = process_claims_with_gemini(results_data)
    
    # Save the results to a file
    save_results_to_file(classification_results, OUTPUT_FILE_PATH)
    
    # Print the results to the terminal with additional analysis
    print_results(classification_results)
    
    logging.info("Fact-checking classification script with Gemini completed")
