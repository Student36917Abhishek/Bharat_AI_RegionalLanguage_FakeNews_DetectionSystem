import json
import re
import requests
from typing import List, Dict, Any, Optional
import gc

# News API configurations
GNEWS_API_KEY = "27e168eef0cf8765a7b0c552eacd30e3"
NEWSAPI_KEY = "36966074260a46599ef9d53e6c05c328"

GNEWS_BASE_URL = "https://gnews.io/api/v4"
NEWSAPI_BASE_URL = "https://newsapi.org/v2"

# Local model path for DeepSeek
LOCAL_MODEL_PATH = "./DeepSeek-R1-Distill-Qwen-1.5B.Q4_K_M.gguf"

# Token limits
MAX_INPUT_TOKENS = 8000
MAX_OUTPUT_TOKENS = 1000

# API call limits
MAX_API_CALLS = 5
api_call_count = 0

# Track which APIs are still available
gnews_available = True
newsapi_available = True

# Global variable for LLM
llm = None

# Improved System Prompt
IMPROVED_SYSTEM_PROMPT = """
You are a claim severity analyzer. Analyze claims and determine if they need external verification.

CATEGORY GUIDELINES:
- HEALTH: Medical treatments, diseases, vaccines, drugs, health risks
- POLITICS: Government actions, elections, policies, political figures
- SCIENCE: Scientific discoveries, research, technology
- FINANCE: Economic data, stocks, markets, financial claims
- SAFETY: Accidents, disasters, security risks, public safety
- MILITARY: Defense, military operations, weapons, national security
- OTHER: Everything else

SEVERITY GUIDELINES:
- CRITICAL: Immediate public safety risk, national security, life-threatening health claims
- HIGH: Political corruption, financial fraud, major health misinformation
- MEDIUM: Significant but not urgent claims, policy decisions
- LOW: Minor claims, personal opinions, general information

VERIFICATION RULES:
- NEEDS VERIFICATION: Claims about current events, public figures, health risks, financial data, safety issues
- NO VERIFICATION: Personal stories, opinions, general knowledge, historical facts

EXAMPLES:
- "Vaccines cause autism" → health, critical, needs verification
- "Plane crashed at 2:10 pm" → safety, medium, needs verification  
- "Stock market will crash" → finance, high, needs verification
- "I feel tired today" → other, low, no verification

Respond in JSON format only.
"""

def cleanup_resources():
    """Aggressively free resources"""
    global llm
    if llm is not None:
        del llm
        llm = None
    gc.collect()
    print("Resources cleaned up successfully")

def initialize_deepseek_model():
    """Initialize the DeepSeek model"""
    global llm
    try:
        from llama_cpp import Llama
        print(f"Loading DeepSeek model from: {LOCAL_MODEL_PATH}")
        
        # Clean up any existing model first
        cleanup_resources()
        
        llm = Llama(
            model_path=LOCAL_MODEL_PATH,
            n_ctx=MAX_INPUT_TOKENS + MAX_OUTPUT_TOKENS,
            n_gpu_layers=-1,
            verbose=False
        )
        print("DeepSeek model loaded successfully.\n")
        return llm
    except Exception as e:
        print(f"ERROR initializing DeepSeek model: {e}")
        return None

def truncate_text_for_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to fit within token limits (rough estimation)"""
    # Rough estimation: 1 token ≈ 4 characters for English text
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(' ', 1)[0] + "..."

def truncate_articles_data(articles: List[Dict[str, str]], max_tokens: int = 6000) -> str:
    """Truncate articles data to fit within token limits"""
    articles_text = ""
    for i, article in enumerate(articles):
        article_content = f"Article {i+1}:\nTitle: {article.get('title', '')}\nDescription: {article.get('description', '')}\nContent: {article.get('content', '')}\nSource: {article.get('source', '')}\nPublished: {article.get('publishedAt', '')}\n\n"
        
        # Check if adding this article would exceed token limit
        if len(articles_text + article_content) > (max_tokens * 4):
            break
        articles_text += article_content
    
    return articles_text

def validate_analysis(analysis: Dict[str, Any], claim: str) -> Dict[str, Any]:
    """Validate and correct analysis results"""
    
    # Auto-correct obvious category errors
    claim_lower = claim.lower()
    
    # Category correction rules
    if 'plane' in claim_lower or 'crash' in claim_lower or 'air' in claim_lower:
        analysis['category'] = 'safety'
    elif 'military' in claim_lower or 'air force' in claim_lower or 'fighter' in claim_lower or 'squadron' in claim_lower:
        analysis['category'] = 'military' 
    elif 'vaccine' in claim_lower or 'drug' in claim_lower or 'cancer' in claim_lower:
        analysis['category'] = 'health'
    elif 'government' in claim_lower or 'modi' in claim_lower or 'political' in claim_lower:
        analysis['category'] = 'politics'
    elif 'stock' in claim_lower or 'market' in claim_lower or 'financial' in claim_lower:
        analysis['category'] = 'finance'
    
    # Severity correction
    if analysis.get('severity') == 'critical':
        # Only truly critical claims should be critical
        critical_indicators = ['death', 'kill', 'terror', 'emergency', 'pandemic', 'collapse']
        if not any(indicator in claim_lower for indicator in critical_indicators):
            analysis['severity'] = 'high'
    
    # Search query improvement
    search_query = analysis.get('search_query', '')
    if '?' in search_query or len(search_query.split()) > 8:
        # Create better search query from claim keywords
        words = re.findall(r'\b\w+\b', claim_lower)
        keywords = [w for w in words if len(w) > 3 and w not in ['this', 'that', 'the', 'and', 'for']]
        analysis['search_query'] = ' '.join(keywords[:5])
    
    return analysis

def create_safe_default_analysis(claim: str) -> Dict[str, Any]:
    """Create conservative default analysis"""
    claim_lower = claim.lower()
    
    # Default category detection
    category = "other"
    if any(word in claim_lower for word in ['vaccine', 'drug', 'health', 'cancer']):
        category = "health"
    elif any(word in claim_lower for word in ['government', 'political', 'election']):
        category = "politics" 
    elif any(word in claim_lower for word in ['crash', 'accident', 'safety']):
        category = "safety"
    elif any(word in claim_lower for word in ['military', 'air force', 'defense']):
        category = "military"
    
    return {
        "needs_verification": "no",  # Conservative default
        "severity": "low",
        "search_query": ' '.join(re.findall(r'\b\w+\b', claim_lower)[:4]),
        "category": category,
        "reasoning": "Conservative analysis applied"
    }

def analyze_claim_severity(claim_data: Dict[str, str]) -> Dict[str, Any]:
    """
    Improved claim analysis with better categorization
    """
    claim = claim_data.get("claim", "")
    evidence = claim_data.get("evidence", "")
    logic = claim_data.get("logic", "")
    
    # Truncate inputs
    claim_truncated = truncate_text_for_tokens(claim, 300)
    evidence_truncated = truncate_text_for_tokens(evidence, 400)
    logic_truncated = truncate_text_for_tokens(logic, 300)
    
    prompt = f"""
{IMPROVED_SYSTEM_PROMPT}

CLAIM TO ANALYZE:
Claim: {claim_truncated}
Evidence: {evidence_truncated} 
Logic: {logic_truncated}

ANALYSIS OUTPUT (JSON):
{{
    "needs_verification": "yes/no",
    "severity": "low/medium/high/critical",
    "search_query": "concise 5-7 word search phrase",
    "category": "health/politics/science/finance/safety/military/other",
    "reasoning": "clear explanation based on guidelines"
}}
"""
    
    try:
        response = llm(
            prompt,
            max_tokens=500,
            temperature=0.1,  # Slight temperature for better reasoning
            echo=False
        )
        
        if isinstance(response, dict) and 'choices' in response:
            content = response['choices'][0]['text']
        else:
            content = str(response)
        
        # Extract JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group())
            
            # Validate and fix categories
            analysis = validate_analysis(analysis, claim_truncated)
            return analysis
            
    except Exception as e:
        print(f"  Analysis error: {e}")
    
    return create_safe_default_analysis(claim_truncated)

def can_make_api_call() -> bool:
    """Check if we can make another API call"""
    global api_call_count
    return api_call_count < MAX_API_CALLS

def increment_api_call():
    """Increment API call counter"""
    global api_call_count
    api_call_count += 1

def get_available_api() -> str:
    """Get which API is available to use"""
    global gnews_available, newsapi_available
    
    if gnews_available:
        return "gnews"
    elif newsapi_available:
        return "newsapi"
    else:
        return "none"

def mark_api_unavailable(api_name: str):
    """Mark an API as unavailable"""
    global gnews_available, newsapi_available
    
    if api_name == "gnews":
        gnews_available = False
        print("  GNews API marked as unavailable")
    elif api_name == "newsapi":
        newsapi_available = False
        print("  NewsAPI marked as unavailable")

def search_single_api(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """
    Search using only one available API (not both)
    Returns articles and the API used
    """
    if not can_make_api_call():
        print("  API call limit reached, skipping search")
        return [], "none"
        
    available_api = get_available_api()
    
    if available_api == "none":
        print("  No APIs available for search")
        return [], "none"
    
    try:
        increment_api_call()
        print(f"  Making {available_api.upper()} API call ({api_call_count}/{MAX_API_CALLS})")
        
        if available_api == "gnews":
            params = {
                'q': query,
                'token': GNEWS_API_KEY,
                'lang': 'en',
                'max': max_results
            }
            
            response = requests.get(f"{GNEWS_BASE_URL}/search", params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = []
                for article in data.get('articles', []):
                    articles.append({
                        'title': article.get('title', ''),
                        'description': article.get('description', ''),
                        'content': article.get('content', ''),
                        'url': article.get('url', ''),
                        'publishedAt': article.get('publishedAt', ''),
                        'source': article.get('source', {}).get('name', ''),
                        'api_used': 'gnews'
                    })
                return articles, "gnews"
            else:
                print(f"  GNews API error: {response.status_code}")
                if response.status_code in [429, 403]:  # Rate limit or forbidden
                    mark_api_unavailable("gnews")
                    # Try the other API immediately if available
                    if newsapi_available and can_make_api_call():
                        print("  Switching to NewsAPI...")
                        return search_single_api(query, max_results)
                return [], "gnews"
                
        elif available_api == "newsapi":
            params = {
                'q': query,
                'apiKey': NEWSAPI_KEY,
                'pageSize': max_results,
                'sortBy': 'relevancy'
            }
            
            response = requests.get(f"{NEWSAPI_BASE_URL}/everything", params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = []
                for article in data.get('articles', []):
                    articles.append({
                        'title': article.get('title', ''),
                        'description': article.get('description', ''),
                        'content': article.get('content', ''),
                        'url': article.get('url', ''),
                        'publishedAt': article.get('publishedAt', ''),
                        'source': article.get('source', {}).get('name', ''),
                        'api_used': 'newsapi'
                    })
                return articles, "newsapi"
            else:
                print(f"  NewsAPI error: {response.status_code}")
                if response.status_code in [429, 403]:  # Rate limit or forbidden
                    mark_api_unavailable("newsapi")
                    # Try the other API immediately if available
                    if gnews_available and can_make_api_call():
                        print("  Switching to GNews...")
                        return search_single_api(query, max_results)
                return [], "newsapi"
                
    except Exception as e:
        print(f"  {available_api.upper()} API call failed: {e}")
        mark_api_unavailable(available_api)
        # Try the other API if available
        other_api = "newsapi" if available_api == "gnews" else "gnews"
        if ((other_api == "gnews" and gnews_available) or 
            (other_api == "newsapi" and newsapi_available)) and can_make_api_call():
            print(f"  Switching to {other_api.upper()}...")
            return search_single_api(query, max_results)
        return [], available_api
    
    return [], "none"

def verify_claim_with_llm(claim: str, evidence: str, logic: str, external_articles: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Use LLM to verify claim by comparing with external articles data
    """
    print("  Using LLM for detailed verification...")
    
    # Truncate articles data to fit token limits
    articles_text = truncate_articles_data(external_articles, 6000)
    
    # Truncate original claim data
    claim_truncated = truncate_text_for_tokens(claim, 500)
    evidence_truncated = truncate_text_for_tokens(evidence, 500)
    logic_truncated = truncate_text_for_tokens(logic, 500)
    
    prompt = f"""
    VERIFICATION TASK:
    Compare the original claim with external news articles and determine if the claim is verified.
    
    ORIGINAL CLAIM DATA:
    Claim: {claim_truncated}
    Evidence: {evidence_truncated}
    Logic: {logic_truncated}
    
    EXTERNAL NEWS ARTICLES:
    {articles_text}
    
    ANALYSIS INSTRUCTIONS:
    1. Compare the original claim with information from external articles
    2. Determine if the claim is supported, contradicted, or unverified
    3. Consider the credibility of sources and recency of information
    4. Provide detailed explanation for your decision
    
    RESPONSE FORMAT (JSON):
    {{
        "claim_name": "brief summary of claim",
        "verification_label": "verified/partially_verified/unverified/contradicted",
        "confidence_level": "high/medium/low",
        "explanation": "detailed explanation comparing claim with external evidence",
        "key_findings": ["list of key points from comparison"],
        "sources_used": ["list of sources referenced"],
        "final_verdict": "clear statement of verification result"
    }}
    
    IMPORTANT: Base your analysis ONLY on the provided external articles and original claim data.
    """
    
    try:
        response = llm(
            prompt,
            max_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.0,
            echo=False
        )
        
        if isinstance(response, dict) and 'choices' in response:
            content = response['choices'][0]['text']
        else:
            content = str(response)
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            verification_result = json.loads(json_match.group())
            
            # Validate required fields
            required_fields = ['claim_name', 'verification_label', 'confidence_level', 'explanation']
            if not all(field in verification_result for field in required_fields):
                verification_result = create_default_verification(claim_truncated)
                
            return verification_result
        else:
            print("  No JSON found in LLM verification response")
            return create_default_verification(claim_truncated)
            
    except Exception as e:
        print(f"  Error in LLM verification: {e}")
        return create_default_verification(claim_truncated)

def create_default_verification(claim: str) -> Dict[str, Any]:
    """Create default verification when LLM fails"""
    return {
        "claim_name": claim[:100],
        "verification_label": "unverified",
        "confidence_level": "low",
        "explanation": "Verification failed due to processing error",
        "key_findings": ["Unable to process verification request"],
        "sources_used": [],
        "final_verdict": "Claim could not be verified due to technical issues"
    }

def print_verification_result(verification_result: Dict[str, Any]):
    """Print verification result in structured format"""
    print("\n" + "=" * 80)
    print("🔄 CLAIM VERIFICATION RESULT")
    print("=" * 80)
    print(f"📋 CLAIM NAME: {verification_result.get('claim_name', 'N/A')}")
    print(f"🏷️  VERIFICATION LABEL: {verification_result.get('verification_label', 'N/A')}")
    print(f"🎯 CONFIDENCE LEVEL: {verification_result.get('confidence_level', 'N/A')}")
    print(f"📝 EXPLANATION: {verification_result.get('explanation', 'N/A')}")
    
    key_findings = verification_result.get('key_findings', [])
    if key_findings:
        print("🔍 KEY FINDINGS:")
        for finding in key_findings[:5]:  # Show max 5 key findings
            print(f"   • {finding}")
    
    sources = verification_result.get('sources_used', [])
    if sources:
        print("📰 SOURCES USED:")
        for source in sources[:3]:  # Show max 3 sources
            print(f"   • {source}")
    
    print(f"✅ FINAL VERDICT: {verification_result.get('final_verdict', 'N/A')}")
    print("=" * 80)

def verify_claim_with_news(claim: str, evidence: str, logic: str, search_query: str) -> Dict[str, Any]:
    """
    Verify claim using only one news API and LLM analysis
    """
    print(f"  Verifying claim: {claim[:80]}...")
    
    # Check if we can make API calls
    if not can_make_api_call():
        return {
            "verified": False,
            "confidence": "low",
            "verification_reason": "API call limit reached",
            "articles_count": 0,
            "api_calls_used": api_call_count,
            "api_used": "none",
            "llm_verification": None
        }
    
    # Search using only one API
    articles, api_used = search_single_api(search_query)
    
    if not articles:
        return {
            "verified": False,
            "confidence": "low",
            "verification_reason": f"No relevant news articles found from {api_used}",
            "articles_count": 0,
            "api_calls_used": api_call_count,
            "api_used": api_used,
            "llm_verification": None
        }
    
    print(f"  Found {len(articles)} articles, using LLM for verification...")
    
    # Use LLM for detailed verification
    llm_verification = verify_claim_with_llm(claim, evidence, logic, articles)
    
    # Print the verification result
    print_verification_result(llm_verification)
    
    # Determine overall verification status
    verification_label = llm_verification.get('verification_label', 'unverified')
    is_verified = verification_label in ['verified', 'partially_verified']
    confidence = llm_verification.get('confidence_level', 'low')
    
    return {
        "verified": is_verified,
        "confidence": confidence,
        "verification_reason": f"LLM analysis: {verification_label}",
        "articles_count": len(articles),
        "api_calls_used": api_call_count,
        "api_used": api_used,
        "llm_verification": llm_verification
    }

def process_claims_with_verification():
    """Main function to process claims with verification"""
    global api_call_count, gnews_available, newsapi_available
    
    # Reset counters
    api_call_count = 0
    gnews_available = True
    newsapi_available = True
    
    print("=" * 60)
    print("CLAIM VERIFICATION SYSTEM")
    print("=" * 60)
    print(f"Input tokens: {MAX_INPUT_TOKENS}, Output tokens: {MAX_OUTPUT_TOKENS}")
    print(f"Max API calls: {MAX_API_CALLS}")
    print(f"Strategy: Single API call + LLM verification")
    print()
    
    # Load existing claims
    try:
        with open("./claims_extracted.json", 'r', encoding='utf-8') as f:
            claims_data = json.load(f)
        print(f"Loaded {len(claims_data)} claims from ./claims_extracted.json\n")
    except Exception as e:
        print(f"ERROR loading claims data: {e}")
        return
    
    # Initialize DeepSeek model
    if not initialize_deepseek_model():
        return
    
    verified_claims = []
    high_severity_count = 0
    verified_count = 0
    api_blocked = False
    
    # Process each claim
    for i, claim_data in enumerate(claims_data):
        if api_call_count >= MAX_API_CALLS:
            api_blocked = True
            print("API call limit reached. Stopping external verification.")
            # Add remaining claims without verification
            for remaining_claim in claims_data[i:]:
                remaining_claim['analysis'] = {
                    "needs_verification": "no",
                    "severity": "low", 
                    "search_query": "",
                    "category": "other",
                    "reasoning": "API limit reached, verification skipped"
                }
                remaining_claim['verification'] = {
                    "verified": False,
                    "confidence": "low",
                    "verification_reason": "API call limit reached",
                    "api_calls_used": api_call_count,
                    "api_used": "none",
                    "llm_verification": None
                }
                verified_claims.append(remaining_claim)
            break
        
        print(f"Processing claim {i+1}/{len(claims_data)}...")
        
        # Analyze claim severity and needs
        analysis = analyze_claim_severity(claim_data)
        
        claim_data['analysis'] = analysis
        
        # Only verify if: needs_verification=YES AND severity=HIGH/CRITICAL AND API calls available
        if (analysis.get('needs_verification') == 'yes' and 
            analysis.get('severity') in ['high', 'critical'] and
            can_make_api_call()):
            
            high_severity_count += 1
            print(f"  High severity claim detected: {analysis.get('category')}")
            print(f"  Search query: {analysis.get('search_query')}")
            
            # Verify with only one news API + LLM analysis
            verification_result = verify_claim_with_news(
                claim_data['claim'],
                claim_data['evidence'],
                claim_data['logic'],
                analysis.get('search_query', claim_data['claim'][:80])
            )
            
            claim_data['verification'] = verification_result
            
            if verification_result['verified']:
                verified_count += 1
                print(f"  ✓ Claim verified with {verification_result['confidence']} confidence")
            else:
                print(f"  ✗ Claim not verified")
        else:
            # Mark as not requiring verification or low severity
            claim_data['verification'] = {
                "verified": False,
                "confidence": "low",
                "verification_reason": f"Does not require external verification (severity: {analysis.get('severity')})",
                "api_calls_used": api_call_count,
                "api_used": "none",
                "llm_verification": None
            }
            print(f"  Skipped verification (severity: {analysis.get('severity')})")
        
        verified_claims.append(claim_data)
        print()
    
    # Save verified claims
    try:
        output_file = "./verified_claims.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(verified_claims, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(verified_claims)} claims to {output_file}")
    except Exception as e:
        print(f"ERROR saving verified claims: {e}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"Total claims processed: {len(claims_data)}")
    print(f"High severity claims: {high_severity_count}")
    print(f"Claims verified: {verified_count}")
    print(f"API calls made: {api_call_count}/{MAX_API_CALLS}")
    print(f"GNews available: {gnews_available}")
    print(f"NewsAPI available: {newsapi_available}")
    if api_blocked:
        print(f"API LIMIT REACHED: Verification stopped early")
    
    # Cleanup resources
    cleanup_resources()

if __name__ == "__main__":
    process_claims_with_verification()
