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
    claims_json_path = "/home/abhi/Pictures/custom_results/verified_claims.json"
    fact_check_results_path = "/home/abhi/Pictures/custom_results/fact_check_results.json"
    final_classification_path = "/home/abhi/Pictures/custom_results/fact_check_classification_results.json"
    model_path = "/home/abhi/Pictures/DeepSeek-R1-Distill-Qwen-1.5B.Q4_K_M.gguf"
    
    print("=" * 80)
    print("REDDIT DATA PROCESSING PIPELINE")
    print("=" * 80)
    
    # Step 0: Scrape data from Reddit
    print("\n🔍 STEP 0: Scraping data from Reddit")
    raw_prompt = "Indian Defense"
    
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
    
    # Check if claims file already exists
    if os.path.exists(claims_json_path):
        print(f"Claims file already exists at {claims_json_path}. Skipping API call and using existing file.")
    else:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(claims_json_path), exist_ok=True)
        
        # Generate claims
        claims = generate_claims_json_from_translated(output_path)
        
        if not claims:
            print("\n❌ Claims generation failed. Stopping process.")
            return
            
        # Save the claims to the expected file
        with open(claims_json_path, 'w') as f:
            json.dump(claims, f, indent=4)
        
        print(f"Claims saved to {claims_json_path}")
    
    # Step 4: Run fact_check.py to fetch news articles
    print("\n📰 STEP 4: Fetching news articles for fact-checking")
    
    # Import here to avoid circular imports
    from fact_check import run_fact_checking_process
    
    # Check if fact check results already exist
    if os.path.exists(fact_check_results_path):
        print(f"Fact check results already exist at {fact_check_results_path}. Skipping API call and using existing file.")
    else:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(fact_check_results_path), exist_ok=True)
        
        # Run fact checking
        fact_check_output = run_fact_checking_process(
            json_file_path=claims_json_path,
            results_filename=fact_check_results_path,
            max_api_calls=10
        )
        
        if not fact_check_output:
            print("\n❌ Fact-checking failed. Stopping process.")
            return
    
    # Step 5: Run main5.py to classify claims using LLM
    print("\n🧠 STEP 5: Classifying claims using LLM")
    
    # Import here to avoid circular imports
    from main5 import run_llm_classification_process
    
    # Check if classification results already exist
    if os.path.exists(final_classification_path):
        print(f"Classification results already exist at {final_classification_path}. Skipping LLM processing and using existing file.")
    else:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(final_classification_path), exist_ok=True)
        
        # Run classification
        classification_output = run_llm_classification_process(
            input_file_path=fact_check_results_path,
            model_path=model_path,
            output_file_path=final_classification_path
        )
        
        if not classification_output:
            print("\n❌ Classification failed. Stopping process.")
            return
    
    print("\n🎉 Entire pipeline completed successfully!")
    print(f"Final results available at: {final_classification_path}")

if __name__ == "__main__":
    main()
