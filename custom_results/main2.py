#API KEY:- "AIzaSyDIvqT4T9x6VnroM-omJBMqegY7cxW_QY4"
import sys
import os
from extract_data import extract_json_data
from translate_data import translate_json_data
from main3 import generate_claims_json_from_translated
import json

# Import the Reddit scraping functionality
from reddit import RedditScraper, gemini_reduce_query

def main():
    """
    Main function to coordinate the Reddit scraping, extraction and translation process.
    """
    # Hardcoded file paths
    reddit_output_path = "reddit_search_output.json"
    extracted_path = "extracted_data.json"
    output_path = "translated_data.json"
    
    print("=" * 60)
    print("REDDIT DATA PROCESSING PIPELINE")
    print("=" * 60)
    
    # Step 0: Scrape data from Reddit
    print("\n🔍 STEP 0: Scraping data from Reddit")
    raw_prompt = "Maratha Empire"
    
    if not raw_prompt:
        print("Search prompt cannot be empty. Using default query: 'Indian Defense'")
        raw_prompt = "Indian Defense"
    
    # Use Gemini API to reduce/refine the query
    final_query = raw_prompt
    print(f"Gemini-generated search query: \"{final_query}\"")
    
    feedback = None
    while True:
        approval = input("\nDo you want to search Reddit with this query? (yes/no/f): ").strip().lower()
        if approval in ['yes', 'y']:
            break
        elif approval == 'no':
            print("Search cancelled by user. Exiting.")
            return
        elif approval == 'f':
            feedback = input("Enter your feedback to improve the query: ")
            final_query = gemini_reduce_query(raw_prompt, feedback)
            print(f"Updated Gemini-generated query: \"{final_query}\"")
        else:
            print("Please enter 'yes', 'no', or 'f' for feedback.")
    
    scraper = RedditScraper()
    if scraper.reddit:
        print(f"Searching Reddit for: \"{final_query}\"...")
        scraped_data = scraper.search_and_fetch(final_query, limit=15)
        
        if scraped_data:
            try:
                with open(reddit_output_path, "w") as f:
                    json.dump(scraped_data, f, indent=4)
                print(f"Successfully saved {len(scraped_data)} posts to {reddit_output_path}")
                
                # Display titles of scraped posts
                print("\n--- Scraped Post Titles ---")
                for i, post_info in enumerate(scraped_data):
                    print(f"{i+1}. {post_info.get('title', 'N/A')}")
                print("---------------------------\n")
            except IOError as e:
                print(f"Error saving data to JSON file: {e}")
                return
        else:
            print("No data was scraped from Reddit. Exiting.")
            return
    else:
        print("Failed to initialize Reddit scraper. Exiting.")
        return
    
    # Step 1: Extract data from the original JSON
    print("\n📂 STEP 1: Extracting data from original JSON")
    print(f"Input: {reddit_output_path}")
    print(f"Output: {extracted_path}")
    extract_json_data(reddit_output_path, extracted_path)
    
    # Check if extraction was successful
    if not os.path.exists(extracted_path):
        print("\n❌ Extraction failed. Stopping process.")
        return
    
    # Step 2: Translate the extracted data
    print("\n🌐 STEP 2: Translating extracted data")
    print(f"Input: {extracted_path}")
    print(f"Output: {output_path}")
    translate_json_data(extracted_path, output_path)
    
    # Check if translation was successful
    if not os.path.exists(output_path):
        print("\n❌ Translation failed. Stopping process.")
        return
    
    print("\n✅ Process completed successfully!")
    print(f"Final output: {output_path}")

    # Step 3: Generate claims JSON from translated data
    print("\n📝 STEP 3: Generating claims JSON from translated data")
    claim = generate_claims_json_from_translated(output_path)
    print("\n✅ Claims JSON generation completed successfully!")
    print(f"Claims JSON: {claim}")

if __name__ == "__main__":
    main()
