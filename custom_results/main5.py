import json
import os
import logging
from datetime import datetime
import tiktoken
from llama_cpp import Llama

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fact_check_llm.log"),
        logging.StreamHandler()
    ]
)

# File paths
RESULTS_FILE_PATH = "/home/abhi/Pictures/custom_results/fact_check_results.json"
MODEL_PATH = "/home/abhi/Pictures/DeepSeek-R1-Distill-Qwen-1.5B.Q4_K_M.gguf"
OUTPUT_FILE_PATH = "/home/abhi/Pictures/custom_results/fact_check_classification_results.json"

# Token limits - adjusted for better allocation
MAX_TOKENS = 8192  # 8k token context window
PROMPT_TOKENS = 400  # Increased for better instructions
CLAIM_EXPLANATION_TOKENS = 200
RESPONSE_TOKENS = 1000  # Increased to 1000 tokens for better reasoning
ARTICLE_TOKENS = MAX_TOKENS - PROMPT_TOKENS - CLAIM_EXPLANATION_TOKENS - RESPONSE_TOKENS  # ~6592 tokens for articles

# More direct and explicit classification prompt
CLASSIFICATION_PROMPT = """
<|im_start|>system
You are a fact-checking AI. Your task is to classify claims as TRUE or FALSE based on provided articles.
You must respond in exactly this format:
LABEL: TRUE or FALSE
EXPLANATION: [Detailed explanation with reasoning]
<|im_end|>
<|im_start|>user
CLAIM: {claim}

ARTICLES:
{articles}

Classify this claim now. Provide a detailed explanation for your classification.
<|im_end|>
<|im_start|>assistant
LABEL:"""

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
    Count the number of tokens in a text string.
    
    Args:
        text (str): Text to count tokens for
        
    Returns:
        int: Number of tokens
    """
    try:
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(encoding.encode(text))
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
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        tokens = encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        else:
            truncated_tokens = tokens[:max_tokens]
            return encoding.decode(truncated_tokens)
    except Exception as e:
        logging.error(f"Error truncating text: {str(e)}")
        # Fallback: approximate character limit (1 token ≈ 4 characters)
        max_chars = max_tokens * 4
        return text[:max_chars]

def extract_article_content(articles, max_tokens):
    """
    Extract and concatenate article content within the token limit.
    
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
            
        # Extract the full article content, not just title and summary
        article_text = f"\n\nArticle {i+1}:\nTitle: {article.get('title', '')}\nSource: {article.get('source', '')}\nContent: {article.get('content', '')}"
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

def classify_claim_with_llm(claim, explanation, articles, llm):
    """
    Classify a claim using the local LLM with streaming enabled.
    
    Args:
        claim (str): The claim to classify
        explanation (str): Explanation of why the claim needs verification
        articles (list): List of article dictionaries
        llm: Loaded LLM model
        
    Returns:
        dict: Classification result with raw response
    """
    # Handle the case with no articles
    if not articles:
        return {
            "label": "unverifiable",
            "llm_response": "No articles available for comparison."
        }
    
    # Extract article content within the token limit
    article_content = extract_article_content(articles, ARTICLE_TOKENS)
    
    # Log the actual token counts for debugging
    prompt_tokens = count_tokens(CLASSIFICATION_PROMPT.format(claim=claim, articles=article_content))
    logging.info(f"Article content tokens: {count_tokens(article_content)}")
    logging.info(f"Total prompt tokens: {prompt_tokens}")
    
    # Format the prompt with the claim and articles
    formatted_prompt = CLASSIFICATION_PROMPT.format(
        claim=claim,
        articles=article_content
    )
    
    # Ensure the prompt fits within the token limit
    formatted_prompt = ensure_token_limit(formatted_prompt, MAX_TOKENS - RESPONSE_TOKENS)
    
    logging.info(f"Sending prompt to LLM (approx. {count_tokens(formatted_prompt)} tokens)")
    
    # Generate a response from the model with streaming
    try:
        print(f"\n{'='*80}")
        print(f"CLAIM: {claim}")
        print(f"{'='*80}")
        print("LLM Response: ", end="", flush=True)
        
        # Use create_chat_completion with streaming enabled
        response_stream = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": "You are a fact-checking AI. Your task is to classify claims as TRUE or FALSE based on provided articles. You must respond in exactly this format: LABEL: TRUE or FALSE\nEXPLANATION: [Detailed explanation with reasoning]"},
                {"role": "user", "content": f"CLAIM: {claim}\n\nARTICLES:\n{article_content}\n\nClassify this claim now. Provide a detailed explanation for your classification."}
            ],
            max_tokens=RESPONSE_TOKENS,  # Increased to 1000 tokens
            temperature=0.1,  # Slightly higher temperature for more nuanced responses
            top_p=0.9,  # More focused output
            repeat_penalty=1.1,  # Discourage repetition
            stop=["\n\n", "USER:", "ASSISTANT:", "<|im_end|>"],  # Stop tokens
            stream=True  # Enable streaming
        )
        
        # Collect the streamed response
        result_text = ""
        
        for chunk in response_stream:
            # Extract the content from the chunk
            if "choices" in chunk and len(chunk["choices"]) > 0 and "delta" in chunk["choices"][0]:
                delta = chunk["choices"][0]["delta"]
                if "content" in delta:
                    content = delta["content"]
                    result_text += content
                    print(content, end="", flush=True)
        
        print("\n" + "="*80)
        
        # Log the actual response for debugging
        logging.info(f"Model response length: {len(result_text)} characters")
        
    except Exception as e:
        logging.error(f"Error generating response from LLM: {str(e)}")
        print(f"\nError: {str(e)}")
        return {
            "label": "error",
            "llm_response": f"Error generating response: {str(e)}"
        }
    
    return {
        "label": "processed",  # Just indicate it was processed
        "llm_response": result_text
    }

def process_claims_with_llm(data):
    """
    Process all claims using the local LLM.
    
    Args:
        data (dict): Loaded JSON data containing claims
        
    Returns:
        dict: Results with classifications
    """
    # Initialize the LLM
    logging.info(f"Loading model from {MODEL_PATH}")
    try:
        llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=MAX_TOKENS,  # Set context size to 8k tokens
            n_threads=8,  # Use 8 CPU threads
            verbose=False,  # Disable verbose logging
            n_batch=512,  # Process more tokens at once
            f16_kv=True  # Use half-precision for key/value cache
        )
        logging.info(f"Model loaded successfully with {MAX_TOKENS} token context window")
    except Exception as e:
        logging.error(f"Error loading model: {str(e)}")
        return {}
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "model_used": MODEL_PATH,
        "max_tokens": MAX_TOKENS,
        "classifications": []
    }
    
    claims = data.get("verified_claims", [])
    total_claims = len(claims)
    
    logging.info(f"Processing {total_claims} claims with LLM using {MAX_TOKENS} token context window")
    logging.info(f"Token allocation: Prompt={PROMPT_TOKENS}, Response={RESPONSE_TOKENS}, Articles={ARTICLE_TOKENS}")
    
    for i, claim_data in enumerate(claims, 1):
        logging.info(f"Processing claim {i}/{total_claims}")
        
        claim = claim_data.get("claim", "")
        explanation = claim_data.get("explanation", "")
        articles = claim_data.get("articles", [])
        
        if not claim:
            logging.warning(f"Skipping claim due to missing claim text")
            continue
        
        classification = classify_claim_with_llm(claim, explanation, articles, llm)
        
        result = {
            "claim": claim,
            "original_claim": claim_data.get("original_claim", ""),
            "search_query": claim_data.get("search_query", ""),
            "category": claim_data.get("category", ""),
            "label": classification["label"],
            "llm_response": classification["llm_response"],
            "articles_used": len(articles),
            "total_tokens": claim_data.get("total_tokens", 0)
        }
        
        results["classifications"].append(result)
        logging.info(f"Processed claim with label '{classification['label']}'")
    
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
    Print the results to the terminal.
    
    Args:
        results (dict): The results to print
    """
    print("\n" + "="*80)
    print("FACT-CHECKING CLASSIFICATION RESULTS SUMMARY")
    print("="*80)
    
    classifications = results.get("classifications", [])
    
    for i, result in enumerate(classifications, 1):
        print(f"\n{i}. Claim: {result['claim']}")
        print(f"   Status: {result['label'].upper()}")
        print(f"   Articles Used: {result['articles_used']}")
        print(f"   Total Tokens: {result['total_tokens']}")

# Main execution
if __name__ == "__main__":
    logging.info("Starting fact-checking classification script")
    
    # Check if the results file exists
    if not os.path.exists(RESULTS_FILE_PATH):
        logging.error(f"Results file not found at {RESULTS_FILE_PATH}")
        exit(1)
    
    # Check if the model file exists
    if not os.path.exists(MODEL_PATH):
        logging.error(f"Model file not found at {MODEL_PATH}")
        exit(1)
    
    # Load the results data
    results_data = load_json_data(RESULTS_FILE_PATH)
    
    if not results_data:
        logging.error("No data to process. Exiting.")
        exit(1)
    
    # Process the claims with the LLM
    classification_results = process_claims_with_llm(results_data)
    
    # Save the results to a file
    save_results_to_file(classification_results, OUTPUT_FILE_PATH)
    
    # Print the results summary
    print_results(classification_results)
    
    logging.info("Fact-checking classification script completed")
