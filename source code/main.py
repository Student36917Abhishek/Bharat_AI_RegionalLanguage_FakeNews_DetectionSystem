import json
import os
import mysql.connector
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import re # Import the regex module

# Import the language detector class
# NOTE: Ensure lang_indicators.py is accessible and contains the required dependencies (langdetect)
try:
    from lang_indicators import SmartLanguageDetector 
    # Initialize the detector globally or in the main processing function
    # Placing it here for easy access, but it will be instantiated in process_json_file
except ImportError:
    print("FATAL ERROR: Could not import SmartLanguageDetector. Make sure 'lang_indicators.py' is in the same directory.")
    exit(1)


# --- MySQL Database Configuration ---
# IMPORTANT: You must ensure your MySQL server is running and the database 
# 'misinformation_db' (or the name you use) is created.
DB_CONFIG = {
    'user': 'agentic_user', # User provided in the prompt
    'password': '12345',    # Password provided in the prompt
    'host': 'localhost',    # Assuming localhost, change if your DB is elsewhere
    'database': 'misinformation_db' # Placeholder database name, please adjust if needed
}

def get_platform_from_url(url: str) -> str:
    """
    Extracts the platform name (e.g., 'Reddit', 'YouTube', 'Instagram') from a URL 
    using regular expressions for more robust matching.
    """
    if not url:
        return 'UNKNOWN'
        
    try:
        # Parse the URL to get the hostname (netloc)
        netloc = urlparse(url).netloc.lower()
        
        # Define a list of common platforms and their domains/subdomains using regex
        # The pattern looks for the primary domain, optionally preceded by a subdomain (www.)
        platform_patterns = {
            'Reddit': r'(?:www\.)?reddit\.com',
            'Twitter': r'(?:www\.)?(?:twitter\.com|x\.com)', # Handles both twitter.com and x.com
            'Facebook': r'(?:www\.)?facebook\.com',
            'YouTube': r'(?:www\.)?(?:youtube\.com|youtu\.be)', # Handles both youtube.com and youtu.be
            'Instagram': r'(?:www\.)?instagram\.com',
            'TikTok': r'(?:www\.)?tiktok\.com',
            'Telegram': r'(?:t\.me|telegram\.org)',
            'WhatsApp': r'(?:wa\.me)',
            # Add other platforms here as needed
        }
        
        for platform, pattern in platform_patterns.items():
            if re.search(pattern, netloc):
                return platform
        
        return 'OTHER'
    except Exception:
        return 'INVALID_URL'

def extract_content(data: Dict[str, Any]) -> Optional[Dict[str, str | None]]:
    """
    Analyzes a single data record, extracts the URL, and uses ONLY the 
    'selftext' as the 'original_text' for insertion and language detection.
    """
    url = data.get('url')
    # Use 'selftext' as the entire content body as requested
    original_text = data.get('selftext')

    # Skip records without a URL or any selftext
    if not url or not original_text:
        return None

    return {
        'url': url,
        'original_text': original_text,
    }

def insert_to_database(cleaned_data: List[Dict[str, str | None]]) -> None:
    """
    Inserts the cleaned data (including platform detected from URL and detected language) 
    into the MySQL 'posts' table.
    """
    print("Attempting to connect to the database...")
    try:
        # Using connect(**DB_CONFIG) to handle connection details dynamically
        cnx = mysql.connector.connect(**DB_CONFIG)
        cursor = cnx.cursor()
    except mysql.connector.Error as err:
        print(f"Database Connection Error: {err}")
        print("Please ensure your MySQL server is running and the database is configured in DB_CONFIG.")
        return

    # SQL statement to insert data. 'INSERT IGNORE' skips rows that violate unique constraints.
    sql = """
    INSERT IGNORE INTO `posts` 
    (`post_url`, `original_text`, `platform`, `detected_lang`)
    VALUES (%s, %s, %s, %s)
    """

    insert_count = 0
    
    for item in cleaned_data:
        url = item.get('url')
        original_text = item.get('original_text') 
        detected_lang = item.get('detected_lang', 'en') # Default to 'en' if detection fails
        
        # Dynamically determine the platform
        platform = get_platform_from_url(url) 

        # Final check for minimal data before insertion attempt
        if not url or not original_text:
            continue
        
        # Data for insertion
        data_to_insert = (
            url,
            original_text,
            platform, # Dynamically determined
            detected_lang
        )

        try:
            cursor.execute(sql, data_to_insert)
            insert_count += 1
        except mysql.connector.Error as err:
            # Silently ignore duplicate entry error (Error 1062) handled by 'INSERT IGNORE'
            if err.errno != 1062:
                 print(f"Database Insert Error: {err} for URL: {url}")
                 
    cnx.commit()
    cursor.close()
    cnx.close()
    print(f"Database processing complete. Attempted to insert {insert_count} records.")


def process_json_file(input_filepath: str, output_filepath: str) -> None:
    """
    Loads a JSON file, processes the data, performs language detection, 
    saves the cleaned results to a JSON file, and inserts the data into the MySQL database.
    """
    if not os.path.exists(input_filepath):
        print(f"Error: Input file not found at {input_filepath}")
        return

    print(f"Processing file: {input_filepath}...")
    
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

    # Initialize the language detector
    detector = SmartLanguageDetector() 
    
    cleaned_data: List[Dict[str, str | None]] = []
    
    for record in data:
        if isinstance(record, dict):
            # Extract content (now only selftext)
            extracted_item = extract_content(record)
            
            if extracted_item:
                original_text = extracted_item.get('original_text', '')
                
                # --- Language Detection ---
                # Detect the language of the selftext
                detected_lang = detector.detect_language(original_text)
                
                # Add the detected language to the extracted item
                extracted_item['detected_lang'] = detected_lang
                
                cleaned_data.append(extracted_item)


    print(f"Extracted {len(cleaned_data)} records for JSON and DB processing.")

    # --- 1. Save the cleaned data to the output JSON file ---
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved cleaned JSON data to: {output_filepath}")
    except Exception as e:
        print(f"Error saving file: {e}")

    # --- 2. Insert the cleaned data into the database ---
    insert_to_database(cleaned_data)


# --- Configuration and Execution ---
if __name__ == "__main__":
    
    INPUT_FILE_REDDIT = "/home/anand/Bharat_fake_new/reddit_data56498.json"
    OUTPUT_FILE_REDDIT = "cleaned_reddit_data.json"
    
    # NOTE: Since the platform is now dynamically detected, this file will still work, 
    # but the platform will be correctly tagged based on the URLs inside.
    process_json_file(INPUT_FILE_REDDIT, OUTPUT_FILE_REDDIT)
    
    print("\nScript finished.")