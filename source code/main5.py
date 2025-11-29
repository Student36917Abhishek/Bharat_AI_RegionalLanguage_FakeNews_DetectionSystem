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

# Token limits - optimized for 8k context
MAX_TOKENS = 8192
SYSTEM_OVERHEAD = 100  # Reserve for system formatting
MAX_RESPONSE_TOKENS = 2000  # Give model plenty of space to reason
CLAIM_OVERHEAD = 100  # For claim text and formatting

# Calculate available tokens for articles
AVAILABLE_FOR_ARTICLES = MAX_TOKENS - SYSTEM_OVERHEAD - MAX_RESPONSE_TOKENS - CLAIM_OVERHEAD

# Simple and direct system prompt
SYSTEM_PROMPT = """You are a fact-checking assistant. Analyze the claim against the provided articles and determine if it's TRUE or FALSE.

Think through your reasoning step by step, then provide your final classification."""

def load_json_data(file_path):
    """Load JSON data from file."""
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
    """Count tokens in text using tiktoken."""
    try:
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(encoding.encode(text))
    except Exception as e:
        logging.error(f"Error counting tokens: {str(e)}")
        return len(text) // 4

def truncate_text_to_tokens(text, max_tokens):
    """Truncate text to fit within token limit."""
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
        max_chars = max_tokens * 4
        return text[:max_chars]

def extract_article_content(articles, max_tokens):
    """Extract article content within token limit."""
    if not articles:
        return "No articles available."
    
    content_parts = []
    remaining_tokens = max_tokens
    tokens_per_article = max_tokens // len(articles)  # Distribute evenly
    
    for i, article in enumerate(articles):
        if remaining_tokens <= 50:  # Keep some buffer
            break
        
        # Prioritize content, then summary, then title
        article_content = article.get('content', '')
        if not article_content:
            article_content = article.get('summary', article.get('description', ''))
        
        title = article.get('title', f'Article {i+1}')
        source = article.get('source', 'Unknown')
        
        # Format article
        article_text = f"\n--- Article {i+1} ---\nSource: {source}\nTitle: {title}\nContent: {article_content}\n"
        
        article_tokens = count_tokens(article_text)
        
        if article_tokens <= remaining_tokens:
            content_parts.append(article_text)
            remaining_tokens -= article_tokens
        else:
            # Truncate to fit
            truncated = truncate_text_to_tokens(article_text, remaining_tokens)
            content_parts.append(truncated)
            break
    
    return ''.join(content_parts)

def extract_classification(response_text):
    """Extract TRUE/FALSE classification from model response."""
    response_lower = response_text.lower()
    
    # Look for explicit TRUE/FALSE statements
    if 'false' in response_lower:
        if 'not false' in response_lower or "isn't false" in response_lower:
            return 'TRUE'
        return 'FALSE'
    elif 'true' in response_lower:
        if 'not true' in response_lower or "isn't true" in response_lower:
            return 'FALSE'
        return 'TRUE'
    
    # Look for conclusive statements
    if 'claim is correct' in response_lower or 'claim is accurate' in response_lower:
        return 'TRUE'
    elif 'claim is incorrect' in response_lower or 'claim is inaccurate' in response_lower or 'claim is wrong' in response_lower:
        return 'FALSE'
    
    # Look for evidence-based conclusions
    if 'no evidence' in response_lower or 'cannot be verified' in response_lower:
        return 'FALSE'
    
    return 'UNVERIFIABLE'

def classify_claim_with_llm(claim, explanation, articles, llm):
    """Classify claim using local LLM."""
    if not articles:
        return {
            "label": "UNVERIFIABLE",
            "llm_response": "No articles available for verification.",
            "reasoning": "Cannot verify without source articles."
        }
    
    # Extract article content
    article_content = extract_article_content(articles, AVAILABLE_FOR_ARTICLES)
    
    # Build user message
    user_message = f"""CLAIM TO VERIFY: {claim}

REFERENCE ARTICLES:
{article_content}

Analyze whether this claim is TRUE or FALSE based on the articles provided. Think through your reasoning carefully."""
    
    # Log token usage
    total_input_tokens = count_tokens(SYSTEM_PROMPT) + count_tokens(user_message)
    logging.info(f"Input tokens: {total_input_tokens} (Articles: {count_tokens(article_content)})")
    
    try:
        print(f"\n{'='*80}")
        print(f"CLAIM: {claim}")
        print(f"{'='*80}")
        print("LLM Response:\n")
        
        # Create chat completion with streaming
        response_stream = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            max_tokens=MAX_RESPONSE_TOKENS,
            temperature=0.3,  # Slightly creative but focused
            top_p=0.95,
            repeat_penalty=1.15,
            stream=True
        )
        
        # Collect full response
        full_response = ""
        for chunk in response_stream:
            if "choices" in chunk and len(chunk["choices"]) > 0:
                delta = chunk["choices"][0].get("delta", {})
                if "content" in delta:
                    content = delta["content"]
                    full_response += content
                    print(content, end="", flush=True)
        
        print("\n" + "="*80 + "\n")
        
        logging.info(f"Generated {len(full_response)} characters")
        
        # Extract classification
        classification = extract_classification(full_response)
        
        return {
            "label": classification,
            "llm_response": full_response,
            "reasoning": full_response  # Keep full reasoning
        }
        
    except Exception as e:
        logging.error(f"Error generating response: {str(e)}")
        return {
            "label": "ERROR",
            "llm_response": f"Error: {str(e)}",
            "reasoning": ""
        }

def process_claims_with_llm(data, model_path):
    """Process all claims using LLM."""
    logging.info(f"Loading model from {model_path}")
    
    try:
        llm = Llama(
            model_path=model_path,
            n_ctx=MAX_TOKENS,
            n_threads=8,
            verbose=False,
            n_batch=512,
            use_mlock=True,  # Lock model in memory
            use_mmap=True    # Memory map for efficiency
        )
        logging.info(f"Model loaded successfully")
    except Exception as e:
        logging.error(f"Error loading model: {str(e)}")
        return {}
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "model_used": model_path,
        "max_tokens": MAX_TOKENS,
        "max_response_tokens": MAX_RESPONSE_TOKENS,
        "classifications": []
    }
    
    claims = data.get("verified_claims", [])
    total_claims = len(claims)
    
    logging.info(f"Processing {total_claims} claims")
    logging.info(f"Token allocation - Max Context: {MAX_TOKENS}, Response: {MAX_RESPONSE_TOKENS}, Articles: ~{AVAILABLE_FOR_ARTICLES}")
    
    for i, claim_data in enumerate(claims, 1):
        logging.info(f"\n{'='*60}")
        logging.info(f"Processing claim {i}/{total_claims}")
        
        claim = claim_data.get("claim", "")
        explanation = claim_data.get("explanation", "")
        articles = claim_data.get("articles", [])
        
        if not claim:
            logging.warning(f"Skipping claim - no text")
            continue
        
        classification = classify_claim_with_llm(claim, explanation, articles, llm)
        
        result = {
            "claim": claim,
            "original_claim": claim_data.get("original_claim", ""),
            "search_query": claim_data.get("search_query", ""),
            "category": claim_data.get("category", ""),
            "classification": classification["label"],
            "reasoning": classification["reasoning"],
            "full_response": classification["llm_response"],
            "articles_count": len(articles),
            "articles_used": [
                {
                    "title": art.get("title", ""),
                    "source": art.get("source", ""),
                    "url": art.get("url", "")
                } for art in articles[:5]  # Keep first 5 for reference
            ]
        }
        
        results["classifications"].append(result)
        logging.info(f"Classification: {classification['label']}")
    
    return results

def save_results_to_file(results, filename):
    """Save results to JSON file."""
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logging.info(f"Results saved to {filename}")
        print(f"\n✓ Results saved to {filename}")
        return True
    except Exception as e:
        logging.error(f"Error saving results: {str(e)}")
        return False

def print_summary(results):
    """Print results summary."""
    print("\n" + "="*80)
    print("FACT-CHECK CLASSIFICATION SUMMARY")
    print("="*80)
    
    classifications = results.get("classifications", [])
    
    # Count results
    counts = {}
    for result in classifications:
        label = result['classification']
        counts[label] = counts.get(label, 0) + 1
    
    print(f"\nTotal Claims Processed: {len(classifications)}")
    print("\nClassification Breakdown:")
    for label, count in sorted(counts.items()):
        print(f"  {label}: {count}")
    
    print("\n" + "-"*80)
    print("Individual Results:")
    print("-"*80)
    
    for i, result in enumerate(classifications, 1):
        print(f"\n{i}. CLAIM: {result['claim'][:100]}{'...' if len(result['claim']) > 100 else ''}")
        print(f"   Classification: {result['classification']}")
        print(f"   Articles Used: {result['articles_count']}")
        if result.get('reasoning'):
            reasoning_preview = result['reasoning'][:200].replace('\n', ' ')
            print(f"   Reasoning: {reasoning_preview}{'...' if len(result['reasoning']) > 200 else ''}")
    
    print("\n" + "="*80)

def run_llm_classification_process(input_file_path, model_path, output_file_path):
    """
    Main function to run the LLM classification process.
    This function can be called from other scripts.
    """
    logging.info("Starting fact-checking classification")
    
    # Check if the output file already exists
    if os.path.exists(output_file_path):
        logging.info(f"Results file already exists at {output_file_path}. Skipping processing.")
        return output_file_path
    
    if not os.path.exists(input_file_path):
        logging.error(f"Results file not found: {input_file_path}")
        return None
    
    if not os.path.exists(model_path):
        logging.error(f"Model file not found: {model_path}")
        return None
    
    # Load data
    results_data = load_json_data(input_file_path)
    
    if not results_data:
        logging.error("No data to process")
        return None
    
    # Process claims
    classification_results = process_claims_with_llm(results_data, model_path)
    
    # Save results
    if save_results_to_file(classification_results, output_file_path):
        # Print summary
        print_summary(classification_results)
        logging.info("Fact-checking completed successfully")
        return output_file_path
    else:
        return None

# Main execution
if __name__ == "__main__":
    if not os.path.exists(RESULTS_FILE_PATH):
        logging.error(f"Results file not found: {RESULTS_FILE_PATH}")
        exit(1)
    
    if not os.path.exists(MODEL_PATH):
        logging.error(f"Model file not found: {MODEL_PATH}")
        exit(1)
    
    # Load data
    results_data = load_json_data(RESULTS_FILE_PATH)
    
    if not results_data:
        logging.error("No data to process")
        exit(1)
    
    # Process claims
    classification_results = process_claims_with_llm(results_data, MODEL_PATH)
    
    # Save results
    save_results_to_file(classification_results, OUTPUT_FILE_PATH)
    
    # Print summary
    print_summary(classification_results)
    
    logging.info("Fact-checking completed successfully")
