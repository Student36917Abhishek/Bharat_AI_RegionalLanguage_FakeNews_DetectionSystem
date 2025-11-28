import asyncio
import json
import re
import logging
from playwright.async_api import async_playwright
import time
from urllib.parse import urlparse, quote
import os
from datetime import datetime
import random
from bs4 import BeautifulSoup
import hashlib
import requests.utils
import traceback
from typing import List, Dict, Optional, Tuple, Any
import platform
import subprocess
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enhanced_search_scraper.log'),
        logging.StreamHandler()
    ]
)

class FreeProxyRotator:
    """Enhanced proxy rotation with better error handling and more sources"""
    
    def __init__(self):
        self.proxies = []
        self.current_index = 0
        self.failed_proxies = set()
        self.proxy_sources = [
            "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"
        ]
        
    async def refresh_proxy_list(self):
        """Refresh proxy list from multiple free sources"""
        try:
            new_proxies = []
            
            # Try to fetch from online sources
            for source_url in self.proxy_sources:
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(source_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                            if response.status == 200:
                                text = await response.text()
                                # Extract proxies from text (format: IP:PORT)
                                for line in text.split('\n'):
                                    if ':' in line and not line.startswith('#'):
                                        parts = line.strip().split(':')
                                        if len(parts) >= 2:
                                            ip, port = parts[0], parts[1]
                                            # Basic validation
                                            if self._validate_ip(ip) and port.isdigit():
                                                new_proxies.append(f"{ip}:{port}")
                except Exception as e:
                    logging.warning(f"Failed to fetch proxies from {source_url}: {str(e)}")
                    continue
            
            # If no proxies from online sources, use some static ones
            if not new_proxies:
                new_proxies = [
                    "103.149.162.194:80",
                    "103.149.162.195:80",
                    "103.149.162.196:80",
                    "103.149.162.197:80",
                    "103.149.162.198:80",
                    "139.59.1.14:3128",
                    "139.59.1.15:3128",
                    "139.59.1.16:3128",
                    "139.59.1.17:3128",
                    "45.67.14.205:3128",
                    "45.67.14.206:3128",
                    "45.67.14.207:3128",
                    "45.67.14.208:3128",
                ]
            
            # Filter out previously failed proxies
            self.proxies = [p for p in new_proxies if p not in self.failed_proxies]
            self.current_index = 0
            logging.info(f"Refreshed proxy list with {len(self.proxies)} proxies")
        except Exception as e:
            logging.error(f"Failed to refresh proxy list: {str(e)}")
            self.proxies = []
    
    def _validate_ip(self, ip):
        """Basic IP validation"""
        try:
            parts = ip.split('.')
            return len(parts) == 4 and all(0 <= int(part) <= 255 for part in parts)
        except:
            return False
    
    def get_next_proxy(self):
        """Get next proxy from the list"""
        if not self.proxies:
            return None
            
        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        return proxy
    
    def mark_proxy_failed(self, proxy):
        """Mark a proxy as failed"""
        self.failed_proxies.add(proxy)
        if proxy in self.proxies:
            self.proxies.remove(proxy)
        logging.warning(f"Marked proxy as failed: {proxy}")
    
    async def test_proxy(self, proxy):
        """Test if a proxy is working"""
        try:
            import aiohttp
            proxy_url = f"http://{proxy}"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "http://httpbin.org/ip",
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return True, data.get("origin", "")
            return False, ""
        except Exception as e:
            logging.debug(f"Proxy test failed for {proxy}: {str(e)}")
            return False, ""

class EnhancedSearchScraper:
    def __init__(self):
        self.search_results = {}
        self.visited_links = []
        
        # Detect OS for appropriate user agents
        self.is_kali = self.detect_kali()
        
        # User agents that look like regular Ubuntu users (even on Kali)
        self.user_agents = [
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0'
        ]
        
        # Enhanced browser arguments for stealth mode
        # NOTE: '--user-data-dir' and '--disk-cache-dir' are removed from here
        # They will be passed as parameters to new_context()
        self.browser_args = [
            '--no-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--disable-features=VizDisplayCompositor',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-ipc-flooding-protection',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-default-apps',
            '--disable-translate',
            '--disable-extensions',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--disable-software-rasterizer',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
            '--password-store=basic',
            '--use-mock-keychain',
            '--force-color-profile=srgb',
            '--metrics-recording-only',
            '--disable-default-apps',
            '--no-report-upload',
            '--disable-domain-reliability'
        ]
        
        # Additional arguments for Kali Linux
        if self.is_kali:
            self.browser_args.extend([
                '--disable-extensions-except',
                '--disable-plugins-discovery',
                '--disable-bundled-ppapi-flash',
                '--disable-logging',
                '--silent-debugger-extension-api',
                '--no-wifi',
                '--disable-notifications',
                '--disable-push-messaging',
                '--disable-sync',
                '--disable-background-networking',
                '--disable-client-side-phishing-detection',
                '--disable-component-extensions-with-background-pages',
                '--disable-hang-monitor',
                '--disable-popup-blocking',
                '--disable-prompt-on-repost',
                '--safebrowsing-disable-auto-update',
                '--enable-automation',
            ])
        
        # Initialize proxy rotator
        self.proxy_rotator = FreeProxyRotator()
        
        # Search engines to try in order
        self.search_engines = [
            {
                "name": "Bing", 
                "url": "https://www.bing.com", 
                "search_path": "/search?q=",
                "direct_search_url": "https://www.bing.com/search?q={query}"
            },
            {
                "name": "StartPage", 
                "url": "https://www.startpage.com", 
                "search_path": "/do/search?query=",
                "direct_search_url": "https://www.startpage.com/do/search?query={query}"
            }
        ]
        
        # Track which search engines are blocked
        self.blocked_engines = set()
        
        # Minimum number of successfully scraped pages
        self.min_scraped_pages = 6
        self.max_scraped_pages = 8
        
        # List of domains to exclude
        self.exclude_domains = [
            'facebook.com',
            'twitter.com',
            'instagram.com',
            'linkedin.com',
            'youtube.com',
            'pinterest.com',
            'reddit.com',
            'apps.apple.com',
            'play.google.com',
            'duck.ai',
            'tiktok.com',
        ]
    
    def detect_kali(self):
        """Detect if we're running on Kali Linux"""
        try:
            # Check for Kali-specific files
            if os.path.exists("/etc/kali-release"):
                logging.info("Kali Linux detected")
                return True
                
            # Check for Kali-specific directories
            if os.path.exists("/usr/share/kali-menu"):
                logging.info("Kali Linux detected")
                return True
                
            # Check lsb_release
            try:
                result = subprocess.run(["lsb_release", "-i"], capture_output=True, text=True)
                if "Kali" in result.stdout:
                    logging.info("Kali Linux detected")
                    return True
            except:
                pass
                
            # Check os-release
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r") as f:
                    content = f.read()
                    if "kali" in content.lower():
                        logging.info("Kali Linux detected")
                        return True
                        
            return False
        except Exception as e:
            logging.warning(f"Could not detect OS: {str(e)}")
            return False

    def get_random_user_agent(self):
        """Get random user agent"""
        return random.choice(self.user_agents)
    
    def human_like_delay(self, min_seconds=1, max_seconds=4):
        """Generate human-like random delay"""
        delay = random.uniform(min_seconds, max_seconds)
        return delay
    
    def extract_links_from_text(self, text):
        """Extract URLs from text using enhanced regex"""
        # Enhanced URL regex pattern
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.-]*\??[/\w\.-=&%]*'
        urls = re.findall(url_pattern, text)
        return urls
    
    def get_domain_name(self, url):
        """Extract domain name from URL"""
        try:
            parsed_url = urlparse(url)
            return parsed_url.netloc.replace('www.', '')
        except:
            return "unknown"
    
    def extract_clean_links(self, html_content, engine_name="Bing"):
        """Extract URLs from search results based on the search engine"""
        soup = BeautifulSoup(html_content, 'html.parser')
        clean_links = []
        
        if engine_name == "Bing":
            # Bing's main search result structure
            result_elements = soup.select('li.b_algo, .b_algo')
            
            for result in result_elements:
                # Get the main link from the result
                link_element = result.select_one('h2 a, .b_title a, a[href]')
                if link_element:
                    href = link_element.get('href', '')
                    if href and href.startswith('http'):
                        # Clean the URL
                        clean_url = self.clean_bing_url(href)
                        if clean_url and clean_url not in clean_links:
                            clean_links.append(clean_url)
            
            # If no structured results, try alternative approach
            if not clean_links:
                logging.warning(f"No structured results found for {engine_name}, trying alternative selectors")
                result_elements = soup.select('a[href]')
                for result in result_elements:
                    href = result.get('href', '')
                    if href and href.startswith('http') and 'bing.com' not in href:
                        clean_url = self.clean_bing_url(href)
                        if clean_url and clean_url not in clean_links:
                            clean_links.append(clean_url)
        
        elif engine_name == "StartPage":
            # StartPage search result structure
            result_elements = soup.select('.w-gl__result, .result')
            
            for result in result_elements:
                link_element = result.select_one('h3 a, a[href]')
                if link_element:
                    href = link_element.get('href', '')
                    if href and href.startswith('http') and 'startpage.com' not in href:
                        clean_url = self.clean_generic_url(href)
                        if clean_url and clean_url not in clean_links:
                            clean_links.append(clean_url)
            
            # If no structured results, try alternative approach
            if not clean_links:
                logging.warning(f"No structured results found for {engine_name}, trying alternative selectors")
                result_elements = soup.select('a[href]')
                for result in result_elements:
                    href = result.get('href', '')
                    if href and href.startswith('http') and 'startpage.com' not in href:
                        clean_url = self.clean_generic_url(href)
                        if clean_url and clean_url not in clean_links:
                            clean_links.append(clean_url)
        
        # If still no structured results, try generic approach
        if not clean_links:
            logging.warning(f"No structured results found for {engine_name}, using generic extraction")
            # Look for any links that look like search results
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                if ('http' in href and 
                    engine_name.lower() not in href.lower() and
                    not any(domain in href.lower() for domain in ['microsoft', 'google']) and
                    not href.endswith(('.jpg', '.png', '.gif'))):
                    clean_url = self.clean_generic_url(href)
                    if clean_url and clean_url not in clean_links:
                        clean_links.append(clean_url)
        
        return clean_links[:20]  # Return more links to increase chances of getting good ones
    
    def clean_bing_url(self, url):
        """Clean URLs from Bing search results"""
        # Remove tracking parameters and clean URL
        if 'bing.com' in url and '/ck/' in url:
            # Bing redirect URL - extract actual URL
            match = re.search(r'u=([^&]+)', url)
            if match:
                import urllib.parse
                actual_url = urllib.parse.unquote(match.group(1))
                url = actual_url
        
        # Remove common Bing tracking
        url = re.sub(r'&r=.*', '', url)
        url = re.sub(r'&c=.*', '', url)
        
        # Basic validation
        if (url.startswith(('http://', 'https://')) and
            len(url) > 10 and
            '.' in url and
            ' ' not in url):
            return url.split('&')[0]  # Remove any remaining parameters
        
        return None
    
    def clean_generic_url(self, url):
        """Clean and validate generic URLs"""
        # Remove common tracking parameters
        url = re.sub(r'[?&](utm_|ref|source|campaign|medium).*?(&|$)', '', url)
        
        # Basic validation
        if (url.startswith(('http://', 'https://')) and
            len(url) > 10 and
            '.' in url and
            ' ' not in url):
            return url.split('&')[0]  # Remove any remaining parameters
        
        return None
    
    def aggressive_url_clean(self, url):
        """More aggressive URL cleaning"""
        # Remove common HTML fragments and malformed endings
        url = re.sub(r'</[^>]+>$', '', url)  # Remove closing HTML tags
        url = re.sub(r'<[^>]+>$', '', url)   # Remove opening HTML tags  
        url = re.sub(r'[<>"\')\]]+$', '', url)  # Remove trailing special chars
        url = url.split(' ')[0]  # Remove anything after space
        url = url.split('\\')[0]  # Remove anything after backslash
        url = url.split('\n')[0]  # Remove newlines
        
        # Ensure it's a valid URL
        if (url.startswith(('http://', 'https://')) and
            len(url) > 15 and  # Longer minimum length
            '.' in url[8:] and
            ' ' not in url):
            return url
        return None
    
    def clean_url(self, url):
        """Clean and validate URLs"""
        # Remove common trailing characters and HTML fragments
        url = re.sub(r'[<>"\)\]]+$', '', url)
        url = re.sub(r'</.*$', '', url)  # Remove HTML tags at end
        url = url.split(' ')[0]  # Remove any trailing spaces/content
        
        # Validate URL format
        if (url.startswith(('http://', 'https://')) and
            len(url) > 10 and
            '.' in url[8:]):  # Ensure there's a domain
            return url
        return None
    
    def is_search_engine_url(self, url, engine_name):
        """Check if URL is related to the search engine"""
        engine_domains = {
            "Bing": ['bing.com', 'microsoft.com', 'live.com', 'office.com'],
            "StartPage": ['startpage.com']
        }
        
        domains = engine_domains.get(engine_name, [])
        return any(domain in url.lower() for domain in domains)
    
    async def extract_home_page_content(self, page):
        """Simple home page content extraction"""
        try:
            body = await page.query_selector('body')
            if body:
                text = await body.text_content()
                return self.clean_content_with_regex(text)
            return "Home page content"
        except:
            return "Content extraction failed"
    
    def clean_content_with_regex(self, text):
        """Clean and extract meaningful content using regex patterns"""
        if not text:
            return ""
        
        # Remove script and style tags content
        text = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', text, flags=re.IGNORECASE)
        
        # Remove HTML tags but keep content
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Remove extra whitespace and newlines
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common unwanted patterns
        unwanted_patterns = [
            r'<!--.*?-->',  # HTML comments
            r'\{.*?\}',     # JSON-like content
            r'&\w+;',       # HTML entities
        ]
        
        for pattern in unwanted_patterns:
            text = re.sub(pattern, '', text)
        
        return text.strip()
    
    def extract_meaningful_content(self, html_content):
        """Extract meaningful content using regex patterns and heuristics"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'meta', 'link']):
            element.decompose()
        
        # Regex patterns for content detection
        content_indicators = [
            r'<main[^>]*>(.*?)</main>',
            r'<article[^>]*>(.*?)</article>',
            r'<div[^>]*class="[^"]*(content|post|article|main|body)[^"]*"[^>]*>(.*?)</div>',
            r'<section[^>]*>(.*?)</section>',
            r'<div[^>]*id="[^"]*(content|main|post|article)[^"]*"[^>]*>(.*?)</div>',
            r'<p[^>]*>(.*?)</p>',
        ]
        
        best_content = ""
        max_content_length = 0
        
        # Try different content extraction methods
        for pattern in content_indicators:
            matches = re.findall(pattern, str(soup), re.IGNORECASE | re.DOTALL)
            for match in matches:
                if isinstance(match, tuple):
                    content = ' '.join(match)
                else:
                    content = match
                
                cleaned_content = self.clean_content_with_regex(content)
                if len(cleaned_content) > max_content_length:
                    max_content_length = len(cleaned_content)
                    best_content = cleaned_content
        
        # Fallback: get all text content
        if not best_content:
            all_text = soup.get_text()
            best_content = self.clean_content_with_regex(all_text)
        
        # Content quality heuristics
        words = best_content.split()
        if len(words) < 50:  # Too short, probably not main content
            # Try body content
            body = soup.find('body')
            if body:
                body_text = body.get_text()
                best_content = self.clean_content_with_regex(body_text)
        
        return best_content[:15000]  # Limit content length
    
    async def setup_stealth_mode(self, page):
        """Enhanced stealth mode to avoid bot detection"""
        try:
            # Random user agent
            await page.set_extra_http_headers({
                'User-Agent': self.get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Linux"',
            })
            
            # Set viewport
            viewports = [
                {'width': 1920, 'height': 1080},
                {'width': 1366, 'height': 768},
                {'width': 1536, 'height': 864},
                {'width': 1440, 'height': 900},
            ]
            viewport = random.choice(viewports)
            await page.set_viewport_size(viewport)
            
            # Enhanced JavaScript evasions
            await page.add_init_script("""
                // Remove webdriver traces
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                // Override plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        }
                    ],
                });
                
                // Override languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                
                // Override permissions
                Object.defineProperty(navigator, 'permissions', {
                    get: () => ({
                        query: () => Promise.resolve({ state: 'granted' })
                    })
                });
                
                // Add chrome object
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {
                        return {
                            requestTime: Date.now() / 1000 - 0.2,
                            startLoadTime: Date.now() / 1000 - 0.2,
                            commitLoadTime: Date.now() / 1000 - 0.1,
                            finishDocumentLoadTime: Date.now() / 1000 - 0.05,
                            finishLoadTime: Date.now() / 1000 - 0.01,
                            firstPaintAfterLoadTime: 0,
                            firstPaintTime: Date.now() / 1000 - 0.15,
                            navigationType: "Other",
                            wasFetchedViaSpdy: false,
                            wasNpnNegotiated: false
                        };
                    },
                    csi: function() {
                        return {
                            pageT: Date.now() / 1000,
                            startE: Date.now() / 1000 - 0.2,
                            tran: 15
                        };
                    }
                };
                
                // Override the permissions query method
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Override WebGL Vendor
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) {
                        return 'Intel Inc.';
                    }
                    if (parameter === 37446) {
                        return 'Intel Iris OpenGL Engine';
                    }
                    return getParameter(parameter);
                };
                
                // Override battery API
                navigator.getBattery = () => Promise.resolve({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: 1
                });
                
                // Override timezone to a common one
                const originalGetTimezoneOffset = Date.prototype.getTimezoneOffset;
                Date.prototype.getTimezoneOffset = function() {
                    return 300; // EST timezone
                };
                
                // Override screen properties
                Object.defineProperty(screen, 'colorDepth', {
                    get: () => 24,
                });
                
                Object.defineProperty(screen, 'pixelDepth', {
                    get: () => 24,
                });
                
                // Add some randomization to make the fingerprint less consistent
                Math.random = function() {
                    const random = new Uint32Array(1);
                    crypto.getRandomValues(random);
                    return random[0] / 0xFFFFFFFF;
                };
                
                // Override connection API
                Object.defineProperty(navigator, 'connection', {
                    get: () => ({
                        effectiveType: '4g',
                        rtt: 100,
                        downlink: 10,
                        saveData: false
                    })
                });
                
                // Override memory API
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });
                
                // Override hardware concurrency
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 4
                });
            """)
            
            # Additional stealth for Kali Linux
            if self.is_kali:
                await page.add_init_script("""
                    // Override platform to look like Ubuntu
                    Object.defineProperty(navigator, 'platform', {
                        get: () => 'Linux x86_64',
                    });
                    
                    // Override userAgentData to look like Ubuntu
                    if (navigator.userAgentData) {
                        Object.defineProperty(navigator, 'userAgentData', {
                            get: () => ({
                                brands: [
                                    { brand: "Google Chrome", version: "120" },
                                    { brand: "Chromium", version: "120" },
                                    { brand: "Not:A-Brand", version: "8" }
                                ],
                                mobile: false,
                                platform: "Linux"
                            })
                        });
                    }
                """)
            
        except Exception as e:
            logging.debug(f"Stealth mode setup: {str(e)}")
    
    async def human_like_mouse_movements(self, page):
        """Simulate human-like mouse movements and scrolling"""
        try:
            # Get viewport size
            viewport = page.viewport_size
            if viewport:
                # Move mouse to random positions
                for _ in range(random.randint(2, 5)):
                    x = random.randint(100, viewport['width'] - 100)
                    y = random.randint(100, viewport['height'] - 100)
                    await page.mouse.move(x, y)
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                
                # Scroll randomly - improved scrolling logic
                scroll_count = random.randint(3, 8)
                for _ in range(scroll_count):
                    # Random scroll amount
                    scroll_amount = random.randint(200, 800)
                    await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                
                # Scroll back to top
                await page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
        except Exception as e:
            logging.debug(f"Mouse movement simulation skipped: {str(e)}")
    
    async def scroll_to_load_content(self, page, max_scrolls=5):
        """Scroll to load dynamic content on a page"""
        try:
            # Get initial page height
            last_height = await page.evaluate("document.body.scrollHeight")
            
            # Scroll down to load more content
            for i in range(max_scrolls):
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                
                # Wait for new content to load
                await asyncio.sleep(random.uniform(1.0, 3.0))
                
                # Calculate new scroll height and compare with last scroll height
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    # No more content loaded
                    break
                
                last_height = new_height
                
                # Random mouse movement while scrolling
                if random.random() > 0.5:  # 50% chance
                    viewport = page.viewport_size
                    if viewport:
                        x = random.randint(100, viewport['width'] - 100)
                        y = random.randint(100, viewport['height'] - 100)
                        await page.mouse.move(x, y)
            
            # Scroll back to top
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            logging.info(f"Scrolled {i+1} times to load content")
            return True
            
        except Exception as e:
            logging.error(f"Error during scrolling: {str(e)}")
            return False
    
    async def handle_captcha(self, page):
        """More accurate CAPTCHA detection and handling"""
        try:
            content = await page.content()
            page_text = content.lower()
            current_url = page.url.lower()
            
            # Strong CAPTCHA indicators
            strong_indicators = [
                (r'recaptcha', 'iframe'),
                (r'hcaptcha', 'iframe'),
                (r'challenge-platform', 'div'),
                (r'cf-challenge', 'div')
            ]
            
            # Check for strong indicators
            for pattern, tag in strong_indicators:
                if re.search(pattern, page_text):
                    # Verify it's actually in the page structure
                    elements = await page.query_selector_all(tag)
                    for element in elements:
                        html = await element.inner_html()
                        if re.search(pattern, html, re.IGNORECASE):
                            logging.warning(f"CAPTCHA confirmed: {pattern}")
                            # Try to solve CAPTCHA automatically (implementation depends on CAPTCHA type)
                            # For now, we'll just wait for manual intervention
                            logging.warning("Please solve the CAPTCHA manually. Waiting for 60 seconds...")
                            await asyncio.sleep(60)
                            
                            # Check if CAPTCHA is still present
                            new_content = await page.content()
                            if re.search(pattern, new_content.lower()):
                                return False  # CAPTCHA still present
                            else:
                                return True  # CAPTCHA solved
            
            # Check URL patterns for CAPTCHA
            captcha_url_patterns = [
                r'challenge',
                r'verify',
                r'captcha'
            ]
            
            for pattern in captcha_url_patterns:
                if re.search(pattern, current_url):
                    logging.warning(f"CAPTCHA URL detected: {current_url}")
                    logging.warning("Please solve the CAPTCHA manually. Waiting for 60 seconds...")
                    await asyncio.sleep(60)
                    
                    # Check if URL has changed (CAPTCHA solved)
                    new_url = page.url.lower()
                    if not re.search(pattern, new_url):
                        return True  # CAPTCHA solved
                    else:
                        return False  # CAPTCHA still present
            
            return True  # No CAPTCHA detected
            
        except Exception as e:
            logging.debug(f"CAPTCHA check completed: {str(e)}")
            return True
    
    def filter_search_links(self, links, engine_name):
        """Filter and clean search result links"""
        filtered_links = []
        
        # Patterns to exclude based on search engine
        exclude_patterns = {
            "Bing": [
                r'bing\.com',
                r'microsoft\.com', 
                r'live\.com',
                r'office\.com',
                r'go\.microsoft\.com',
                r'privacy',
                r'preferences',
                r'account'
            ],
            "StartPage": [
                r'startpage\.com',
                r'ixquick\.com'
            ]
        }
        
        # Common patterns to exclude
        common_patterns = [
            r'\.(png|jpg|jpeg|gif|pdf|css|js|woff|ttf)($|\?)',
        ]
        
        # Get engine-specific patterns
        engine_patterns = exclude_patterns.get(engine_name, [])
        
        for link in links:
            # Skip if matches exclude patterns
            if any(re.search(pattern, link, re.IGNORECASE) for pattern in engine_patterns + common_patterns):
                continue
                
            # Skip if domain is in exclude list
            domain = self.get_domain_name(link)
            if any(exclude_domain in domain for exclude_domain in self.exclude_domains):
                continue
                
            # Skip very short links
            if len(link) < 10:
                continue
                
            # Skip duplicate links
            if link not in filtered_links:
                filtered_links.append(link)
        
        return filtered_links
    
    def validate_content_quality(self, content):
        """Validate if the scraped content is of good quality"""
        if not content:
            return False
        
        # Remove HTML tags if any
        text = re.sub(r'<[^>]+>', ' ', content)
        
        # Count words
        words = text.split()
        
        # Check if content has enough words
        if len(words) < 100:
            return False
        
        # Check if content has meaningful sentences
        sentences = re.split(r'[.!?]+', text)
        meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        if len(meaningful_sentences) < 5:
            return False
        
        return True
    
    async def search_engine(self, page, engine, query, use_proxy=False, retry_count=0):
        """Search using a specific search engine with improved error handling and retry logic"""
        engine_name = engine["name"]
        engine_url = engine["url"]
        search_path = engine["search_path"]
        direct_search_url = engine.get("direct_search_url", "")
        
        max_retries = 3
        if retry_count >= max_retries:
            logging.error(f"Max retries ({max_retries}) exceeded for {engine_name}")
            return []
        
        # Add delay between retries
        if retry_count > 0:
            delay = min(10 * (2 ** retry_count), 60)  # Exponential backoff, max 60 seconds
            logging.info(f"Retrying {engine_name} in {delay} seconds (attempt {retry_count + 1}/{max_retries})")
            await asyncio.sleep(delay)
        
        logging.info(f"Searching {engine_name} for: {query} (Proxy: {use_proxy}, Retry: {retry_count})")
        
        try:
            # Setup stealth
            await self.setup_stealth_mode(page)
            await asyncio.sleep(self.human_like_delay(2, 4))
            
            # Try alternative search methods based on engine
            if engine_name == "Bing":
                # Try different Bing search URLs to avoid detection
                bing_urls = [
                    f"https://www.bing.com/search?q={quote(query)}",
                    f"https://www.bing.com/?q={quote(query)}",
                    f"https://cc.bingj.com/cache.aspx?d=503-6298-7580&w=8f5c3f3e4e0c6e6b4c2e5f6e5d6e5f6e&u={quote('https://www.bing.com/search?q=' + query)}"
                ]
                
                for url in bing_urls:
                    try:
                        logging.info(f"Trying Bing URL: {url}")
                        await page.goto(url, timeout=20000, wait_until='domcontentloaded')
                        
                        # Check if we're blocked
                        page_content = await page.content()
                        if 'blocked' in page_content.lower() or 'captcha' in page_content.lower():
                            logging.warning(f"Bing URL blocked: {url}")
                            continue
                        
                        # Wait for results
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        
                        # Add human-like behavior on search results page
                        await self.human_like_mouse_movements(page)
                        
                        # Scroll to load more results if needed
                        await self.scroll_to_load_content(page, max_scrolls=2)
                        
                        # Check for blocks
                        final_content = await page.content()
                        if 'no results' in final_content.lower() or 'blocked' in final_content.lower():
                            logging.warning(f"Possible block detected on Bing - no results found")
                            continue
                        
                        # Extract links
                        links = self.extract_clean_links(final_content, engine_name)
                        filtered_links = self.filter_search_links(links, engine_name)
                        
                        if filtered_links:
                            return filtered_links
                    except Exception as e:
                        logging.warning(f"Bing URL failed: {url} - {str(e)}")
                        continue
            
            elif engine_name == "StartPage":
                # Try different StartPage search URLs
                startpage_urls = [
                    f"https://www.startpage.com/do/search?query={quote(query)}",
                    f"https://www.startpage.com/sp/search?query={quote(query)}",
                    f"https://startpage.com/do/search?query={quote(query)}"
                ]
                
                for url in startpage_urls:
                    try:
                        logging.info(f"Trying StartPage URL: {url}")
                        await page.goto(url, timeout=20000, wait_until='domcontentloaded')
                        
                        # Check if we're blocked
                        page_content = await page.content()
                        if 'blocked' in page_content.lower() or 'captcha' in page_content.lower():
                            logging.warning(f"StartPage URL blocked: {url}")
                            continue
                        
                        # Wait for results
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        
                        # Add human-like behavior on search results page
                        await self.human_like_mouse_movements(page)
                        
                        # Scroll to load more results if needed
                        await self.scroll_to_load_content(page, max_scrolls=2)
                        
                        # Check for blocks
                        final_content = await page.content()
                        if 'no results' in final_content.lower() or 'blocked' in final_content.lower():
                            logging.warning(f"Possible block detected on StartPage - no results found")
                            continue
                        
                        # Extract links
                        links = self.extract_clean_links(final_content, engine_name)
                        filtered_links = self.filter_search_links(links, engine_name)
                        
                        if filtered_links:
                            return filtered_links
                    except Exception as e:
                        logging.warning(f"StartPage URL failed: {url} - {str(e)}")
                        continue
            
            # If all specific URLs failed, try the generic approach
            logging.warning(f"All specific URLs failed for {engine_name}, trying generic approach")
            return await self._generic_search(page, engine, query, use_proxy)
                
        except Exception as e:
            logging.error(f"Search on {engine_name} failed: {str(e)}")
            # Retry if we haven't reached max retries
            if retry_count < max_retries:
                return await self.search_engine(page, engine, query, use_proxy, retry_count + 1)
            return []

    async def _generic_search(self, page, engine, query, use_proxy):
        """Generic search approach as a fallback"""
        engine_name = engine["name"]
        engine_url = engine["url"]
        search_path = engine["search_path"]
        
        try:
            # Navigate to the search engine homepage
            await page.goto(engine_url, timeout=15000, wait_until='domcontentloaded')
            
            # Check if we're blocked immediately
            page_content = await page.content()
            if 'blocked' in page_content.lower() or 'captcha' in page_content.lower():
                logging.error(f"{engine_name} blocked access immediately")
                return []
            
            # Find search box using multiple approaches
            search_box = await self.find_search_box(page, engine_name)
            
            if search_box:
                # Use JavaScript to set value (more reliable)
                await page.evaluate(f'(element) => element.value = "{query}"', search_box)
                await asyncio.sleep(1)
                await search_box.press('Enter')
            else:
                # Direct URL fallback
                encoded_query = quote(query)
                search_url = f"{engine_url}{search_path}{encoded_query}"
                await page.goto(search_url, timeout=15000, wait_until='domcontentloaded')
            
            # Wait for results
            await page.wait_for_load_state('networkidle', timeout=15000)
            
            # Add human-like behavior on search results page
            await self.human_like_mouse_movements(page)
            
            # Scroll to load more results if needed
            await self.scroll_to_load_content(page, max_scrolls=2)
            
            # Check for blocks
            final_content = await page.content()
            if 'no results' in final_content.lower() or 'blocked' in final_content.lower():
                logging.warning(f"Possible block detected on {engine_name} - no results found")
                return []
            
            # Extract links
            links = self.extract_clean_links(final_content, engine_name)
            filtered_links = self.filter_search_links(links, engine_name)
            
            return filtered_links
            
        except Exception as e:
            logging.error(f"Generic search on {engine_name} failed: {str(e)}")
            return []
        
        async def find_search_box(self, page, engine_name):
            """Find search box based on search engine"""
            search_selectors = {
                "Bing": ['input[name="q"]', '#sb_form_q', 'input[type="search"]'],
                "StartPage": ['input[name="query"]', '#query', 'input[type="search"]']
            }
            
            selectors = search_selectors.get(engine_name, ['input[name="q"]', 'input[type="search"]'])
            
            for selector in selectors:
                try:
                    search_box = await page.wait_for_selector(selector, timeout=5000)
                    if search_box:
                        return search_box
                except:
                    continue
            
            return None
    
    async def search_with_fallback(self, page, query):
        """Try searching with multiple search engines as fallbacks with better error handling"""
        all_links = []
        engine_usage = {}
        connection_methods = {}
        
        # Try each search engine until we have enough links
        for engine in self.search_engines:
            engine_name = engine["name"]
            
            # Skip if this engine is blocked
            if engine_name in self.blocked_engines:
                logging.info(f"Skipping {engine_name} - previously blocked")
                continue
                
            try:
                # Create a new page for this search
                search_page = await page.context.new_page()
                await self.setup_stealth_mode(search_page)
                
                # Try searching with this engine using direct connection first
                links = await self.search_engine(search_page, engine, query, use_proxy=False)
                
                if links:
                    logging.info(f"Successfully found {len(links)} links using {engine_name} (direct)")
                    all_links.extend(links)
                    engine_usage[engine_name] = engine_usage.get(engine_name, 0) + 1
                    connection_methods[f"{engine_name}:direct"] = connection_methods.get(f"{engine_name}:direct", 0) + 1
                    
                    # Remove duplicates
                    all_links = list(dict.fromkeys(all_links))
                    
                    # Check if we have enough links
                    if len(all_links) >= 15:  # Get more links to increase chances of good content
                        await search_page.close()
                        return all_links, engine_usage, connection_methods
                else:
                    logging.warning(f"No results from {engine_name} (direct)")
                    await search_page.close()
                    
                    # Check if we're blocked
                    if await self.is_engine_blocked(engine):
                        self.blocked_engines.add(engine_name)
                        logging.warning(f"{engine_name} appears to be blocked, adding to blocked list")
                    
                    # Try with proxy if available
                    proxy = self.proxy_rotator.get_next_proxy()
                    if proxy:
                        try:
                            # Create a new context with proxy
                            proxy_context = await page.context.browser.new_context(
                                proxy={"server": f"http://{proxy}"},
                                viewport={'width': 1920, 'height': 1080},
                                user_agent=self.get_random_user_agent()
                            )
                            
                            proxy_page = await proxy_context.new_page()
                            await self.setup_stealth_mode(proxy_page)
                            
                            links = await self.search_engine(proxy_page, engine, query, use_proxy=True)
                            
                            if links:
                                logging.info(f"Successfully found {len(links)} links using {engine_name} (proxy: {proxy})")
                                all_links.extend(links)
                                engine_usage[engine_name] = engine_usage.get(engine_name, 0) + 1
                                connection_methods[f"{engine_name}:proxy"] = connection_methods.get(f"{engine_name}:proxy", 0) + 1
                                
                                # Remove duplicates
                                all_links = list(dict.fromkeys(all_links))
                                
                                # Check if we have enough links
                                if len(all_links) >= 15:  # Get more links to increase chances of good content
                                    await proxy_page.close()
                                    await proxy_context.close()
                                    return all_links, engine_usage, connection_methods
                            else:
                                logging.warning(f"No results from {engine_name} (proxy: {proxy})")
                                await proxy_page.close()
                                await proxy_context.close()
                                
                                # Mark proxy as failed
                                self.proxy_rotator.mark_proxy_failed(proxy)
                                
                        except Exception as e:
                            logging.error(f"Proxy search failed for {engine_name}: {str(e)}")
                            try:
                                await proxy_page.close()
                                await proxy_context.close()
                            except:
                                pass
                            
                            # Mark proxy as failed
                            self.proxy_rotator.mark_proxy_failed(proxy)
                        
            except Exception as e:
                logging.error(f"Error searching with {engine_name}: {str(e)}")
                try:
                    await search_page.close()
                except:
                    pass
        
        # If we've tried all engines and still don't have enough links, return what we have
        if all_links:
            logging.warning(f"Only found {len(all_links)} links after trying all engines")
            return all_links, engine_usage, connection_methods
        else:
            logging.error("All search engines failed or are blocked")
            return [], engine_usage, connection_methods
    
    async def is_engine_blocked(self, engine):
        """Check if a search engine is likely blocking us"""
        # This is a simplified check - in a real implementation, you might
        # want to navigate to the engine and check for CAPTCHA or block messages
        return False
    
    async def scrape_page_content(self, page, url):
        """Scrape content with better targeting and scrolling"""
        try:
            logging.info(f"Scraping content from: {url}")
            
            # Setup stealth mode
            await self.setup_stealth_mode(page)
            
            # Navigate to the page
            await page.goto(url, timeout=30000, wait_until='domcontentloaded')
            
            # Wait for content to load
            await asyncio.sleep(self.human_like_delay(2, 4))
            
            # Add human-like behavior
            await self.human_like_mouse_movements(page)
            
            # Scroll to load dynamic content
            await self.scroll_to_load_content(page, max_scrolls=5)
            
            # Get page title
            title = await page.title()
            
            # Try to extract main content using multiple strategies
            content_text = await self.extract_main_content(page)
            
            # If no meaningful content found, it might be a home page
            if len(content_text.split()) < 100:
                logging.info(f"Low content on {url}, might be home page")
                content_text = await self.extract_home_page_content(page)
            
            # Validate content quality
            is_quality_content = self.validate_content_quality(content_text)
            
            return {
                'url': url,
                'title': title,
                'content': content_text[:10000],
                'content_length': len(content_text),
                'word_count': len(content_text.split()),
                'is_quality_content': is_quality_content,
                'scraped_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error scraping {url}: {str(e)}")
            return {
                'url': url,
                'title': 'Error loading page',
                'content': f'Error: {str(e)}',
                'content_length': 0,
                'word_count': 0,
                'is_quality_content': False,
                'error': str(e),
                'scraped_at': datetime.now().isoformat()
            }
    
    async def extract_main_content(self, page):
        """Extract main content from page"""
        content_selectors = [
            'article',
            'main',
            '.content',
            '#content',
            '.post-content',
            '.entry-content',
            '.article-content',
            'div[role="main"]'
        ]
        
        for selector in content_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.text_content()
                    if text and len(text.strip().split()) > 50:  # Meaningful content
                        return self.clean_content_with_regex(text)
            except:
                continue
        
        # Fallback: get body content
        body = await page.query_selector('body')
        if body:
            text = await body.text_content()
            return self.clean_content_with_regex(text)
        
        return ""
    
    def should_skip_url(self, url):
        """Check if we should skip scraping this URL"""
        domain = self.get_domain_name(url)
        
        # Skip if domain is in exclude list
        if any(exclude_domain in domain for exclude_domain in self.exclude_domains):
            return True
        
        # Skip if URL contains certain patterns
        skip_patterns = [
            'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
            'zip', 'rar', 'tar', 'gz', 'exe', 'dmg',
            'login', 'signin', 'register', 'signup',
            'cart', 'checkout', 'payment'
        ]
        
        for pattern in skip_patterns:
            if pattern in url.lower():
                return True
        
        return False
    
    async def run_scraping(self):
            # Hardcoded search queries
            search_queries = [
                "AI-generated image of Jackie Chan's death circulated online",
                "Elon Musk's conversation with his AI chatbot Grok about Lord Ganesha",
                "Dog Dental Powder",
                "Best practices for remote team management",
                "Latest advancements in renewable energy technologies",
                "Impact of social media on mental health",
                "Top programming languages to learn in 2026",
                "Post Quantum Cryptography",
                "AI Vocal Remover",
                "Benefits of mindfulness meditation"
            ]
            
            # Refresh proxy list
            await self.proxy_rotator.refresh_proxy_list()
            
            # We don't need a single browser instance anymore.
            # We will launch a persistent context for each query.
            async with async_playwright() as p:
                all_results = {}
                
                for query_index, query in enumerate(search_queries):
                    logging.info(f"Processing query {query_index + 1}/{len(search_queries)}: {query}")
                    
                    # Create a unique user data directory for each query to ensure isolation
                    user_data_dir = f"/tmp/chromium-user-data-{query_index}-{uuid.uuid4().hex[:8]}"
                    
                    # Launch a persistent context for each query. This replaces browser.launch() and browser.new_context()
                    context = await p.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        headless=False,  # Keep visible for debugging
                        args=self.browser_args,
                        slow_mo=500,  # Slow down operations
                        viewport={'width': 1920, 'height': 1080},
                        user_agent=self.get_random_user_agent(),
                        java_script_enabled=True,
                        bypass_csp=True,
                        ignore_https_errors=True,
                        extra_http_headers={
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                            'Cache-Control': 'max-age=0',
                            'Sec-Fetch-Dest': 'document',
                            'Sec-Fetch-Mode': 'navigate',
                            'Sec-Fetch-Site': 'none',
                            'Sec-Fetch-User': '?1',
                            'Upgrade-Insecure-Requests': '1',
                        }
                    )
                    
                    # Create a page for searching
                    search_page = await context.new_page()
                    await self.setup_stealth_mode(search_page)
                    
                    # Perform search with fallback engines
                    links, engine_usage, connection_methods = await self.search_with_fallback(search_page, query)
                    
                    await search_page.close()  # Close page after search
                    
                    if not links:
                        logging.warning(f"No links found for query: {query}. Possible block detected.")
                        # Skip to next query
                        await context.close() # Close the context for this query
                        continue
                    
                    # Print links to terminal
                    print(f"\n{'='*60}")
                    print(f"Links found for: '{query}'")
                    print(f"{'='*60}")
                    for i, link in enumerate(links, 1):
                        domain = self.get_domain_name(link)
                        print(f"{i:2d}. {domain:30} {link}")
                    
                    # Scrape content from each link until we have enough quality content
                    query_results = []
                    quality_content_count = 0
                    total_scraped = 0
                    
                    for link_index, link in enumerate(links):
                        if link in self.visited_links or self.should_skip_url(link):
                            continue
                        
                        # Stop if we have enough quality content
                        if quality_content_count >= self.min_scraped_pages:
                            logging.info(f"Successfully scraped {quality_content_count} quality pages, stopping for this query")
                            break
                        
                        # Stop if we've scraped too many pages
                        if total_scraped >= self.max_scraped_pages * 2:  # Allow double attempts to find quality content
                            logging.info(f"Scraped {total_scraped} pages, stopping for this query")
                            break
                        
                        total_scraped += 1
                        logging.info(f"Scraping {total_scraped}/{len(links)}: {self.get_domain_name(link)}")
                        
                        # Create a new page for each link to avoid detection
                        scrape_page = await context.new_page()
                        await self.setup_stealth_mode(scrape_page)
                        
                        # Handle CAPTCHA if needed
                        if not await self.handle_captcha(scrape_page):
                            logging.warning(f"CAPTCHA not solved for {link}, skipping")
                            await scrape_page.close()
                            continue
                        
                        # Scrape content
                        result = await self.scrape_page_content(scrape_page, link)
                        await scrape_page.close()
                        
                        # Add to visited links
                        self.visited_links.append(link)
                        
                        # Check if we got quality content
                        if result.get('is_quality_content', False):
                            quality_content_count += 1
                            query_results.append(result)
                            logging.info(f"Got quality content from {link} ({quality_content_count}/{self.min_scraped_pages})")
                        else:
                            logging.warning(f"Low quality content from {link}")
                    
                    # Store results for this query
                    all_results[query] = {
                        'query': query,
                        'results': query_results,
                        'engine_usage': engine_usage,
                        'connection_methods': connection_methods,
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    # Save results to file
                    output_file = f"search_results_{query_index + 1}.json"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(all_results[query], f, indent=2, ensure_ascii=False)
                    
                    logging.info(f"Saved results for query '{query}' to {output_file}")
                    
                    # Clean up user data directory
                    try:
                        import shutil
                        shutil.rmtree(user_data_dir)
                        logging.info(f"Cleaned up user data directory: {user_data_dir}")
                    except Exception as e:
                        logging.warning(f"Could not clean up user data directory {user_data_dir}: {str(e)}")

                    # Close the context for this query
                    await context.close()
                    
                    # Wait between queries to avoid rate limiting
                    if query_index < len(search_queries) - 1:
                        wait_time = random.uniform(10, 30)
                        logging.info(f"Waiting {wait_time:.2f} seconds before next query...")
                        await asyncio.sleep(wait_time)
                
                # Save all results
                with open("all_search_results.json", 'w', encoding='utf-8') as f:
                    json.dump(all_results, f, indent=2, ensure_ascii=False)
                
                logging.info("Scraping completed. Results saved to all_search_results.json")
                return all_results
    async def search_with_alternatives(self, page, query):
        """Try alternative search methods when traditional engines fail"""
        all_links = []
        
        # Try DuckDuckGo HTML version (no JS required)
        try:
            duckduckgo_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            await page.goto(duckduckgo_url, timeout=15000, wait_until='domcontentloaded')
            
            # Extract links from DuckDuckGo results
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            result_links = soup.select('.result__a')
            for link in result_links:
                href = link.get('href', '')
                if href and href.startswith('http'):
                    clean_url = self.clean_generic_url(href)
                    if clean_url and clean_url not in all_links:
                        all_links.append(clean_url)
            
            if all_links:
                logging.info(f"Found {len(all_links)} links using DuckDuckGo HTML")
                return all_links
        except Exception as e:
            logging.warning(f"DuckDuckGo HTML search failed: {str(e)}")
        
        # Try Qwant (privacy-focused search engine)
        try:
            qwant_url = f"https://www.qwant.com/?q={quote(query)}&t=web"
            await page.goto(qwant_url, timeout=15000, wait_until='domcontentloaded')
            
            # Extract links from Qwant results
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            result_links = soup.select('a.result')
            for link in result_links:
                href = link.get('href', '')
                if href and href.startswith('http'):
                    clean_url = self.clean_generic_url(href)
                    if clean_url and clean_url not in all_links:
                        all_links.append(clean_url)
            
            if all_links:
                logging.info(f"Found {len(all_links)} links using Qwant")
                return all_links
        except Exception as e:
            logging.warning(f"Qwant search failed: {str(e)}")
        
        # Try Yandex (Russian search engine)
        try:
            yandex_url = f"https://yandex.com/search/?text={quote(query)}"
            await page.goto(yandex_url, timeout=15000, wait_until='domcontentloaded')
            
            # Extract links from Yandex results
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            result_links = soup.select('a.organic__url')
            for link in result_links:
                href = link.get('href', '')
                if href and href.startswith('http'):
                    clean_url = self.clean_generic_url(href)
                    if clean_url and clean_url not in all_links:
                        all_links.append(clean_url)
            
            if all_links:
                logging.info(f"Found {len(all_links)} links using Yandex")
                return all_links
        except Exception as e:
            logging.warning(f"Yandex search failed: {str(e)}")
        
        return all_links

# Add this method to the EnhancedSearchScraper class in scrapping.py


# Add this function at the end of your data_scrapper.py file, outside the class

async def search_and_scrape(queries, headless=False):
    """
    Interface function between the main pipeline (main4.py) and the scraper.
    
    Args:
        queries (list): A list of search query strings.
        headless (bool): Whether to run the browser in headless mode.
        
    Returns:
        dict: A dictionary mapping each query to its scraped results.
    """
    # This is the main function that main4.py will call.
    # It creates an instance of the scraper and runs the scraping process.
    
    scraper = EnhancedSearchScraper()
    await scraper.proxy_rotator.refresh_proxy_list()
    results = {}

    for i, query in enumerate(queries):
        logging.info(f"Processing query {i + 1}/{len(queries)}: '{query}'")
        
        # Add a delay between queries to avoid rate limiting
        if i > 0:
            delay = random.uniform(10, 20)
            logging.info(f"Waiting {delay:.2f} seconds before next query...")
            await asyncio.sleep(delay)
        
        try:
            # Create a unique user data directory for each query to ensure isolation
            user_data_dir = f"/tmp/chromium-user-data-{uuid.uuid4().hex[:8]}"
            
            # Use a persistent context for each query to avoid detection
            async with async_playwright() as p:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=headless,
                    args=scraper.browser_args,
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=scraper.get_random_user_agent(),
                    java_script_enabled=True,
                    bypass_csp=True,
                    ignore_https_errors=True
                )
                
                # Create a page for searching
                search_page = await context.new_page()
                await scraper.setup_stealth_mode(search_page)
                
                # Perform search with fallback engines
                links, engine_usage, connection_methods = await scraper.search_with_fallback(search_page, query)
                
                # If traditional search engines failed, try the alternatives
                if not links:
                    logging.warning("Traditional search engines failed, trying alternative methods...")
                    links = await scraper.search_with_alternatives(search_page, query)
                
                await search_page.close()
                
                if links:
                    # Scrape content from each link
                    query_results = []
                    quality_content_count = 0
                    
                    for link_index, link in enumerate(links):
                        # Stop if we have enough quality content
                        if quality_content_count >= scraper.min_scraped_pages:
                            logging.info(f"Successfully scraped {quality_content_count} quality pages, stopping for this query")
                            break
                        
                        if scraper.should_skip_url(link):
                            continue
                        
                        # Create a new page for each link to avoid detection
                        scrape_page = await context.new_page()
                        await scraper.setup_stealth_mode(scrape_page)
                        
                        # Handle CAPTCHA if needed
                        if not await scraper.handle_captcha(scrape_page):
                            logging.warning(f"CAPTCHA not solved for {link}, skipping")
                            await scrape_page.close()
                            continue
                        
                        # Scrape content
                        result = await scraper.scrape_page_content(scrape_page, link)
                        await scrape_page.close()
                        
                        # Check if we got quality content
                        if result.get('is_quality_content', False):
                            quality_content_count += 1
                            query_results.append(result)
                            logging.info(f"Got quality content from {link} ({quality_content_count}/{scraper.min_scraped_pages})")
                        else:
                            logging.warning(f"Low quality content from {link}")
                        
                        # Add delay between page scrapes
                        await asyncio.sleep(random.uniform(3, 8))
                    
                    results[query] = {
                        'query': query,
                        'results': query_results,
                        'engine_usage': engine_usage,
                        'connection_methods': connection_methods,
                        'scraped_at': datetime.now().isoformat()
                    }
                else:
                    logging.warning(f"No links found for query: {query}")
                    results[query] = {
                        'query': query,
                        'results': [],
                        'engine_usage': engine_usage,
                        'connection_methods': connection_methods,
                        'scraped_at': datetime.now().isoformat(),
                        'error': 'No links found'
                    }
                
                # Clean up user data directory
                try:
                    import shutil
                    shutil.rmtree(user_data_dir)
                    logging.info(f"Cleaned up user data directory: {user_data_dir}")
                except Exception as e:
                    logging.warning(f"Could not clean up user data directory {user_data_dir}: {str(e)}")

        except Exception as e:
            logging.error(f"Error processing query '{query}': {str(e)}")
            results[query] = {
                'query': query,
                'results': [],
                'scraped_at': datetime.now().isoformat(),
                'error': str(e)
            }
    
    return results
# Add a main function to run the scraper
async def main():
    scraper = EnhancedSearchScraper()
    await scraper.run_scraping()

if __name__ == "__main__":
    # Run the scraper
    asyncio.run(main())