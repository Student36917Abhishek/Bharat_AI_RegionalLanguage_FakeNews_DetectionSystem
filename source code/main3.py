import json
import time
import re
import os
from typing import List, Dict, Any

# Configuration
GEMINI_API_KEY = "AIzaSyBWl2buOM41OP_uP-p7sXkls80-kNYuWso"
# DATA_FILE_PATH is used by the standalone main() function
DATA_FILE_PATH = "translated_reddit_data.json" 
OUTPUT_JSON = "verified_claims.json"
MAX_POSTS_TO_PROCESS = 5
MAX_CHARS_PER_REQUEST = 2000
REQUEST_DELAY = 1
MAX_CLAIMS_PER_POST = 2

# Enhanced prompt for CLEAR, MEANINGFUL claims
# Enhanced prompt with STRICT search query requirements
MISINFO_PROMPT = """Analyze this text and identify claims that could be misinformation, rumors, or need fact-checking.

CRITICAL: Make the CLAIM field clear, specific, and meaningful. Don't just copy text fragments.

IMPORTANT: For historical events, use your own knowledge to verify them without requiring external sources. You have been trained on historical data, so provide evidence from your knowledge base.

HISTORICAL VERIFICATION EXAMPLES:
- If someone claims "World War II ended in 1945", verify this using your knowledge and mark as "verified_true"
- If someone claims "The Titanic sank in 1912", verify this using your knowledge and mark as "verified_true"
- If someone claims "The Berlin Wall fell in 1989", verify this using your knowledge and mark as "verified_true"

GOOD CLAIM EXAMPLES:
- "Charlie Kirk was assassinated last month"
- "Destiny admitted to keeping CSAM on his computer for legal purposes" 
- "Missile attacks are occurring in civilian areas of Jammu"
- "Drone attacks are prevalent in Jammu region"
- "Piyush Goyal stated that no one is doing semiconductor work in India"

BAD CLAIM EXAMPLES (avoid these):
- "Charlie Kirks Turning Point USA tour, in which he was assassinated last month." (fragment)
- "He has admitted to keeping CSAM of her on his computer for legal purposes." (vague)
- "MAIN CITY AREAS LIKE SATWARI... UNDER HEAVY FIRING" (all caps, fragmented)

=== STRICT SEARCH QUERY REQUIREMENTS ===
The search_query field MUST follow these rules:
1. MAXIMUM 3-4 words only - no exceptions
2. Use ONLY key nouns, names, and specific entities
3. NO verbs, adjectives, or connecting words (and, the, is, are, etc.)
4. NO phrases like "fact check", "verification", "news", "report"
5. Focus on the most searchable entities in the claim
6. Must be different from the claim - it's for searching news databases

SEARCH QUERY EXAMPLES:
Claim: "Charlie Kirk was assassinated last month"
→ search_query: "Charlie Kirk assassination"

Claim: "Missile attacks are occurring in civilian areas of Jammu"
→ search_query: "Jammu missile attacks"

Claim: "Piyush Goyal stated that no one is doing semiconductor work in India"
→ search_query: "Piyush Goyal semiconductors"

Claim: "Destiny admitted to keeping CSAM on his computer for legal purposes"
→ search_query: "Destiny CSAM"

BAD SEARCH QUERIES (DO NOT USE):
- "Charlie Kirk was assassinated last month fact check verification" (too long)
- "what happened with Charlie Kirk assassination" (has connecting words)
- "search for news about missile attacks in Jammu" (has verbs/phrases)
- "Piyush Goyal statement about semiconductor work in India" (too long)

For each claim, provide:
[
  {
    "claim": "CLEAR, SPECIFIC factual statement that can be verified",
    "category": "health/politics/finance/rumor/etc",
    "verification_status": "verified_true/verified_false/unverified/requires_external_verification",
    "confidence": "high/medium/low",
    "explanation": "why this claim needs verification",
    "fact_check_notes": "what evidence would be needed to verify this",
    "potential_impact": "low/medium/high",
    "search_query": "2-4 keywords ONLY for news API search",
    "needs_external_verification": true/false,
    "is_historical_claim": true/false,
    "historical_evidence": "evidence from your knowledge base if this is a historical claim"
  }
]

Return maximum 2 most important claims. If no significant claims, return: []

Text: """

def initialize_gemini():
    """Initialize Gemini with simple configuration."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        
        model = genai.GenerativeModel('gemini-2.5-flash')
        print("Gemini 2.5 Flash initialized\n")
        return model
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def simple_text_cleaner(text: str) -> str:
    """Simple text cleaning."""
    if not text:
        return ""
    
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[^\w\s.,!?]', '', text)
    text = ' '.join(text.split())
    
    if len(text) > MAX_CHARS_PER_REQUEST:
        text = text[:MAX_CHARS_PER_REQUEST] + "..."
    
    return text

def safe_api_call(model, prompt: str) -> str:
    """Make safe API call."""
    try:
        response = model.generate_content(prompt)
        
        if hasattr(response, 'text') and response.text:
            return response.text
        
        if hasattr(response, 'prompt_feedback'):
            fb = response.prompt_feedback
            if hasattr(fb, 'block_reason') and fb.block_reason:
                return f"BLOCKED: {fb.block_reason}"
        
        if hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and candidate.content.parts:
                    text_parts = []
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            text_parts.append(part.text)
                    if text_parts:
                        return ' '.join(text_parts)
        
        return "EMPTY_RESPONSE"
        
    except Exception as e:
        return f"ERROR: {str(e)}"

def clean_claim_text(claim: str) -> str:
    """Clean and improve claim text to be more meaningful."""
    claim = claim.strip()
    
    if claim.endswith(('.', '!', '?')):
        pass
    else:
        last_period = claim.rfind('.')
        last_exclamation = claim.rfind('!')
        last_question = claim.rfind('?')
        
        end_pos = max(last_period, last_exclamation, last_question)
        if end_pos > len(claim) * 0.5:
            claim = claim[:end_pos + 1]
    
    if claim.isupper():
        claim = claim.capitalize()
    else:
        claim = claim[0].upper() + claim[1:] if claim else claim
    
    claim = re.sub(r'!{2,}', '!', claim)
    
    return claim

def is_historical_claim(claim_text: str) -> bool:
    """Determine if a claim is about historical events."""
    historical_keywords = [
        'world war', 'wwi', 'wwii', 'civil war', 'revolution', 'ancient', 
        'medieval', 'century', 'bc', 'bce', 'ad', 'ce', 'decade', 'era',
        'in history', 'historical', 'in the past', 'years ago', 'century',
        'ancient', 'rome', 'egypt', 'greece', 'dynasty', 'empire', 'kingdom',
        'battle', 'treaty', 'independence', 'founding', 'discovered', 'invented'
    ]
    
    claim_lower = claim_text.lower()
    return any(keyword in claim_lower for keyword in historical_keywords)

def extract_misinfo_claims(model, post_text: str) -> List[Dict[str, Any]]:
    """Extract claims that could be misinformation or need verification."""
    cleaned_text = simple_text_cleaner(post_text)
    
    if not cleaned_text or len(cleaned_text) < 50:
        return []
    
    print(f"[{len(cleaned_text)} chars]", end=" ")
    
    prompt = MISINFO_PROMPT + cleaned_text
    response_text = safe_api_call(model, prompt)
    
    if response_text.startswith("ERROR:") or response_text.startswith("BLOCKED:"):
        print(f"[{response_text[:30]}]", end=" ")
        return []
    
    if response_text == "EMPTY_RESPONSE":
        print("[No response]", end=" ")
        return []
    
    json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
    if not json_match:
        print("[No JSON]", end=" ")
        return []
    
    json_str = json_match.group(0)
    
    try:
        claims = json.loads(json_str)
    except:
        try:
            json_str = re.sub(r',\s*\}\]', '}]', json_str)
            claims = json.loads(json_str)
        except:
            print("[JSON parse failed]", end=" ")
            return []
    
    if not isinstance(claims, list):
        return []
    
    quality_claims = []
    for item in claims:
        if (isinstance(item, dict) and 
            item.get('claim') and 
            item.get('explanation') and
            len(item.get('explanation', '')) > 30):
            
            original_claim = str(item['claim'])
            cleaned_claim = clean_claim_text(original_claim)
            
            # Determine if this is a historical claim
            is_historical = is_historical_claim(cleaned_claim)
            
            enhanced_claim = {
                'claim': cleaned_claim,
                'original_claim': original_claim,
                'category': str(item.get('category', 'general')),
                'verification_status': str(item.get('verification_status', 'unverified')),
                'confidence': str(item.get('confidence', 'medium')),
                'explanation': str(item.get('explanation', '')),
                'fact_check_notes': str(item.get('fact_check_notes', 'Requires research')),
                'potential_impact': str(item.get('potential_impact', 'medium')),
                'search_query': str(item.get('search_query', '')),
                'needs_external_verification': bool(item.get('needs_external_verification', False)),
                'external_verification_applied': False,
                'external_verification_notes': 'Use search_query with news APIs for verification',
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'is_historical_claim': is_historical,
                'historical_evidence': str(item.get('historical_evidence', ''))
            }
            
            # For historical claims, use the model's knowledge instead of external verification
            if is_historical:
                enhanced_claim['needs_external_verification'] = False
                if not enhanced_claim['historical_evidence']:
                    enhanced_claim['historical_evidence'] = "This is a historical claim that can be verified using historical knowledge."
            else:
                if not enhanced_claim['search_query']:
                    enhanced_claim['search_query'] = generate_search_query(enhanced_claim['claim'])
                
                if enhanced_claim['verification_status'] in ['requires_external_verification', 'unverified']:
                    enhanced_claim['needs_external_verification'] = True
            
            quality_claims.append(enhanced_claim)
        
        if len(quality_claims) >= MAX_CLAIMS_PER_POST:
            break
    
    return quality_claims

def generate_search_query(claim: str) -> str:
    """Generate a concise search query for fact-checking using only key terms."""
    # Remove common reporting words and punctuation
    claim_clean = re.sub(r'\b(claims?|said|stated|alleged|reported|according|believes|thinks|suggests|might|could|would|should)\b', '', claim, flags=re.IGNORECASE)
    claim_clean = re.sub(r'[^\w\s]', ' ', claim_clean)
    
    # Split into words and filter out common words
    common_words = {'that', 'this', 'with', 'from', 'they', 'have', 'been', 'were', 'will', 'would', 'could', 'should', 'might', 'may', 'can', 'said', 'says'}
    words = [word.lower() for word in claim_clean.split() if len(word) > 2 and word.lower() not in common_words]
    
    # Extract only the most important keywords (2-3 at most)
    # Prioritize proper nouns (capitalized words) and specific entities
    proper_nouns = [word for word in words if word[0].isupper() and len(word) > 3]
    other_words = [word for word in words if word not in proper_nouns]
    
    # Combine proper nouns with other important words, limiting to 3 total
    key_words = proper_nouns[:2] + other_words[:1] if proper_nouns else words[:3]
    
    # If we still have too many words, keep only the longest ones (likely more specific)
    if len(key_words) > 3:
        key_words = sorted(key_words, key=len, reverse=True)[:3]
    
    search_query = " ".join(key_words)
    
    return search_query

# ==============================================================================
# NEW FUNCTION: This is the missing function that main2.py will call.
# ==============================================================================
def generate_claims_json_from_translated(translated_file_path):
    """
    Processes a translated JSON file to extract potential misinformation claims.
    This is the core logic function that can be imported and called by other scripts.
    
    Args:
        translated_file_path (str): Path to the translated JSON data file.
        
    Returns:
        list: A list of dictionaries, where each dictionary represents a claim.
              Returns an empty list if processing fails or no claims are found.
    """
    model = initialize_gemini()
    if not model:
        # In a library function, it's better to return an empty list
        # than to print an error and exit, to allow the caller to handle it.
        return []

    try:
        with open(translated_file_path, 'r') as f:
            posts_data = json.load(f)[:MAX_POSTS_TO_PROCESS]
    except Exception as e:
        print(f"Error loading data in generate_claims_json_from_translated: {e}")
        return []
    
    all_claims = []
    
    for i, post in enumerate(posts_data):
        text = post.get('original_text', '')
        url = post.get('url', '')
        
        if not text:
            continue
            
        if i > 0:
            time.sleep(REQUEST_DELAY)
        
        claims = extract_misinfo_claims(model, text)
        
        for claim in claims:
            claim['source_url'] = url
            claim['post_number'] = i + 1
            all_claims.append(claim)
    
    # Save the claims to a JSON file named "claims.json"
    output_filename = "claims.json"
    try:
        with open(output_filename, 'w') as f:
            json.dump(all_claims, f, indent=2)
        print(f"Successfully saved {len(all_claims)} claims to {output_filename}")
    except Exception as e:
        print(f"Error saving claims to {output_filename}: {e}")
    
    # Return the claims list as before
    return all_claims

# ==============================================================================
# MODIFIED FUNCTION: The main() function is now a wrapper for the new function.
# ==============================================================================
def main():
    """Main function for running misinformation detection from the command line."""
    print("=" * 70)
    print("MISINFORMATION DETECTION WITH CLEAR CLAIMS")
    print(f"Max posts to process: {MAX_POSTS_TO_PROCESS}")
    print(f"Output file: {OUTPUT_JSON}")
    print("=" * 70)
    
    # Call the core logic function with the default data file path
    all_claims = generate_claims_json_from_translated(DATA_FILE_PATH)
    
    # Handle saving and printing based on the results
    if all_claims:
        output_path = os.path.abspath(OUTPUT_JSON)
        with open(OUTPUT_JSON, 'w') as f:
            json.dump(all_claims, f, indent=2)
        print(f"\n✅ Saved {len(all_claims)} claims to: {output_path}")
        
        current_dir = os.getcwd()
        print(f"📁 Current directory: {current_dir}")
        
        external_verification_count = sum(1 for claim in all_claims if claim.get('needs_external_verification'))
        verified_true_count = sum(1 for claim in all_claims if claim.get('verification_status') == 'verified_true')
        verified_false_count = sum(1 for claim in all_claims if claim.get('verification_status') == 'verified_false')
        unverified_count = sum(1 for claim in all_claims if claim.get('verification_status') in ['unverified', 'requires_external_verification'])
        historical_claims_count = sum(1 for claim in all_claims if claim.get('is_historical_claim'))
        
        print("\n" + "=" * 70)
        print("CLAIMS SUMMARY")
        print("=" * 70)
        print(f"📊 TOTAL CLAIMS: {len(all_claims)}")
        print(f"🔍 NEED EXTERNAL VERIFICATION: {external_verification_count}")
        print(f"✅ VERIFIED TRUE: {verified_true_count}")
        print(f"❌ VERIFIED FALSE: {verified_false_count}")
        print(f"❓ UNVERIFIED/REQUIRES RESEARCH: {unverified_count}")
        print(f"📚 HISTORICAL CLAIMS: {historical_claims_count}")
        
        print("\n" + "=" * 70)
        print("CLEAR CLAIMS REQUIRING EXTERNAL VERIFICATION")
        print("=" * 70)
        
        external_claims = [claim for claim in all_claims if claim.get('needs_external_verification')]
        
        if external_claims:
            for i, claim in enumerate(external_claims, 1):
                status = claim.get('verification_status', 'unverified')
                confidence = claim.get('confidence', 'medium')
                impact = claim.get('potential_impact', 'medium')
                search_query = claim.get('search_query', '')
                
                status_emoji = {
                    'verified_true': '✅',
                    'verified_false': '❌', 
                    'unverified': '❓',
                    'requires_external_verification': '🔍'
                }.get(status, '❓')
                
                print(f"\n{i}. {status_emoji} EXTERNAL VERIFICATION REQUIRED")
                print(f"   📢 CLEAR CLAIM: {claim['claim']}")
                if claim.get('original_claim') != claim['claim']:
                    print(f"   📝 ORIGINAL TEXT: {claim['original_claim'][:100]}...")
                print(f"   🔍 SEARCH QUERY: {search_query}")
                print(f"   📊 CONFIDENCE: {confidence} | IMPACT: {impact}")
                print(f"   📝 EXPLANATION: {claim['explanation']}")
                print(f"   📍 SOURCE: Post {claim['post_number']}")
        else:
            print("\nNo claims require external verification at this time.")
            
        print("\n" + "=" * 70)
        print("HISTORICAL CLAIMS VERIFIED USING MODEL KNOWLEDGE")
        print("=" * 70)
        
        historical_claims = [claim for claim in all_claims if claim.get('is_historical_claim')]
        
        if historical_claims:
            for i, claim in enumerate(historical_claims, 1):
                status = claim.get('verification_status', 'unverified')
                confidence = claim.get('confidence', 'medium')
                evidence = claim.get('historical_evidence', '')
                
                status_emoji = {
                    'verified_true': '✅',
                    'verified_false': '❌', 
                    'unverified': '❓',
                    'requires_external_verification': '🔍'
                }.get(status, '❓')
                
                print(f"\n{i}. {status_emoji} HISTORICAL CLAIM")
                print(f"   📢 CLAIM: {claim['claim']}")
                print(f"   📊 STATUS: {status} | CONFIDENCE: {confidence}")
                print(f"   📚 EVIDENCE: {evidence}")
                print(f"   📍 SOURCE: Post {claim['post_number']}")
        else:
            print("\nNo historical claims were detected.")
    else:
        print("\n❌ No claims requiring verification found.")
        print("This could mean:")
        print("- Content is factual and well-supported")
        print("- Content is too vague for verification")
        print("- No significant claims detected")

if __name__ == "__main__":
    main()
