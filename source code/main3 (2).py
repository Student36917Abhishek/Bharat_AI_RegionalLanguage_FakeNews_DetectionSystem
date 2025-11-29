import json
import time
import re
import os
from typing import List, Dict, Any

# Configuration
GEMINI_API_KEY = "AIzaSyCsNPhjSCU4A09LyMK71tQGODk9uO9kQv4"
DATA_FILE_PATH = "translated_reddit_data.json"
OUTPUT_JSON = "verified_claims.json"
MAX_POSTS_TO_PROCESS = 5
MAX_CHARS_PER_REQUEST = 2000
REQUEST_DELAY = 1
MAX_CLAIMS_PER_POST = 2

# Enhanced prompt for BETTER claim extraction with STRICTER filtering
MISINFO_PROMPT = """Analyze this text and identify ONLY claims that could be actual misinformation, false rumors, or unverified assertions that need fact-checking.

CRITICAL: Focus on claims that are:
1. Factual assertions that can be objectively verified
2. Potentially false or misleading information
3. Rumors circulating without evidence
4. Controversial statements that contradict established facts

STRICTLY REJECT and DO NOT EXTRACT:
- Personal opinions, subjective statements, or value judgments
- General discussions without specific claims
- Obvious jokes or sarcasm (unless they're being presented seriously)
- Routine statements that don't need verification
- Statements that are clearly labeled as hypothetical
- Advice, recommendations, or suggestions
- Personal experiences or anecdotes
- Policy critiques or political opinions without factual inaccuracies
- Business viability assessments or market opinions

GOOD CLAIM EXAMPLES (actual misinformation):
- "Charlie Kirk was assassinated last month" (verifiably false)
- "Vaccines contain microchips for tracking" (common misinformation)
- "The election was stolen through massive fraud" (unverified conspiracy)
- "This chemical in food causes immediate cancer" (exaggerated health claim)

BAD CLAIM EXAMPLES (STRICTLY REJECT these):
- "I think the policy is bad" (opinion)
- "This advice is ineffective" (subjective assessment)
- "The Indian defense sector doesn't need private help" (policy opinion)
- "This business model is not viable" (business opinion)
- "People are discussing the event" (general statement)
- "The weather might be nice tomorrow" (speculation)

For each genuine misinformation claim, provide:
[
  {
    "claim": "CLEAR, SPECIFIC factual statement that can be verified",
    "category": "health/politics/finance/rumor/conspiracy/etc",
    "verification_status": "verified_true/verified_false/unverified/requires_external_verification",
    "confidence": "high/medium/low",
    "explanation": "why this specific claim needs verification and why it might be misinformation",
    "fact_check_notes": "what evidence would be needed to verify this",
    "potential_impact": "low/medium/high",
    "search_query": "concise search query for fact-checking this claim",
    "needs_external_verification": true/false
  }
]

Return maximum 2 most significant MISINFORMATION claims. If no clear misinformation claims found, return: []

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
    # Remove trailing fragments and normalize
    claim = claim.strip()
    
    # Remove trailing incomplete sentences
    if claim.endswith(('.', '!', '?')):
        # Good - ends with proper punctuation
        pass
    else:
        # Try to find a natural break point
        last_period = claim.rfind('.')
        last_exclamation = claim.rfind('!')
        last_question = claim.rfind('?')
        
        end_pos = max(last_period, last_exclamation, last_question)
        if end_pos > len(claim) * 0.5:  # If we have a reasonable break point
            claim = claim[:end_pos + 1]
    
    # Remove ALL CAPS and normalize case
    if claim.isupper():
        claim = claim.capitalize()
    else:
        # Capitalize first letter
        claim = claim[0].upper() + claim[1:] if claim else claim
    
    # Remove excessive punctuation
    claim = re.sub(r'!{2,}', '!', claim)
    
    return claim

def is_quality_claim(claim_data: Dict[str, Any]) -> bool:
    """STRICTER check if this is a quality misinformation claim worth keeping."""
    claim = claim_data.get('claim', '').lower()
    explanation = claim_data.get('explanation', '').lower()
    
    # Skip if claim is too short
    if len(claim) < 15:
        return False
    
    # Skip if explanation is too brief
    if len(explanation) < 40:
        return False
    
    # STRONGER opinion filtering
    opinion_indicators = [
        'i think', 'i believe', 'in my opinion', 'personally', 
        'should', 'ought to', 'would be better', 'is better', 'is worse',
        'advice', 'recommend', 'suggest', 'tip', 'should do',
        'is good', 'is bad', 'is effective', 'is ineffective',
        'is viable', 'is not viable', 'waste of time', 'useless',
        'need help', 'does not need help', 'solve problems'
    ]
    if any(indicator in claim for indicator in opinion_indicators):
        return False
    
    # Skip advice/effectiveness claims (like claim #2)
    advice_patterns = [
        r'\badvice\b.*\b(false|ineffective|wrong|bad)\b',
        r'\btip\b.*\b(false|ineffective|wrong|bad)\b',
        r'\bsuggestion\b.*\b(false|ineffective|wrong|bad)\b',
        r'\bresponse\b.*\b(false|ineffective|wrong|bad)\b',
        r'\bhow to\b.*\b(false|ineffective|wrong|bad)\b'
    ]
    if any(re.search(pattern, claim, re.IGNORECASE) for pattern in advice_patterns):
        return False
    
    # Skip business viability claims (like claim #5)
    business_viability_patterns = [
        r'\b(not |un)viable\b',
        r'\bwaste of time\b',
        r'\bnot worth\b',
        r'\bdoes not need\b',
        r'\bsolve.*on its own\b',
        r'\bprivate sector.*not viable\b'
    ]
    if any(re.search(pattern, claim, re.IGNORECASE) for pattern in business_viability_patterns):
        return False
    
    # Skip vague claims
    vague_indicators = [
        'something', 'someone', 'things', 'stuff', 'people say',
        'rumors', 'allegedly', 'supposedly', 'some people',
        'many believe', 'it is said'
    ]
    vague_count = sum(1 for indicator in vague_indicators if indicator in claim)
    if vague_count > 1:
        return False
    
    # Skip claims that are too general or lack specific factual content
    general_indicators = [
        'everything', 'everyone', 'nothing', 'no one', 'always', 'never'
    ]
    if any(indicator in claim for indicator in general_indicators):
        # But allow if it's part of a specific factual claim
        specific_indicators = ['assassinated', 'died', 'killed', 'attack', 'launched', 'retaliating']
        if not any(specific in claim for specific in specific_indicators):
            return False
    
    # Ensure the claim contains verifiable factual content
    factual_indicators = [
        'was', 'were', 'is', 'are', 'did', 'does', 'has', 'have',
        'occurred', 'happened', 'took place', 'launched', 'attacked',
        'died', 'killed', 'assassinated', 'admitted', 'kept'
    ]
    if not any(indicator in claim for indicator in factual_indicators):
        return False
    
    return True

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
    
    # Extract JSON
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
            is_quality_claim(item)):
            
            # Clean and improve the claim text
            original_claim = str(item['claim'])
            cleaned_claim = clean_claim_text(original_claim)
            
            # Enhanced claim object with search query
            enhanced_claim = {
                'claim': cleaned_claim,
                'original_claim': original_claim,  # Keep original for reference
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
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Generate search query if not provided
            if not enhanced_claim['search_query']:
                enhanced_claim['search_query'] = generate_search_query(enhanced_claim['claim'])
            
            # Auto-mark for external verification based on status
            if enhanced_claim['verification_status'] in ['requires_external_verification', 'unverified']:
                enhanced_claim['needs_external_verification'] = True
            
            quality_claims.append(enhanced_claim)
        
        if len(quality_claims) >= MAX_CLAIMS_PER_POST:
            break
    
    return quality_claims

def generate_search_query(claim: str) -> str:
    """Generate a search query for fact-checking."""
    # Remove common phrases and clean the claim
    claim_clean = re.sub(r'\b(claims?|said|stated|alleged|reported)\b', '', claim, flags=re.IGNORECASE)
    claim_clean = re.sub(r'[^\w\s]', ' ', claim_clean)
    
    # Extract key words (nouns and important verbs)
    words = [word for word in claim_clean.split() if len(word) > 3]
    
    # Take most relevant words (limit to 5-6 words)
    key_words = words[:6]
    
    # Create search query
    search_query = " ".join(key_words)
    
    # Add fact-check context for better results
    if len(search_query.split()) >= 3:
        search_query += " fact check verification"
    else:
        search_query += " news report investigation"
    
    return search_query

def main():
    """Main function for misinformation detection with STRICTER filtering."""
    print("=" * 70)
    print("IMPROVED MISINFORMATION DETECTION - STRICTER CLAIM FILTERING")
    print(f"Max claims per post: {MAX_CLAIMS_PER_POST}")
    print(f"Output file: {OUTPUT_JSON}")
    print("=" * 70)
    
    model = initialize_gemini()
    if not model:
        return
    
    # Load data
    try:
        with open(DATA_FILE_PATH, 'r') as f:
            posts_data = json.load(f)[:MAX_POSTS_TO_PROCESS]
        print(f"Loaded {len(posts_data)} posts\n")
    except Exception as e:
        print(f"Data load error: {e}")
        return
    
    all_claims = []
    
    for i, post in enumerate(posts_data):
        text = post.get('original_text', '')
        url = post.get('url', '')
        
        if not text:
            continue
            
        print(f"Post {i+1}: ", end="")
        
        if i > 0:
            time.sleep(REQUEST_DELAY)
        
        claims = extract_misinfo_claims(model, text)
        
        for claim in claims:
            claim['source_url'] = url
            claim['post_number'] = i + 1
            all_claims.append(claim)
        
        print(f"→ {len(claims)} claims")
    
    # Save results with file path info
    if all_claims:
        output_path = os.path.abspath(OUTPUT_JSON)
        with open(OUTPUT_JSON, 'w') as f:
            json.dump(all_claims, f, indent=2)
        print(f"\n✅ Saved {len(all_claims)} claims to: {output_path}")
        
        # Show file location info
        current_dir = os.getcwd()
        print(f"📁 Current directory: {current_dir}")
        print(f"💾 File location: {output_path}")
        
        # Calculate statistics
        external_verification_count = sum(1 for claim in all_claims if claim.get('needs_external_verification'))
        verified_true_count = sum(1 for claim in all_claims if claim.get('verification_status') == 'verified_true')
        verified_false_count = sum(1 for claim in all_claims if claim.get('verification_status') == 'verified_false')
        unverified_count = sum(1 for claim in all_claims if claim.get('verification_status') in ['unverified', 'requires_external_verification'])
        
        print("\n" + "=" * 70)
        print("CLAIMS SUMMARY")
        print("=" * 70)
        print(f"📊 TOTAL CLAIMS: {len(all_claims)}")
        print(f"🔍 NEED EXTERNAL VERIFICATION: {external_verification_count}")
        print(f"✅ VERIFIED TRUE: {verified_true_count}")
        print(f"❌ VERIFIED FALSE: {verified_false_count}")
        print(f"❓ UNVERIFIED/REQUIRES RESEARCH: {unverified_count}")
        
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
        print("ALL CLAIMS CATEGORIES")
        print("=" * 70)
        
        # Categorize claims
        categories = {}
        for claim in all_claims:
            cat = claim.get('category', 'unknown')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(claim)
        
        for category, claims_in_cat in categories.items():
            ext_count = sum(1 for c in claims_in_cat if c.get('needs_external_verification'))
            print(f"\n📁 {category.upper()} ({len(claims_in_cat)} claims, {ext_count} need external verification)")
            
            # Show first claim from each category as example
            if claims_in_cat:
                sample_claim = claims_in_cat[0]
                print(f"   Sample: {sample_claim['claim'][:80]}...")
    
    else:
        print("\n❌ No claims requiring verification found.")
        print("This could mean:")
        print("- Content is factual and well-supported")
        print("- Content is too vague for verification")
        print("- No significant claims detected")

if __name__ == "__main__":
    main()
