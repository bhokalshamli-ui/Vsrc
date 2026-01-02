import httpx
import re
import json
from typing import Dict, Any, List
from bs4 import BeautifulSoup
import base64
import js2py

class VidSrcProvider:
    BASE_URL = "https://vidsrc.to"  # Updated to working domain
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    async def get_streams(
        self,
        media_type: str,  # movie, tv
        id: str,
        season: int = None,
        episode: int = None,
        server: str = "9",  # VidSrc server ID
        sources: bool = True,
        subtitles: bool = True
    ) -> Dict[str, Any]:
        
        if media_type == "tv" and season and episode:
            url = f"{self.BASE_URL}/embed/{id}/{season}/{episode}"
        else:
            url = f"{self.BASE_URL}/embed/{media_type}/{id}"
        
        async with httpx.AsyncClient(
            headers=self.HEADERS,
            timeout=30.0,
            follow_redirects=True
        ) as client:
            
            # Step 1: Get main page
            resp = await client.get(url)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Step 2: Find the actual player iframe
            player_iframe = self.find_player_iframe(soup)
            if not player_iframe:
                return {"sources": [], "subtitles": [], "error": "Player not found"}
            
            # Step 3: Extract from player iframe
            player_sources = await self.extract_player_sources(player_iframe, client)
            
            result = {
                "sources": player_sources,
                "subtitles": await self.extract_subtitles(player_iframe, client) if subtitles else [],
                "error": None
            }
            
            return result
    
    def find_player_iframe(self, soup: BeautifulSoup) -> str:
        """Find the actual VidSrc player iframe"""
        
        # Method 1: Data-iframe attribute
        iframe = soup.find('div', {'data-iframe': True})
        if iframe:
            src = iframe.get('data-iframe')
            if src:
                return src
        
        # Method 2: Script with iframe src
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # VidSrc iframe pattern
                match = re.search(r'iframe\.src\s*=\s*["\']([^"\']+)["\']', script.string)
                if match:
                    return match.group(1)
                
                # Base64 encoded iframe
                b64_match = re.search(r'iframe\.src\s*=\s*["\']([^"\']+)["\']', script.string)
                if b64_match:
                    try:
                        decoded = base64.b64decode(b64_match.group(1)).decode()
                        iframe_url_match = re.search(r'(https?://[^\s"\'<>]+)', decoded)
                        if iframe_url_match:
                            return iframe_url_match.group(1)
                    except:
                        pass
        
        # Method 3: Direct iframe
        iframe = soup.find('iframe', src=re.compile(r'vidsrc|player'))
        if iframe:
            return iframe.get('src') or iframe.get('data-src')
        
        return None
    
    async def extract_player_sources(self, player_url: str, client: httpx.AsyncClient) -> List[Dict]:
        """Extract direct sources from VidSrc player"""
        try:
            resp = await client.get(player_url)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            sources = []
            
            # VidSrc uses encrypted JSON - decode it
            sources.extend(self.decode_vidsrc_player(soup))
            
            # Fallback: common patterns
            if not sources:
                sources.extend(self.extract_fallback_sources(resp.text))
            
            return sources
            
        except Exception as e:
            print(f"Player extraction error: {e}")
            return []
    
    def decode_vidsrc_player(self, soup: BeautifulSoup) -> List[Dict]:
        """Decode VidSrc's encrypted player config"""
        sources = []
        
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # VidSrc player config pattern
                config_match = re.search(r'playerConfig\s*=\s*({[^}]+})', script.string, re.DOTALL)
                if config_match:
                    try:
                        config = json.loads(config_match.group(1))
                        if 'sources' in config:
                            for source in config['sources']:
                                sources.append({
                                    "file": source.get('file'),
                                    "label": source.get('label', 'Auto'),
                                    "type": source.get('type', 'mp4'),
                                    "quality": source.get('quality', 'Auto')
                                })
                        break
                    except:
                        pass
                
                # Alternative: Base64 + eval pattern
                b64_match = re.search(r'atob\(["\']([^"\']+)["\']\)', script.string)
                if b64_match:
                    try:
                        encoded = b64_match.group(1)
                        decoded = base64.b64decode(encoded).decode()
                        json_match = re.search(r'\{[^}]+\}', decoded)
                        if json_match:
                            data = json.loads(json_match.group(0))
                            if 'sources' in data:
                                sources.extend([{
                                    "file": s['file'],
                                    "label": s.get('label', 'Auto'),
                                    "type": s.get('type', 'mp4')
                                } for s in data['sources']])
                    except:
                        pass
        
        return sources
    
    def extract_fallback_sources(self, html: str) -> List[Dict]:
        """Fallback extraction methods"""
        sources = []
        
        # HLS/M3U8 streams
        hls_matches = re.findall(r'(https?://[^\s<>"\']+\.m3u8[^\s<>"\']*)', html)
        for url in hls_matches:
            sources.append({"file": url, "label": "HLS", "type": "m3u8"})
        
        # MP4 streams
        mp4_matches = re.findall(r'(https?://[^\s<>"\']+\.mp4[^\s<>"\']*)', html)
        for url in mp4_matches:
            sources.append({"file": url, "label": "MP4", "type": "mp4"})
        
        return sources[:5]  # Limit
    
    async def extract_subtitles(self, player_url: str, client: httpx.AsyncClient) -> List[Dict]:
        """Extract subtitles"""
        try:
            resp = await client.get(player_url)
            subs = re.findall(r'(https?://[^\s<>"\']+\.(?:vtt|srt)[^\s<>"\']*)', resp.text)
            return [{"file": sub, "label": "English"} for sub in subs[:3]]
        except:
            return []
