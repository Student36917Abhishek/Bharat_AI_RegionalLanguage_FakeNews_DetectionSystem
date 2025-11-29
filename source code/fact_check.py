import json
import requests
import time
from datetime import datetime
import re
import tiktoken
import logging
import os
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fact_check.log"),
        logging.StreamHandler()
    ]
)

# News API configurations
GNEWS_API_KEY = "27e168eef0cf8765a7b0c552eacd30e3"
NEWSAPI_KEY = "36966074260a46599ef9d53e6c05c328"

GNEWS_BASE_URL = "https://gnews.io/api/v4"
NEWSAPI_BASE_URL = "https://newsapi.org/v2"

def load_json_data(file_path):
    """Load JSON data from the specified file path."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logging.info(f"Successfully loaded data from {file_path}")
        return data
    except FileNotFoundError:
        logging.error(f"Error: File not found at {file_path}")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Error: Invalid JSON format in {file_path}: {str(e)}")
        return []

def generate_alternative_query(original_query):
    """Generate a single alternative search query based on the original query."""
    key_terms = re.findall(r'\b\w+\b', original_query)
    if len(key_terms) >= 3:
        return ' '.join(key_terms[:3])
    elif len(key_terms) >= 2:
        return ' '.join(key_terms[:2])
    else:
        return original_query

def sanitize_search_query(query):
    """Sanitize search query to avoid API errors."""
    sanitized = re.sub(r'[^\w\s]', ' ', query)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
        logging.warning(f"Query truncated to 100 characters: {sanitized}")
    return sanitized

def make_api_call(url, params, api_name):
    """A generic function to make an API call and handle the response."""
    try:
        response = requests.get(url, params=params, timeout=10)
        logging.info(f"{api_name} API request for query: '{params.get('q', 'N/A')}'")
        logging.info(f"Response status code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            if "articles" in data and data["articles"]:
                logging.info(f"Found {len(data['articles'])} articles via {api_name}")
                return data["articles"]
            else:
                logging.warning(f"No articles found via {api_name} for query.")
                return []  # Return empty list for no results
        else:
            logging.error(f"{api_name} API request failed with status {response.status_code}: {response.text}")
            return None  # Indicate a hard failure (not just no results)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error with {api_name} API: {str(e)}")
        return None

def fetch_news_articles(search_query, current_api_calls, max_api_calls, max_articles=10):
    """
    Fetch news articles, managing API calls and respecting the call limit.
    Returns a tuple: (articles, new_api_calls_count)
    """
    sanitized_query = sanitize_search_query(search_query)
    
    # --- Try GNews ---
    if current_api_calls < max_api_calls:
        params = {"q": sanitized_query, "token": GNEWS_API_KEY, "lang": "en", "max": max_articles}
        articles = make_api_call(f"{GNEWS_BASE_URL}/search", params, "GNews")
        current_api_calls += 1
        if articles is not None: # Success (even if empty list)
            return articles, current_api_calls
    else:
        logging.warning("Max API calls reached. Skipping GNews.")

    # --- If GNews failed, try NewsAPI ---
    if current_api_calls < max_api_calls:
        logging.info("GNews API failed, trying NewsAPI as fallback")
        params = {"q": sanitized_query, "apiKey": NEWSAPI_KEY, "language": "en", "pageSize": max_articles}
        articles = make_api_call(f"{NEWSAPI_BASE_URL}/everything", params, "NewsAPI")
        current_api_calls += 1
        if articles is not None:
            # Convert NewsAPI format to match GNews format
            converted_articles = []
            for article in articles:
                converted_article = {
                    "title": article.get("title", ""),
                    "description": article.get("description", ""),
                    "url": article.get("url", ""),
                    "source": {"name": article.get("source", {}).get("name", "")},
                    "publishedAt": article.get("publishedAt", ""),
                    "content": article.get("content", "")
                }
                converted_articles.append(converted_article)
            return converted_articles, current_api_calls
    else:
        logging.warning("Max API calls reached. Skipping NewsAPI fallback.")

    # --- If both failed, try an alternative query ---
    alt_query = generate_alternative_query(search_query)
    if alt_query == sanitized_query:
        logging.warning("Alternative query is the same as the original. Skipping.")
        return [], current_api_calls

    logging.info(f"Trying alternative query: {alt_query}")
    
    # --- Try GNews with alternative query ---
    if current_api_calls < max_api_calls:
        params = {"q": alt_query, "token": GNEWS_API_KEY, "lang": "en", "max": max_articles}
        articles = make_api_call(f"{GNEWS_BASE_URL}/search", params, "GNews")
        current_api_calls += 1
        if articles is not None:
            return articles, current_api_calls
    else:
        logging.warning("Max API calls reached. Skipping GNews with alternative query.")

    # --- If GNews with alt query failed, try NewsAPI ---
    if current_api_calls < max_api_calls:
        logging.info("GNews with alternative query failed, trying NewsAPI as fallback")
        params = {"q": alt_query, "apiKey": NEWSAPI_KEY, "language": "en", "pageSize": max_articles}
        articles = make_api_call(f"{NEWSAPI_BASE_URL}/everything", params, "NewsAPI")
        current_api_calls += 1
        if articles is not None:
            converted_articles = []
            for article in articles:
                converted_article = {
                    "title": article.get("title", ""),
                    "description": article.get("description", ""),
                    "url": article.get("url", ""),
                    "source": {"name": article.get("source", {}).get("name", "")},
                    "publishedAt": article.get("publishedAt", ""),
                    "content": article.get("content", "")
                }
                converted_articles.append(converted_article)
            return converted_articles, current_api_calls
    else:
        logging.warning("Max API calls reached. Skipping NewsAPI with alternative query.")

    # If all attempts failed or were skipped
    return [], current_api_calls

def is_domain_blocked(url):
    """Check if the domain is known to block requests."""
    blocked_domains = ['ndtv.com']
    parsed_url = urlparse(url)
    return parsed_url.netloc in blocked_domains

def fetch_full_article_content(url):
    """Fetch the full content of an article from its URL using regex."""
    try:
        if is_domain_blocked(url):
            logging.warning(f"Skipping known blocked domain: {url}")
            return None
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html = response.text
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        
        content = ""
        patterns = [r'<article[^>]*>(.*?)</article>', r'<div[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</div>', r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>']
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1)
                break
        
        if not content:
            paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, flags=re.DOTALL | re.IGNORECASE)
            if paragraphs:
                content = "\n".join(paragraphs)
        
        content = re.sub(r'<[^>]+>', '', content)
        content = re.sub(r'\s+', ' ', content).strip()
        
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        content = '. '.join(sentences)
        
        return content if content else None
    except Exception as e:
        logging.error(f"Error fetching article content from {url}: {str(e)}")
        return None

def count_tokens(text):
    """Count number of tokens in a text string."""
    try:
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(encoding.encode(text))
    except Exception as e:
        logging.error(f"Error counting tokens: {str(e)}")
        return len(text) // 4


def process_claims(json_data, max_api_calls=10):
    """
    Process claims and fetch news articles, correctly managing API call limits.
    Skips external verification for claims with needs_external_verification=false.
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "verified_claims": []
    }
    
    total_claims = len(json_data)
    processed_claims = 0
    successful_claims = 0
    api_call_count = 0  # This will now be the definitive counter
    
    logging.info(f"Processing {total_claims} claims with a maximum of {max_api_calls} API calls.")
    
    for claim_data in json_data:
        processed_claims += 1
        logging.info(f"Processing claim {processed_claims}/{total_claims} (API calls made: {api_call_count}/{max_api_calls})")
        
        # Check if external verification is needed
        needs_external_verification = claim_data.get("needs_external_verification", True)
        
        # Create a base result object with common fields
        claim_result = {
            "claim": claim_data.get("claim", ""),
            "original_claim": claim_data.get("original_claim", ""),
            "search_query": claim_data.get("search_query", ""),
            "category": claim_data.get("category", ""),
            "verification_status": claim_data.get("verification_status", ""),
            "confidence": claim_data.get("confidence", ""),
            "explanation": claim_data.get("explanation", ""),
            "fact_check_notes": claim_data.get("fact_check_notes", ""),
            "potential_impact": claim_data.get("potential_impact", ""),
            "source_url": claim_data.get("source_url", ""),
            "post_number": claim_data.get("post_number", ""),
            "articles": [],
            "total_tokens": 0,
            "needs_external_verification": needs_external_verification
        }
        
        if not needs_external_verification:
            # Skip external verification, use existing data
            claim_result["verification_result"] = "verified_by_knowledge"
            claim_result["historical_evidence"] = claim_data.get("historical_evidence", "")
            logging.info(f"Skipping external verification for claim: {claim_result['claim']}")
        else:
            # The key check: stop before the next claim if the limit is reached
            if api_call_count >= max_api_calls:
                logging.warning(f"Maximum of {max_api_calls} API calls reached. Stopping further claim processing.")
                break
                
            search_query = claim_data.get("search_query", "")
            if not search_query:
                search_query = claim_data.get("claim", "")
            
            if search_query:
                # The function now returns articles and the updated call count
                articles, api_call_count = fetch_news_articles(
                    search_query, 
                    current_api_calls=api_call_count, 
                    max_api_calls=max_api_calls
                )
                
                if articles:
                    successful_claims += 1
                    for article in articles:
                        full_content = fetch_full_article_content(article['url'])
                        article_data = {
                            "title": article.get("title", ""),
                            "description": article.get("description", ""),
                            "url": article.get("url", ""),
                            "source": article.get("source", {}).get("name", ""),
                            "publishedAt": article.get("publishedAt", ""),
                            "content": full_content,
                            "content_tokens": count_tokens(full_content) if full_content else 0
                        }
                        if full_content:
                            claim_result["total_tokens"] += article_data["content_tokens"]
                        claim_result["articles"].append(article_data)
                    
                    claim_result["verification_result"] = "content_found" if claim_result["total_tokens"] > 0 else "no_content_found"
                else:
                    claim_result["verification_result"] = "no_articles_found"
        
        results["verified_claims"].append(claim_result)
        if needs_external_verification:
            time.sleep(1) # Be respectful to the APIs
    
    logging.info(f"Finished. Processed {processed_claims}/{total_claims} claims, {successful_claims} were successful. Total API calls made: {api_call_count}.")
    return results

def save_results_to_file(results, filename):
    """Save the results to a JSON file."""
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logging.info(f"Results saved to {filename}")
        print(f"\nAll data has been saved to {filename}")
        return True
    except Exception as e:
        logging.error(f"Error saving results to file: {str(e)}")
        return False

def print_results(results):
    """Print the results to the terminal."""
    print("\n" + "="*80)
    print("FACT-CHECKING RESULTS")
    print("="*80)
    
    for i, claim_data in enumerate(results["verified_claims"], 1):
        print(f"\n{i}. Claim: {claim_data['claim']}")
        print(f"   Search Query: {claim_data['search_query']}")
        print(f"   Verification Result: {claim_data['verification_result']}")
        
        # Display verification method
        if claim_data.get('needs_external_verification', True) == False:
            print(f"   Verification Method: Knowledge-based (no external verification)")
            if 'historical_evidence' in claim_data:
                print(f"   Historical Evidence: {claim_data['historical_evidence']}")
        else:
            print(f"   Verification Method: External news sources")
            print(f"   Total Tokens: {claim_data.get('total_tokens', 0)}")
        
        if claim_data["articles"]:
            print(f"   Found {len(claim_data['articles'])} articles:")
            for j, article in enumerate(claim_data["articles"], 1):
                source_name = article['source'].get('name', 'N/A') if isinstance(article['source'], dict) else article['source']
                print(f"   {j}. Title: {article['title']}")
                print(f"      Source: {source_name}")
                print(f"      URL: {article['url']}")
                if article.get('content_tokens', 0) > 0:
                    print(f"      Content Tokens: {article['content_tokens']}")
                print()
        else:
            print("   No articles found or error occurred.")

def run_fact_checking_process(json_file_path, results_filename="fact_check_results.json", max_api_calls=10):
    """
    Main function to run the fact-checking process.
    This function can be called from other scripts.
    """
    logging.info("Starting fact-checking script")
    
    # Check if the output file already exists
    if os.path.exists(results_filename):
        logging.info(f"Results file already exists at {results_filename}. Skipping processing.")
        return results_filename
    
    if not os.path.exists(json_file_path):
        logging.error(f"JSON file not found at {json_file_path}")
        return None
    
    json_data = load_json_data(json_file_path)
    if not json_data:
        logging.error("No data to process. Exiting.")
        return None
    
    # Call the updated process_claims function
    results = process_claims(json_data, max_api_calls)
    
    if save_results_to_file(results, results_filename):
        print_results(results)
        logging.info(f"Fact-checking script completed. Results saved to {results_filename}")
        return results_filename
    else:
        return None

# Main execution
if __name__ == "__main__":
    JSON_FILE_PATH = "/home/abhi/Pictures/custom_results/verified_claims.json"
    RESULTS_FILE_PATH = "/home/abhi/Pictures/custom_results/fact_check_results.json"
    run_fact_checking_process(JSON_FILE_PATH, RESULTS_FILE_PATH)
