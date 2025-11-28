import streamlit as st
import sys
import os
import json
import time

# Import the necessary functions from your existing modules
# Ensure extract_data.py, translate_data.py, main3.py, and reddit.py are in the same directory
from extract_data import extract_json_data
from translate_data import translate_json_data
from main3 import generate_claims_json_from_translated
from reddit import RedditScraper, gemini_reduce_query

# --- System Description ---
PROJECT_NAME = "The Bharat: Regional Lang Fake News Detection System"
SYSTEM_DESCRIPTION = """
This system analyzes Reddit discussions on regional topics in India. It scrapes relevant posts, 
translates the local language content into English, and then uses AI to identify and extract 
potential claims or key narratives from the translated text.
"""

# --- Hardcoded File Paths ---
REDDIT_OUTPUT_PATH = "reddit_search_output.json"
EXTRACTED_PATH = "extracted_data.json"
TRANSLATED_PATH = "translated_data.json"

# --- Session State Initialization ---
# 'st.session_state' is used to store variables that persist across page reruns.
def initialize_session_state():
    if 'process_started' not in st.session_state:
        st.session_state.process_started = False
    if 'refined_query' not in st.session_state:
        st.session_state.refined_query = ""
    if 'scraping_done' not in st.session_state:
        st.session_state.scraping_done = False
    if 'translation_approved' not in st.session_state:
        st.session_state.translation_approved = False
    if 'final_claims' not in st.session_state:
        st.session_state.final_claims = None

# --- Main Application Logic ---
def main():
    initialize_session_state()

    # --- UI Header and Description ---
    st.set_page_config(page_title=PROJECT_NAME, layout="wide")
    st.title(PROJECT_NAME)
    st.markdown(SYSTEM_DESCRIPTION)
    st.markdown("---")

    # --- User Input Section ---
    st.header("1. Enter Search Topic")
    user_query = st.text_input(
        "Enter a topic to search on Reddit (e.g., 'Indian Defense', 'Karnataka Politics')",
        placeholder="Type your query here..."
    )

    if st.button("Start Analysis", type="primary", disabled=st.session_state.process_started):
        if not user_query.strip():
            st.error("Search query cannot be empty. Please enter a topic.")
            return
        
        st.session_state.process_started = True
        with st.spinner("Refining your query using AI..."):
            # Use Gemini API to reduce/refine the query
            st.session_state.refined_query = gemini_reduce_query(user_query)
        st.rerun()

    # --- Step 0: Confirm Refined Query and Scrape Data ---
    if st.session_state.process_started and not st.session_state.scraping_done:
        st.header("2. Confirm Search & Scrape Data")
        st.info(f"AI-generated search query: **\"{st.session_state.refined_query}\"**")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Yes, Scrape Reddit", key="scrape_yes"):
                with st.spinner(f"Searching Reddit for '{st.session_state.refined_query}' and extracting data..."):
                    try:
                        scraper = RedditScraper()
                        if scraper.reddit:
                            scraped_data = scraper.search_and_fetch(st.session_state.refined_query, limit=15)
                            if scraped_data:
                                with open(REDDIT_OUTPUT_PATH, "w") as f:
                                    json.dump(scraped_data, f, indent=4)
                                st.success(f"✅ Successfully scraped {len(scraped_data)} posts.")
                                
                                # Step 1: Extract data
                                with st.spinner("Extracting relevant content..."):
                                    extract_json_data(REDDIT_OUTPUT_PATH, EXTRACTED_PATH)
                                
                                if os.path.exists(EXTRACTED_PATH):
                                    st.success("✅ Data extraction complete.")
                                    st.session_state.scraping_done = True
                                    st.rerun()
                                else:
                                    st.error("❌ Data extraction failed.")
                            else:
                                st.error("❌ No data scraped from Reddit. The query might not have returned results.")
                        else:
                            st.error("❌ Failed to initialize Reddit scraper. Check credentials.")
                    except Exception as e:
                        st.error(f"An error occurred during scraping: {e}")
        
        with col2:
            if st.button("❌ Cancel", key="scrape_no"):
                st.session_state.process_started = False
                st.rerun()

    # --- Step 2: Ask for Permission to Translate ---
    if st.session_state.scraping_done and not st.session_state.translation_approved:
        st.header("3. Translate Extracted Data")
        st.info("The raw data has been extracted. The next step is to translate it to English for analysis.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🌐 Proceed with Translation", key="translate_yes"):
                st.session_state.translation_approved = True
                st.rerun()
        with col2:
            if st.button("⏭️ Skip Translation", key="translate_no"):
                st.warning("Translation skipped. Cannot proceed to claim generation without translated data.")
                st.session_state.process_started = False # Reset process
                st.rerun()

    # --- Step 3: Perform Translation and Generate Claims ---
    if st.session_state.translation_approved and not st.session_state.final_claims:
        st.header("4. Processing and Generating Claims")
        with st.spinner("Translating data... This may take a few minutes."):
            try:
                translate_json_data(EXTRACTED_PATH, TRANSLATED_PATH)
                if os.path.exists(TRANSLATED_PATH):
                    st.success("✅ Translation completed successfully.")
                else:
                    st.error("❌ Translation failed.")
                    return
            except Exception as e:
                st.error(f"An error occurred during translation: {e}")
                return

        with st.spinner("Generating claims from translated data..."):
            try:
                claims = generate_claims_json_from_translated(TRANSLATED_PATH)
                st.success("✅ Claims generation completed!")
                st.session_state.final_claims = claims
                st.rerun()
            except Exception as e:
                st.error(f"An error occurred during claim generation: {e}")

    # --- Step 4: Display Final Output ---
    if st.session_state.final_claims:
        st.header("5. Final Analysis: Detected Claims")
        st.markdown("Below are the potential claims and narratives identified by the AI from the translated Reddit discussions.")
        
        # Display the JSON in a clean, expandable format
        st.json(st.session_state.final_claims)
        
        st.markdown("---")
        if st.button("🔄 Start New Analysis"):
            # Reset all session state variables
            for key in st.session_state.keys():
                del st.session_state[key]
            initialize_session_state()
            st.rerun()

if __name__ == "__main__":
    main()
