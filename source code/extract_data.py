import json
import os
from typing import List, Dict, Any, Optional

def extract_content(data: Dict[str, Any]) -> Optional[Dict[str, str | None]]:
    """
    Analyzes a single data record, extracts the URL, and uses ONLY the 
    'selftext' as the 'original_text' for later processing.
    """
    url = data.get('url')
    # Use 'selftext' as the entire content body
    original_text = data.get('selftext')

    # Skip records without a URL or any selftext
    if not url or not original_text:
        return None

    return {
        'url': url,
        'original_text': original_text,
    }

def extract_json_data(input_filepath: str, output_filepath: str) -> None:
    """
    Loads a JSON file, extracts the URL and selftext data, 
    and saves the simplified results to a new JSON file.
    """
    if not os.path.exists(input_filepath):
        print(f"Error: Input file not found at {input_filepath}")
        return

    print(f"Extracting data from: {input_filepath}...")
    
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

    extracted_data = []
    
    for record in data:
        if isinstance(record, dict):
            # Extract content (URL and selftext only)
            extracted_item = extract_content(record)
            
            if extracted_item:
                extracted_data.append(extracted_item)

    print(f"Extracted {len(extracted_data)} records.")

    # Save the extracted data to the output JSON file
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(extracted_data, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved extracted data to: {output_filepath}")
    except Exception as e:
        print(f"Error saving file: {e}")

if __name__ == "__main__":
    # For direct execution, use default paths
    INPUT_FILE = "./reddit_data56498.json"
    OUTPUT_FILE = "./extracted_reddit_data.json"
    
    extract_json_data(INPUT_FILE, OUTPUT_FILE)