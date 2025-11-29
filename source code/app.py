import streamlit as st
import sys
import os
import json
import time

# Import the necessary functions from your existing modules
from extract_data import extract_json_data
from translate_data import translate_json_data
from main3 import generate_claims_json_from_translated
from reddit import RedditScraper, gemini_reduce_query

# --- System Description ---
PROJECT_NAME = "🔍 The Bharat: Regional Language Fake News Detection System"
SYSTEM_DESCRIPTION = """
🌐 This system analyzes Reddit discussions on regional topics in India. It scrapes relevant posts, translates the local language content into English, and then uses AI to identify and extract potential claims or key narratives from the translated text. It then performs fact-checking and classifies the claims using advanced AI models.
"""

# --- Project Objective ---
PROJECT_OBJECTIVE = """
### 🎯 Our Mission: Fighting Misinformation in Regional Languages

Project Bharat is your intelligent, multilingual fact-checking assistant designed specifically for India's diverse linguistic landscape. 

#### The Problem We're Solving:
In today's digital age, misinformation spreads rapidly through social media, messaging platforms, and local news sites. When this content is in regional languages, it becomes even more challenging to verify, leading to confusion and potential harm.

#### Our Solution:
Bharat acts as a digital detective that:
- Understands content in multiple Indian languages
- Identifies potential claims and narratives
- Verifies information against trusted sources
- Provides clear, evidence-based assessments

#### Who It Helps:
- Journalists verifying stories in regional languages
- Fact-checkers combating local misinformation
- Everyday citizens seeking to confirm information before sharing
- Researchers studying information flows in regional contexts

During elections, health crises, or regional events, Bharat works quietly in the background to ensure that truth has a fighting chance against misinformation.
"""

# --- Project Steps ---
PROJECT_STEPS = [
    {
        "title": "Reddit Search",
        "description": "We search Reddit for discussions on regional topics in India. The system uses AI to refine your search query to find the most relevant discussions.",
        "icon": "🔍"
    },
    {
        "title": "Data Extraction",
        "description": "We extract key information from the Reddit posts, including titles, content, comments, and metadata to prepare for analysis.",
        "icon": "📥"
    },
    {
        "title": "Language Translation",
        "description": "Regional language content is translated to English using advanced translation models, enabling our AI systems to analyze the content effectively.",
        "icon": "🌐"
    },
    {
        "title": "Claim Identification",
        "description": "Our AI analyzes the translated content to identify potential claims, statements, or narratives that could be verified or debunked.",
        "icon": "🧠"
    },
    {
        "title": "Fact-Checking",
        "description": "We search through trusted news sources and official databases to find evidence that supports or contradicts each identified claim.",
        "icon": "📰"
    },
    {
        "title": "AI Classification",
        "description": "Using advanced AI models, we classify each claim as TRUE, FALSE, or UNVERIFIABLE based on the available evidence.",
        "icon": "🎯"
    },
    {
        "title": "Results Presentation",
        "description": "We present the findings in an easy-to-understand format with explanations, evidence, and confidence levels for each claim.",
        "icon": "📊"
    }
]

# --- Hardcoded File Paths ---
REDDIT_OUTPUT_PATH = "reddit_search_output.json"
EXTRACTED_PATH = "extracted_data.json"
TRANSLATED_PATH = "translated_data.json"
CLAIMS_PATH = "/home/abhi/Pictures/custom_results/verified_claims.json"
FACT_CHECK_PATH = "/home/abhi/Pictures/custom_results/fact_check_results.json"
CLASSIFICATION_PATH = "/home/abhi/Pictures/custom_results/fact_check_classification_results.json"
MODEL_PATH = "/home/abhi/Pictures/DeepSeek-R1-Distill-Qwen-1.5B.Q4_K_M.gguf"

# --- Session State Initialization ---
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
    if 'fact_check_done' not in st.session_state:
        st.session_state.fact_check_done = False
    if 'classification_done' not in st.session_state:
        st.session_state.classification_done = False
    if 'final_results' not in st.session_state:
        st.session_state.final_results = None

# --- Helper function to display reasoning ---
def display_reasoning_section(claim_data):
    """Display the reasoning and full response for a claim."""
    if 'reasoning' in claim_data and claim_data['reasoning']:
        with st.expander("🧠 AI Reasoning Process"):
            st.write(claim_data['reasoning'])
    
    if 'full_response' in claim_data and claim_data['full_response']:
        with st.expander("📄 Complete AI Response"):
            st.write(claim_data['full_response'])

# --- Main Application Logic ---
def main():
    initialize_session_state()

    # --- UI Header and Description ---
    st.set_page_config(page_title=PROJECT_NAME, layout="wide")
    
    # Custom CSS for cybersecurity theme
    st.markdown("""
    <style>
        /* Cybersecurity color theme */
        :root {
            --primary-color: #00D9FF; /* Bright cyan for highlights */
            --secondary-color: #0A2540; /* Dark blue for backgrounds */
            --tertiary-color: #1E3A5F; /* Medium blue for cards */
            --accent-color: #00FF88; /* Bright green for success */
            --warning-color: #FF6B6B; /* Red for warnings */
            --text-color: #E0E0E0; /* Light gray for text */
            --heading-color: #FFFFFF; /* White for headings */
        }
        
        /* Global styles */
        .stApp {
            background-color: var(--secondary-color);
            color: var(--text-color);
        }
        
        /* Typography */
        .main-title {
            font-size: 3rem !important;
            font-weight: bold;
            text-align: center;
            margin-bottom: 1rem;
            color: var(--heading-color);
            text-shadow: 0 0 10px rgba(0, 217, 255, 0.5);
        }
        
        .subtitle {
            font-size: 1.5rem !important;
            text-align: center;
            margin-bottom: 2rem;
            color: var(--primary-color);
        }
        
        .section-header {
            font-size: 2rem !important;
            font-weight: bold;
            margin-top: 2rem;
            margin-bottom: 1rem;
            color: var(--primary-color);
            padding-bottom: 0.5rem;
        }
        
        /* HOW TO ADJUST BOX SIZES: */
        /* 1. Adjust 'padding' to control internal spacing */
        /* 2. Adjust 'min-height' to control minimum height */
        /* 3. Adjust 'margin-bottom' to control spacing between boxes */
        /* 4. Adjust 'width' if you want specific width (not recommended with columns) */
        
        /* Objective cards - More compact with vertical content */
        .card {
            background-color: var(--tertiary-color);
            padding: 1rem; /* Reduced from 1.5rem for more compact look */
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            margin-bottom: 1rem;
            height: 100%;
            min-height: 140px; /* Reduced from 180px for smaller boxes */
            border: 1px solid rgba(0, 217, 255, 0.3);
            display: flex;
            flex-direction: column;
        }
        
        .card-title {
            font-size: 1.3rem !important; /* Reduced from 1.5rem */
            font-weight: bold;
            margin-bottom: 0.5rem;
            color: var(--primary-color);
        }
        
        .card-content {
            font-size: 1rem !important; /* Reduced from 1.1rem */
            flex-grow: 1;
            line-height: 1.4; /* Added for better readability */
        }
        
        /* Step cards - More compact with consistent sizing */
        .step-card {
            background-color: var(--tertiary-color);
            padding: 1rem; /* Reduced from 1.5rem */
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            margin-bottom: 1rem;
            height: 100%;
            min-height: 220px; /* Reduced from 280px for smaller boxes */
            border-left: 5px solid var(--primary-color);
            border: 1px solid rgba(0, 217, 255, 0.3);
            display: flex;
            flex-direction: column;
        }
        
        .step-number {
            font-size: 1.5rem; /* Reduced from 2rem */
            font-weight: bold;
            color: var(--primary-color);
            margin-bottom: 0.3rem; /* Reduced from 0.5rem */
        }
        
        .step-title {
            font-size: 1.3rem !important; /* Reduced from 1.4rem */
            font-weight: bold;
            margin-bottom: 0.5rem;
            color: var(--primary-color);
        }
        
        .step-content {
            font-size: 0.95rem !important; /* Reduced from 1.1rem */
            flex-grow: 1;
            line-height: 1.9; /* Added for better readability */
        }
        
        .icon-large {
            font-size: 2.0rem; /* Reduced from 3rem */
            text-align: center;
            margin-bottom: 0.5rem; /* Reduced from 1rem */
            filter: drop-shadow(0 0 5px rgba(0, 217, 255, 0.5));
        }
        .steps-container{
            margin-top: -1rem;
        }
        
        /* Streamlit component overrides */
        div.stButton > button:first-child {
            background-color: var(--primary-color);
            color: var(--secondary-color);
            font-weight: bold;
            border: none;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
        }
        
        div.stButton > button:first-child:hover {
            background-color: var(--accent-color);
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
        }
        
        div.stTextInput > div > div > input {
            background-color: var(--tertiary-color);
            color: var(--text-color);
            border: 1px solid var(--primary-color);
        }
        
        div.stSelectbox > div > div > select {
            background-color: var(--tertiary-color);
            color: var(--text-color);
            border: 1px solid var(--primary-color);
        }
        
        /* Expander styles */
        .streamlit-expanderHeader {
            background-color: var(--tertiary-color);
            color: var(--primary-color);
            font-weight: bold;
            border-radius: 5px;
            border: 1px solid rgba(0, 217, 255, 0.3);
        }
        
        .streamlit-expanderContent {
            background-color: var(--tertiary-color);
            border-radius: 5px;
            border: 1px solid rgba(0, 217, 255, 0.3);
        }
        
        /* Progress bar */
        .stProgress > div > div > div > div {
            background-color: var(--primary-color);
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            background-color: var(--tertiary-color);
            border-radius: 5px;
            border: 1px solid rgba(0, 217, 255, 0.3);
        }
        
        .stTabs [data-baseweb="tab"] {
            color: var(--text-color);
        }
        
        /* Metrics */
        div[data-testid="metric-container"] {
            background-color: var(--tertiary-color);
            border: 1px solid rgba(0, 217, 255, 0.3);
            padding: 1rem;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }
        
        /* Info messages */
        .stInfo {
            background-color: rgba(0, 217, 255, 0.1);
            border-left: 5px solid var(--primary-color);
            color: var(--text-color);
        }
        
        .stSuccess {
            background-color: rgba(0, 255, 136, 0.1);
            border-left: 5px solid var(--accent-color);
            color: var(--text-color);
        }
        
        .stWarning {
            background-color: rgba(255, 107, 107, 0.1);
            border-left: 5px solid var(--warning-color);
            color: var(--text-color);
        }
        
        .stError {
            background-color: rgba(255, 107, 107, 0.2);
            border-left: 5px solid var(--warning-color);
            color: var(--text-color);
        }
        
        /* Sidebar */
        .css-1d391kg {
            background-color: var(--secondary-color);
        }
        
        /* Download button */
        .stDownloadButton > button {
            background-color: var(--primary-color);
            color: var(--secondary-color);
            font-weight: bold;
            border: none;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 10px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--secondary-color);
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--primary-color);
            border-radius: 5px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--accent-color);
        }
        
        /* Fix for horizontal lines crossing boxes */
        hr {
            border: none;
            height: 2px;
            background-color: var(--primary-color);
            margin: 2rem 0;
        }
        
        /* Column container fix */
        .element-container:has(> div[data-testid="stHorizontalBlock"]) {
            border: none !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Main title with custom styling
    st.markdown(f'<h1 class="main-title">{PROJECT_NAME}</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="subtitle">{SYSTEM_DESCRIPTION}</p>', unsafe_allow_html=True)
    
    # --- Project Objective Section ---
    st.markdown('<h2 class="section-header">📖 About Project Bharat</h2>', unsafe_allow_html=True)
    
    # Create columns for objective cards
    obj_col1, obj_col2 = st.columns(2)
    
    with obj_col1:
        st.markdown("""
        <div class="card">
            <div class="card-title">🎯 Our Mission</div>
            <div class="card-content">Fighting misinformation in regional languages across India by providing intelligent, multilingual fact-checking capabilities.</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="card">
            <div class="card-title">🔍 The Problem</div>
            <div class="card-content">Misinformation spreads rapidly through social media and local news sites, especially in regional languages where verification is challenging.</div>
        </div>
        """, unsafe_allow_html=True)
    
    with obj_col2:
        st.markdown("""
        <div class="card">
            <div class="card-title">💡 Our Solution</div>
            <div class="card-content">Bharat acts as a digital detective that understands content in multiple Indian languages and provides evidence-based assessments.</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="card">
            <div class="card-title">👥 Who It Helps</div>
            <div class="card-content">Journalists, fact-checkers, everyday citizens, and researchers seeking to verify information in regional languages.</div>
        </div>
        """, unsafe_allow_html=True)
    
    # --- Project Steps Section ---
    st.markdown('<h2 class="section-header">🔄 How It Works: Our Process</h2>', unsafe_allow_html=True)
    
    # Create columns for step cards
    steps_col1, steps_col2, steps_col3 = st.columns(3)
    
    # Distribute steps across columns
    for i, step in enumerate(PROJECT_STEPS):
        column = [steps_col1, steps_col2, steps_col3][i % 3]
        
        with column:
            st.markdown(f"""
            <div class="step-card">
                <div class="icon-large">{step['icon']}</div>
                <div class="step-number">Step {i+1}</div>
                <div class="step-title">{step['title']}</div>
                <div class="step-content">{step['description']}</div>
            </div>
            """, unsafe_allow_html=True)

    # --- Progress Indicator ---
    if st.session_state.process_started:
        progress_steps = ["🔍 Search", "📥 Scrape", "🌐 Translate", "🧠 Analyze", "📰 Fact-Check", "🎯 Classify", "📊 Results"]
        current_step = 1
        if st.session_state.scraping_done:
            current_step = 3
        if st.session_state.translation_approved:
            current_step = 4
        if st.session_state.final_claims:
            current_step = 5
        if st.session_state.fact_check_done:
            current_step = 6
        if st.session_state.classification_done:
            current_step = 7
        
        progress_text = " → ".join(progress_steps[:current_step])
        st.info(f"**Current Progress:** {progress_text}")
        st.markdown("---")

    # --- User Input Section ---
    st.markdown('<h2 class="section-header">1. 🔍 Enter Search Topic</h2>', unsafe_allow_html=True)
    user_query = st.text_input(
        "Enter a topic to search on Reddit (e.g., 'Indian Defense', 'Karnataka Politics')",
        placeholder="Type your query here..."
    )

    if st.button("🚀 Start Analysis", type="primary", disabled=st.session_state.process_started):
        if not user_query.strip():
            st.error("⚠️ Search query cannot be empty. Please enter a topic.")
            return
        
        st.session_state.process_started = True
        with st.spinner("🤖 Refining your query using AI..."):
            st.session_state.refined_query = gemini_reduce_query(user_query)
        st.rerun()

    # --- Step 0: Confirm Refined Query and Scrape Data ---
    if st.session_state.process_started and not st.session_state.scraping_done:
        st.markdown('<h2 class="section-header">2. 📥 Confirm Search & Scrape Data</h2>', unsafe_allow_html=True)
        st.info(f"🤖 AI-generated search query: **\"{st.session_state.refined_query}\"**")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Yes, Scrape Reddit", key="scrape_yes"):
                with st.spinner(f"🔍 Searching Reddit for '{st.session_state.refined_query}' and extracting data..."):
                    try:
                        scraper = RedditScraper()
                        if scraper.reddit:
                            scraped_data = scraper.search_and_fetch(st.session_state.refined_query, limit=15)
                            if scraped_data:
                                with open(REDDIT_OUTPUT_PATH, "w") as f:
                                    json.dump(scraped_data, f, indent=4)
                                st.success(f"✅ Successfully scraped {len(scraped_data)} posts.")
                                
                                # Step 1: Extract data
                                with st.spinner("📋 Extracting relevant content..."):
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
        st.markdown('<h2 class="section-header">3. 🌐 Translate Extracted Data</h2>', unsafe_allow_html=True)
        st.info("📄 The raw data has been extracted. The next step is to translate it to English for analysis.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🌐 Proceed with Translation", key="translate_yes"):
                st.session_state.translation_approved = True
                st.rerun()
        with col2:
            if st.button("⏭️ Skip Translation", key="translate_no"):
                st.warning("⚠️ Translation skipped. Cannot proceed to claim generation without translated data.")
                st.session_state.process_started = False
                st.rerun()

    # --- Step 3: Perform Translation and Generate Claims ---
    if st.session_state.translation_approved and not st.session_state.final_claims:
        st.markdown('<h2 class="section-header">4. 🧠 Processing and Generating Claims</h2>', unsafe_allow_html=True)
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Step 1: Translation
        status_text.text("🌐 Translating data... This may take a few minutes.")
        progress_bar.progress(25)
        
        try:
            translate_json_data(EXTRACTED_PATH, TRANSLATED_PATH)
            if os.path.exists(TRANSLATED_PATH):
                status_text.text("✅ Translation completed successfully.")
                progress_bar.progress(50)
            else:
                status_text.text("❌ Translation failed.")
                progress_bar.progress(0)
                return
        except Exception as e:
            status_text.text(f"❌ An error occurred during translation: {e}")
            progress_bar.progress(0)
            return

        # Step 2: Generate claims
        status_text.text("🧠 Generating claims from translated data...")
        progress_bar.progress(75)
        
        try:
            claims = generate_claims_json_from_translated(TRANSLATED_PATH)
            status_text.text("✅ Claims generation completed!")
            progress_bar.progress(100)
            st.session_state.final_claims = claims
            time.sleep(1)
            st.rerun()
        except Exception as e:
            status_text.text(f"❌ An error occurred during claim generation: {e}")
            progress_bar.progress(0)

    # --- Step 4: Fact-Checking ---
    if st.session_state.final_claims and not st.session_state.fact_check_done:
        st.markdown('<h2 class="section-header">5. 📰 Fact-Checking Claims</h2>', unsafe_allow_html=True)
        st.info("🔍 Now performing fact-checking on the generated claims using news APIs...")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📰 Start Fact-Checking", key="fact_check_yes"):
                with st.spinner("🔍 Performing fact-checking... This may take several minutes."):
                    try:
                        # Ensure directory exists
                        os.makedirs(os.path.dirname(CLAIMS_PATH), exist_ok=True)
                        
                        # Save claims if not already saved
                        if not os.path.exists(CLAIMS_PATH):
                            with open(CLAIMS_PATH, 'w') as f:
                                json.dump(st.session_state.final_claims, f, indent=4)
                        
                        # Import and run fact-checking
                        from fact_check import run_fact_checking_process
                        
                        fact_check_output = run_fact_checking_process(
                            json_file_path=CLAIMS_PATH,
                            results_filename=FACT_CHECK_PATH,
                            max_api_calls=10
                        )
                        
                        if fact_check_output:
                            st.success("✅ Fact-checking completed successfully!")
                            st.session_state.fact_check_done = True
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Fact-checking failed.")
                    except Exception as e:
                        st.error(f"An error occurred during fact-checking: {e}")
        
        with col2:
            if st.button("⏭️ Skip Fact-Checking", key="fact_check_no"):
                st.warning("⚠️ Fact-checking skipped. Results may be less accurate.")
                st.session_state.fact_check_done = True
                st.rerun()

    # --- Step 5: LLM Classification ---
    if st.session_state.fact_check_done and not st.session_state.classification_done:
        st.markdown('<h2 class="section-header">6. 🎯 Classifying Claims with AI</h2>', unsafe_allow_html=True)
        st.info("🧠 Now classifying claims using advanced AI model for final verification...")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🎯 Start Classification", key="classify_yes"):
                with st.spinner("🧠 Running AI classification... This may take several minutes."):
                    try:
                        # Ensure directory exists
                        os.makedirs(os.path.dirname(CLASSIFICATION_PATH), exist_ok=True)
                        
                        # Import and run classification
                        from main5 import run_llm_classification_process
                        
                        classification_output = run_llm_classification_process(
                            input_file_path=FACT_CHECK_PATH,
                            model_path=MODEL_PATH,
                            output_file_path=CLASSIFICATION_PATH
                        )
                        
                        if classification_output:
                            # Load the final results
                            with open(CLASSIFICATION_PATH, 'r') as f:
                                st.session_state.final_results = json.load(f)
                            
                            st.success("✅ Classification completed successfully!")
                            st.session_state.classification_done = True
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Classification failed.")
                    except Exception as e:
                        st.error(f"An error occurred during classification: {e}")
        
        with col2:
            if st.button("⏭️ Skip Classification", key="classify_no"):
                st.warning("⚠️ Classification skipped. Using fact-check results as final.")
                # Load fact-check results as final
                if os.path.exists(FACT_CHECK_PATH):
                    with open(FACT_CHECK_PATH, 'r') as f:
                        st.session_state.final_results = json.load(f)
                st.session_state.classification_done = True
                st.rerun()

    # --- Step 6: Display Final Results ---
    if st.session_state.classification_done and st.session_state.final_results:
        st.markdown('<h2 class="section-header">7. 📊 Final Analysis Results</h2>', unsafe_allow_html=True)
        st.info("📝 Below are the final classified results after fact-checking and AI analysis.")
        
        # Get the claims data
        if 'classifications' in st.session_state.final_results:
            claims_data = st.session_state.final_results['classifications']
        elif 'verified_claims' in st.session_state.final_results:
            claims_data = st.session_state.final_results['verified_claims']
        else:
            claims_data = st.session_state.final_claims if st.session_state.final_claims else []
        
        # Model information
        if 'model_used' in st.session_state.final_results:
            st.info(f"**Model Used:** {st.session_state.final_results['model_used']}")
        
        # Summary statistics
        total_claims = len(claims_data)
        verified_true = sum(1 for claim in claims_data if claim.get('classification') == 'TRUE' or claim.get('verification_status') == 'verified_true')
        verified_false = sum(1 for claim in claims_data if claim.get('classification') == 'FALSE' or claim.get('verification_status') == 'verified_false')
        unverified = sum(1 for claim in claims_data if claim.get('classification') in ['UNVERIFIABLE', 'UNVERIFIED'] or claim.get('verification_status') in ['unverified', 'requires_external_verification'])
        historical = sum(1 for claim in claims_data if claim.get('is_historical_claim', False))
        
        st.markdown('<h3 class="section-header">📈 Summary Statistics</h3>', unsafe_allow_html=True)
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("📊 Total Claims", total_claims)
        with col2:
            st.metric("✅ Verified True", verified_true)
        with col3:
            st.metric("❌ Verified False", verified_false)
        with col4:
            st.metric("❓ Unverified", unverified)
        with col5:
            st.metric("📚 Historical", historical)
        
        st.markdown("---")
        
        # Tabs for different views
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 All Claims", "✅ Verified Claims", "🔍 Claims Needing Verification", "📰 Fact-Check Details", "🧠 AI Reasoning"])
        
        with tab1:
            st.markdown('<h3 class="section-header">📋 All Detected Claims</h3>', unsafe_allow_html=True)
            if claims_data:
                for i, claim in enumerate(claims_data):
                    # Get classification status
                    if 'classification' in claim:
                        status = claim.get('classification', 'UNVERIFIABLE')
                    else:
                        status = claim.get('verification_status', 'unverified')
                    
                    confidence = claim.get('confidence', 'medium')
                    impact = claim.get('potential_impact', 'medium')
                    is_historical = claim.get('is_historical_claim', False)
                    
                    status_emoji = {
                        'TRUE': '✅',
                        'verified_true': '✅',
                        'FALSE': '❌', 
                        'verified_false': '❌',
                        'UNVERIFIABLE': '❓',
                        'UNVERIFIED': '❓',
                        'unverified': '❓',
                        'requires_external_verification': '🔍'
                    }.get(status, '❓')
                    
                    with st.expander(f"{status_emoji} Claim #{i+1}: {claim.get('claim', 'Unknown claim')[:80]}..."):
                        st.write(f"**📢 Claim:** {claim.get('claim', 'Unknown claim')}")
                        st.write(f"**📂 Category:** {claim.get('category', 'general')}")
                        st.write(f"**🔍 Classification Status:** {status_emoji} {status}")
                        st.write(f"**📊 Confidence:** {confidence}")
                        st.write(f"**💥 Potential Impact:** {impact}")
                        st.write(f"**📝 Explanation:** {claim.get('explanation', 'No explanation provided')}")
                        st.write(f"**🔎 Fact Check Notes:** {claim.get('fact_check_notes', 'No notes provided')}")
                        st.write(f"**🔍 Search Query:** {claim.get('search_query', 'No query provided')}")
                        st.write(f"**🌐 Needs External Verification:** {'Yes' if claim.get('needs_external_verification') else 'No'}")
                        if is_historical:
                            st.write(f"**📜 Historical Evidence:** {claim.get('historical_evidence', 'No evidence provided')}")
                        st.write(f"**🔗 Source:** [Post #{claim.get('post_number', 'Unknown')}]({claim.get('source_url', '#')})")
                        st.write(f"**🕒 Timestamp:** {claim.get('timestamp', 'Unknown')}")
                        
                        # Show fact-check results if available
                        if 'articles' in claim and claim['articles']:
                            st.write(f"**📰 Fact-Check Articles Found:** {len(claim['articles'])}")
                            for j, article in enumerate(claim['articles'][:3], 1):  # Show first 3 articles
                                st.write(f"   {j}. {article.get('title', 'No title')}")
                                st.write(f"      Source: {article.get('source', 'Unknown')}")
                                st.write(f"      URL: {article.get('url', '#')}")
                        
                        # Display reasoning and full response
                        display_reasoning_section(claim)
            else:
                st.info("No claims found.")
        
        with tab2:
            st.markdown('<h3 class="section-header">✅ Verified Claims</h3>', unsafe_allow_html=True)
            verified_claims = [claim for claim in claims_data if claim.get('classification') in ['TRUE', 'FALSE'] or claim.get('verification_status') in ['verified_true', 'verified_false']]
            
            if verified_claims:
                for i, claim in enumerate(verified_claims):
                    # Get classification status
                    if 'classification' in claim:
                        status = claim.get('classification', 'UNVERIFIABLE')
                    else:
                        status = claim.get('verification_status', 'unverified')
                    
                    is_true = status in ['TRUE', 'verified_true']
                    status_emoji = '✅' if is_true else '❌'
                    
                    with st.expander(f"{status_emoji} Verified Claim #{i+1}: {claim.get('claim', 'Unknown claim')[:80]}..."):
                        st.write(f"**📢 Claim:** {claim.get('claim', 'Unknown claim')}")
                        st.write(f"**🔍 Classification Status:** {status_emoji} {status}")
                        st.write(f"**📝 Explanation:** {claim.get('explanation', 'No explanation provided')}")
                        if claim.get('is_historical_claim'):
                            st.write(f"**📜 Historical Evidence:** {claim.get('historical_evidence', 'No evidence provided')}")
                        st.write(f"**🔗 Source:** [Post #{claim.get('post_number', 'Unknown')}]({claim.get('source_url', '#')})")
                        
                        # Display reasoning and full response
                        display_reasoning_section(claim)
            else:
                st.info("No verified claims found.")
        
        with tab3:
            st.markdown('<h3 class="section-header">🔍 Claims Needing Verification</h3>', unsafe_allow_html=True)
            unverified_claims = [claim for claim in claims_data if claim.get('classification') in ['UNVERIFIABLE', 'UNVERIFIED'] or claim.get('verification_status') in ['unverified', 'requires_external_verification']]
            
            if unverified_claims:
                for i, claim in enumerate(unverified_claims):
                    with st.expander(f"🔍 Unverified Claim #{i+1}: {claim.get('claim', 'Unknown claim')[:80]}..."):
                        st.write(f"**📢 Claim:** {claim.get('claim', 'Unknown claim')}")
                        st.write(f"**📂 Category:** {claim.get('category', 'general')}")
                        st.write(f"**📊 Confidence:** {claim.get('confidence', 'medium')}")
                        st.write(f"**💥 Potential Impact:** {claim.get('potential_impact', 'medium')}")
                        st.write(f"**📝 Explanation:** {claim.get('explanation', 'No explanation provided')}")
                        st.write(f"**🔎 Fact Check Notes:** {claim.get('fact_check_notes', 'No notes provided')}")
                        st.write(f"**🔍 Search Query:** {claim.get('search_query', 'No query provided')}")
                        st.write(f"**🔗 Source:** [Post #{claim.get('post_number', 'Unknown')}]({claim.get('source_url', '#')})")
                        
                        # Display reasoning and full response
                        display_reasoning_section(claim)
            else:
                st.info("No claims requiring verification found.")
        
        with tab4:
            st.markdown('<h3 class="section-header">📰 Fact-Check Details</h3>', unsafe_allow_html=True)
            if st.session_state.fact_check_done and os.path.exists(FACT_CHECK_PATH):
                with open(FACT_CHECK_PATH, 'r') as f:
                    fact_check_data = json.load(f)
                
                st.write(f"**🕒 Fact-Check Timestamp:** {fact_check_data.get('timestamp', 'Unknown')}")
                st.write(f"**📊 Total Claims Processed:** {len(fact_check_data.get('verified_claims', []))}")
                
                # Show API usage statistics
                api_calls = sum(1 for claim in fact_check_data.get('verified_claims', []) 
                              if claim.get('needs_external_verification', True))
                st.write(f"**🌐 API Calls Made:** {api_calls}")
                
                st.markdown("---")
                
                for i, claim in enumerate(fact_check_data.get('verified_claims', []), 1):
                    with st.expander(f"📰 Fact-Check for Claim #{i}: {claim.get('claim', 'Unknown')[:60]}..."):
                        st.write(f"**🔍 Verification Result:** {claim.get('verification_result', 'Unknown')}")
                        st.write(f"**📊 Total Tokens:** {claim.get('total_tokens', 0)}")
                        
                        if claim.get('articles'):
                            st.write(f"**📰 Articles Found:** {len(claim['articles'])}")
                            for j, article in enumerate(claim['articles'], 1):
                                st.write(f"   {j}. **Title:** {article.get('title', 'No title')}")
                                st.write(f"      **Source:** {article.get('source', 'Unknown')}")
                                st.write(f"      **URL:** {article.get('url', '#')}")
                                st.write(f"      **Content Tokens:** {article.get('content_tokens', 0)}")
                                if article.get('content'):
                                    content_preview = article['content'][:200] + "..." if len(article['content']) > 200 else article['content']
                                    st.write(f"      **Content Preview:** {content_preview}")
                                st.write("")
                        else:
                            st.write("**📰 No articles found for this claim**")
            else:
                st.info("Fact-checking was not performed or results not available.")
        
        with tab5:
            st.markdown('<h3 class="section-header">🧠 AI Reasoning Analysis</h3>', unsafe_allow_html=True)
            if claims_data:
                # Display model information
                if 'model_used' in st.session_state.final_results:
                    st.info(f"**Model Used:** {st.session_state.final_results['model_used']}")
                    st.info(f"**Max Tokens:** {st.session_state.final_results.get('max_tokens', 'N/A')}")
                    st.info(f"**Max Response Tokens:** {st.session_state.final_results.get('max_response_tokens', 'N/A')}")
                
                st.markdown("---")
                
                for i, claim in enumerate(claims_data):
                    # Get classification status
                    if 'classification' in claim:
                        status = claim.get('classification', 'UNVERIFIABLE')
                    else:
                        status = claim.get('verification_status', 'unverified')
                    
                    status_emoji = {
                        'TRUE': '✅',
                        'verified_true': '✅',
                        'FALSE': '❌', 
                        'verified_false': '❌',
                        'UNVERIFIABLE': '❓',
                        'UNVERIFIED': '❓',
                        'unverified': '❓',
                        'requires_external_verification': '🔍'
                    }.get(status, '❓')
                    
                    with st.expander(f"{status_emoji} AI Reasoning for Claim #{i+1}: {claim.get('claim', 'Unknown claim')[:80]}..."):
                        st.write(f"**📢 Claim:** {claim.get('claim', 'Unknown claim')}")
                        st.write(f"**🔍 Classification Status:** {status_emoji} {status}")
                        
                        # Display reasoning and full response
                        display_reasoning_section(claim)
                        
                        # Show articles used for classification
                        if 'articles_used' in claim and claim['articles_used']:
                            st.write(f"**📰 Articles Used for Classification:** {len(claim['articles_used'])}")
                            for j, article in enumerate(claim['articles_used'], 1):
                                st.write(f"   {j}. **Title:** {article.get('title', 'No title')}")
                                st.write(f"      **Source:** {article.get('source', 'Unknown')}")
                                st.write(f"      **URL:** {article.get('url', '#')}")
                        elif 'articles_count' in claim:
                            st.write(f"**📰 Articles Used for Classification:** {claim['articles_count']}")
            else:
                st.info("No claims found.")
        
        st.markdown("---")
        
        # Download buttons
        st.markdown('<h3 class="section-header">💾 Download Results</h3>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            claims_json = json.dumps(st.session_state.final_claims, indent=2)
            st.download_button(
                label="📥 Download Claims JSON",
                data=claims_json,
                file_name="reddit_claims_analysis.json",
                mime="application/json"
            )
        
        with col2:
            if os.path.exists(FACT_CHECK_PATH):
                with open(FACT_CHECK_PATH, 'r') as f:
                    fact_check_json = json.dumps(json.load(f), indent=2)
                st.download_button(
                    label="📰 Download Fact-Check JSON",
                    data=fact_check_json,
                    file_name="fact_check_results.json",
                    mime="application/json"
                )
        
        with col3:
            if os.path.exists(CLASSIFICATION_PATH):
                with open(CLASSIFICATION_PATH, 'r') as f:
                    classification_json = json.dumps(json.load(f), indent=2)
                st.download_button(
                    label="🎯 Download Final Classification",
                    data=classification_json,
                    file_name="final_classification_results.json",
                    mime="application/json"
                )
        
        st.markdown("---")
        
        # Reset button
        if st.button("🔄 Start New Analysis"):
            for key in st.session_state.keys():
                del st.session_state[key]
            initialize_session_state()
            st.rerun()

if __name__ == "__main__":
    main()
