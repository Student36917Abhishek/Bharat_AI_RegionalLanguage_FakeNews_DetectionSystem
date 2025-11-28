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

# GNews API key
API_KEY = "27e168eef0cf8765a7b0c552eacd30e3"

# Base URL for GNews API
BASE_URL = "https://gnews.io/api/v4/search"

# File path for JSON data
JSON_FILE_PATH = "/home/abhi/Pictures/custom_results/verified_claims.json"

# Global counter for API calls
api_call_count = 0
MAX_API_CALLS = 5

def load_json_data(file_path):
    """
    Load JSON data from the specified file path.
    
    Args:
        file_path (str): Path to the JSON file
        
    Returns:
        list: List of claims from the JSON file
    """
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
    """
    Generate a single alternative search query based on the original query.
    
    Args:
        original_query (str): The original search query
        
    Returns:
        str: Alternative search query
    """
    # Extract key terms from the original query
    key_terms = re.findall(r'\b\w+\b', original_query)
    
    # Try the first 3 terms
    if len(key_terms) >= 3:
        return ' '.join(key_terms[:3])
    elif len(key_terms) >= 2:
        return ' '.join(key_terms[:2])
    else:
        return original_query

def sanitize_search_query(query):
    """
    Sanitize search query to avoid API errors.
    
    Args:
        query (str): Original search query
        
    Returns:
        str: Sanitized search query
    """
    # Remove special characters that might cause API issues
    sanitized = re.sub(r'[^\w\s]', ' ', query)
    # Replace multiple spaces with a single space
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    # Limit length to avoid URL length issues
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
        logging.warning(f"Query truncated to 100 characters: {sanitized}")
    return sanitized

def fetch_news_articles(search_query, max_articles=10):
    """
    Fetch news articles from GNews API based on a search query.
    Try the original query and one alternative, then move on.
    
    Args:
        search_query (str): The query to search for
        max_articles (int): Maximum number of articles to retrieve
        
    Returns:
        list: List of articles or None if error occurred
    """
    global api_call_count
    
    # Check if we've reached the maximum number of API calls
    if api_call_count >= MAX_API_CALLS:
        logging.warning(f"Maximum number of API calls ({MAX_API_CALLS}) reached. Skipping further requests.")
        return None
    
    # Sanitize the search query
    sanitized_query = sanitize_search_query(search_query)
    
    params = {
        "q": sanitized_query,
        "token": API_KEY,
        "lang": "en",
        "max": max_articles
    }
    
    # Log the full URL for debugging
    url = f"{BASE_URL}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    logging.info(f"Making API request to: {url}")
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        api_call_count += 1
        logging.info(f"API call #{api_call_count}/{MAX_API_CALLS}")
        logging.info(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if "articles" in data and data["articles"]:
                logging.info(f"Found {len(data['articles'])} articles for query: {sanitized_query}")
                return data["articles"]
            else:
                logging.warning(f"No articles found for query: {sanitized_query}")
                
                # Try one alternative query if we still have API calls left
                if api_call_count < MAX_API_CALLS:
                    alt_query = generate_alternative_query(sanitized_query)
                    logging.info(f"Trying alternative query: {alt_query}")
                    
                    alt_params = params.copy()
                    alt_params["q"] = alt_query
                    alt_url = f"{BASE_URL}?{'&'.join([f'{k}={v}' for k, v in alt_params.items()])}"
                    
                    try:
                        alt_response = requests.get(BASE_URL, params=alt_params, timeout=10)
                        api_call_count += 1
                        logging.info(f"API call #{api_call_count}/{MAX_API_CALLS}")
                        
                        if alt_response.status_code == 200:
                            alt_data = alt_response.json()
                            if "articles" in alt_data and alt_data["articles"]:
                                logging.info(f"Found {len(alt_data['articles'])} articles for alternative query: {alt_query}")
                                return alt_data["articles"]
                            else:
                                logging.warning(f"No articles found for alternative query: {alt_query}")
                                return []
                        else:
                            logging.error(f"Alternative API request failed with status {alt_response.status_code}: {alt_response.text}")
                            return None
                    except requests.exceptions.RequestException as e:
                        logging.error(f"Error with alternative query '{alt_query}': {str(e)}")
                        return None
                
                return []
        else:
            logging.error(f"API request failed with status {response.status_code}: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching articles for query '{sanitized_query}': {str(e)}")
        return None

def is_domain_blocked(url):
    """
    Check if the domain is known to block requests.
    
    Args:
        url (str): URL to check
        
    Returns:
        bool: True if the domain is known to block requests
    """
    blocked_domains = ['ndtv.com']
    parsed_url = urlparse(url)
    return parsed_url.netloc in blocked_domains

def fetch_full_article_content(url):
    """
    Fetch the full content of an article from its URL using regex.
    
    Args:
        url (str): URL of the article
        
    Returns:
        str: Full article content or None if error occurred
    """
    try:
        # Skip known blocked domains
        if is_domain_blocked(url):
            logging.warning(f"Skipping known blocked domain: {url}")
            return None
            
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        logging.info(f"Fetching article content from: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        html = response.text
        
        # Remove script and style elements using regex
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        
        # Try different regex patterns to extract article content
        content = ""
        
        # Pattern 1: Extract content from common article tags
        patterns = [
            r'<article[^>]*>(.*?)</article>',
            r'<div[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*post[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*entry[^"]*"[^>]*>(.*?)</div>',
            r'<main[^>]*>(.*?)</main>',
            r'<div[^>]*id="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="[^"]*article[^"]*"[^>]*>(.*?)</div>',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1)
                break
        
        # If no content found with specific patterns, try to extract paragraphs
        if not content:
            # Extract all paragraphs
            paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, flags=re.DOTALL | re.IGNORECASE)
            if paragraphs:
                content = "\n".join(paragraphs)
        
        # If still no content, try to extract text from div tags
        if not content:
            # Extract text from div tags
            divs = re.findall(r'<div[^>]*>(.*?)</div>', html, flags=re.DOTALL | re.IGNORECASE)
            if divs:
                content = "\n".join(divs)
        
        # If still no content, extract all text from body
        if not content:
            body_match = re.search(r'<body[^>]*>(.*?)</body>', html, flags=re.DOTALL | re.IGNORECASE)
            if body_match:
                content = body_match.group(1)
        
        # Remove all remaining HTML tags
        content = re.sub(r'<[^>]+>', '', content)
        
        # Clean up the text
        content = re.sub(r'\s+', ' ', content).strip()
        
        # Try to extract meaningful content by looking for sentences
        sentences = re.split(r'[.!?]+', content)
        # Filter out very short sentences
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        content = '. '.join(sentences)
        
        if not content:
            logging.warning(f"Could not extract meaningful content from {url}")
        
        return content
    except Exception as e:
        logging.error(f"Error fetching article content from {url}: {str(e)}")
        return None

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

def process_claims(json_data):
    """
    Process claims that need external verification and fetch news articles.
    
    Args:
        json_data (dict): The JSON data containing claims
        
    Returns:
        dict: Results containing claim information and fetched articles
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "verified_claims": []
    }
    
    total_claims = len(json_data)
    processed_claims = 0
    successful_claims = 0
    
    logging.info(f"Processing {total_claims} claims with maximum {MAX_API_CALLS} API calls")
    
    for claim_data in json_data:
        # Check if we've reached the maximum number of API calls
        if api_call_count >= MAX_API_CALLS:
            logging.warning(f"Maximum number of API calls ({MAX_API_CALLS}) reached. Stopping further processing.")
            break
            
        processed_claims += 1
        logging.info(f"Processing claim {processed_claims}/{total_claims}")
        
        if claim_data.get("needs_external_verification", False):
            search_query = claim_data.get("search_query", "")
            if search_query:
                logging.info(f"Fetching articles for: {search_query}")
                articles = fetch_news_articles(search_query, max_articles=10)
                
                claim_result = {
                    "claim": claim_data.get("claim", ""),
                    "original_claim": claim_data.get("original_claim", ""),
                    "search_query": search_query,
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
                    "verification_result": "processed"
                }
                
                if articles:
                    successful_claims += 1
                    for article in articles:
                        logging.info(f"Fetching full content for: {article['title']}")
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
                        else:
                            logging.warning(f"Failed to fetch content for article: {article['title']}")
                        
                        claim_result["articles"].append(article_data)
                    
                    logging.info(f"Total tokens collected: {claim_result['total_tokens']}")
                    
                    # Determine verification result based on content
                    if claim_result["total_tokens"] > 0:
                        claim_result["verification_result"] = "content_found"
                    else:
                        claim_result["verification_result"] = "no_content_found"
                else:
                    logging.warning(f"No articles found for query: {search_query}")
                    claim_result["verification_result"] = "no_articles_found"
                
                results["verified_claims"].append(claim_result)
                
                # Add a delay to avoid rate limiting
                time.sleep(1)
    
    logging.info(f"Processed {processed_claims}/{total_claims} claims, {successful_claims} successful")
    return results

def save_results_to_file(results, filename="fact_check_results.json"):
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
        print(f"\nAll data has been saved to {filename}")
    except Exception as e:
        logging.error(f"Error saving results to file: {str(e)}")

def print_results(results):
    """
    Print the results to the terminal.
    
    Args:
        results (dict): The results to print
    """
    print("\n" + "="*80)
    print("FACT-CHECKING RESULTS")
    print("="*80)
    
    for i, claim_data in enumerate(results["verified_claims"], 1):
        print(f"\n{i}. Claim: {claim_data['claim']}")
        print(f"   Search Query: {claim_data['search_query']}")
        print(f"   Verification Status: {claim_data['verification_status']}")
        print(f"   Verification Result: {claim_data['verification_result']}")
        print(f"   Total Tokens: {claim_data.get('total_tokens', 0)}")
        
        if claim_data["articles"]:
            print(f"   Found {len(claim_data['articles'])} articles:")
            for j, article in enumerate(claim_data["articles"], 1):
                print(f"   {j}. Title: {article['title']}")
                print(f"      Source: {article['source']}")
                print(f"      Published: {article['publishedAt']}")
                print(f"      URL: {article['url']}")
                if article['content_tokens'] > 0:
                    print(f"      Content Tokens: {article['content_tokens']}")
                    print(f"      Content Preview: {article['content'][:200]}...")
                print()
        else:
            print("   No articles found or error occurred.")

# Main execution
if __name__ == "__main__":
    logging.info("Starting fact-checking script")
    
    # Check if the JSON file exists
    if not os.path.exists(JSON_FILE_PATH):
        logging.error(f"JSON file not found at {JSON_FILE_PATH}")
        exit(1)
    
    # Load JSON data from file
    json_data = load_json_data(JSON_FILE_PATH)
    
    if not json_data:
        logging.error("No data to process. Exiting.")
        exit(1)
    
    # Process the claims and fetch articles
    results = process_claims(json_data)
    
    # Save results to file
    save_results_to_file(results)
    
    # Print results to terminal
    print_results(results)
    
    logging.info(f"Fact-checking script completed. Used {api_call_count}/{MAX_API_CALLS} API calls.")
