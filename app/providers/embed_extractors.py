import httpx
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Any
import json

async def get_direct_sources(embed_url: str) -> List[Dict[str, Any]]:
    """Extract direct stream sources from any embed URL"""
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(embed_url, follow_redirects=True)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Try multiple extraction methods
            sources = []
            
            # Method 1: JSON player config
            sources.extend(extract_json_player(soup))
            
            # Method 2: iframe src
            sources.extend(await extract_nested_iframe(embed_url, client))
            
            # Method 3: Script tags with sources
            sources.extend(extract_script_sources(soup))
            
            # Method 4: Meta tags
            sources.extend(extract_meta_sources(soup))
            
            # Method 5: Common embed patterns
            sources.extend(extract_pattern_sources(soup))
            
            # Deduplicate and filter
            unique_sources = []
            seen_urls = set()
            
            for source in sources:
                if source.get('file') and source['file'] not in seen_urls:
                    seen_urls.add(source['file'])
                    unique_sources.append(source)
            
            return unique_sources
            
        except Exception as e:
            print(f"Error extracting sources: {e}")
            return []

def extract_json_player(soup: BeautifulSoup) -> List[Dict]:
    """Extract from JSON player configs"""
    sources = []
    
    # Common player JSON patterns
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string:
            # Vidstream/dooood pattern
            m = re.search(r'file:\s*"([^"]+)"', script.string)
            if m:
                sources.append({"file": m.group(1), "label": "Auto", "type": "mp4"})
            
            # JSON.parse config
            json_match = re.search(r'JSON\.parse\(["\']([^"\']+)["\']\)', script.string)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    if isinstance(data, dict) and 'sources' in data:
                        sources.extend(data['sources'])
                except:
                    pass
    
    return sources

async def extract_nested_iframe(embed_url: str, client: httpx.AsyncClient) -> List[Dict]:
    """Follow iframe redirects"""
    sources = []
    
    try:
        iframes = BeautifulSoup(await client.get(embed_url)).find_all('iframe')
        for iframe in iframes[:3]:  # Limit to avoid infinite loops
            iframe_src = iframe.get('src') or iframe.get('data-src')
            if iframe_src:
                if not iframe_src.startswith('http'):
                    # Relative URL
                    from urllib.parse import urljoin
                    iframe_src = urljoin(embed_url, iframe_src)
                
                iframe_resp = await client.get(iframe_src)
                iframe_sources = extract_json_player(BeautifulSoup(iframe_resp.text))
                sources.extend(iframe_sources)
    except:
        pass
    
    return sources

def extract_script_sources(soup: BeautifulSoup) -> List[Dict]:
    """Extract from inline scripts"""
    sources = []
    scripts = soup.find_all('script')
    
    patterns = [
        r'sources\s*:\s*\[([^\]]+)\]',
        r'fileUrl\s*["\']([^"\']+)["\']',
        r'hlsSrc\s*["\']([^"\']+)["\']',
        r'source\s*["\']([^"\']+)["\']',
    ]
    
    for script in scripts:
        if script.string:
            for pattern in patterns:
                matches = re.findall(pattern, script.string, re.IGNORECASE)
                for match in matches:
                    if match.strip():
                        sources.append({"file": match.strip(), "label": "Auto", "type": "mp4"})
    
    return sources

def extract_meta_sources(soup: BeautifulSoup) -> List[Dict]:
    """Extract from meta tags"""
    sources = []
    metas = soup.find_all('meta', attrs={'property': re.compile('video')})
    
    for meta in metas:
        content = meta.get('content')
        if content:
            sources.append({"file": content, "label": "Auto", "type": "mp4"})
    
    return sources

def extract_pattern_sources(soup: BeautifulSoup) -> List[Dict]:
    """Catch-all pattern matching"""
    sources = []
    
    # Common stream patterns in text/content
    patterns = [
        r'(?:https?://[^\s<>"\']+\.(?:m3u8|mp4|ts|webm)[^\s<>"\']*)',
        r'"([^"]+\.(?:m3u8|mp4|ts|webm))"',
        r"'([^']+\.(?:m3u8|mp4|ts|webm))'",
    ]
    
    text = soup.get_text()
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            sources.append({"file": match, "label": "Auto", "type": "mp4"})
    
    return sources[:10]  # Limit results
