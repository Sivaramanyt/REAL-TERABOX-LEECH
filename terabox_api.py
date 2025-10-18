"""
Terabox API - Based on SudoR2spr's Working Method (June 2025)
GitHub: https://github.com/SudoR2spr/Terabox-API
This method scrapes tokens from HTML and uses official Terabox API
"""
import requests
import logging
import re
import json
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class TeraboxAPI:
    def __init__(self):
        """Initialize with SudoR2spr's working cookies and config"""
        # Working cookies from SudoR2spr (updated June 23, 2025)
        self.cookies = {
            'ndus': 'Y-wWXKyteHuigAhC03Fr4bbee-QguZ4JC6UAdqap',
            'browserid': 'veWFJBJ9hgVgY0eI9S7yzv66aE28f3als3qUXadSjEuICKF1WWBh4inG3KAWJsAYMkAFpH2FuNUum87q',
            'csrfToken': 'wlv_WNcWCjBtbNQDrHSnut2h',
            'lang': 'en'
        }
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.1024tera.com/',
            'Origin': 'https://www.1024tera.com'
        }
        
        self.max_retries = 3
        self.retry_delay = 2
        
    def extract_data(self, url: str, video_quality: str = "HD Video") -> Dict:
        """
        Extract Terabox file info using SudoR2spr's method
        Args:
            url: Terabox share URL
            video_quality: Preferred quality (not used in this method)
        Returns:
            Dict with files list containing name, size, and download_url
        """
        logger.info(f"🔍 Extracting from: {url}")
        
        # Step 1: Convert to 1024tera.com domain
        url = self._convert_url(url)
        logger.info(f"🔄 Converted URL: {url}")
        
        # Step 2: Extract shorturl from URL
        shorturl = self._extract_shorturl(url)
        if not shorturl:
            raise Exception("Could not extract shorturl from URL")
        
        logger.info(f"🔑 Shorturl: {shorturl}")
        
        # Step 3: Get HTML page and extract tokens
        logger.info("📄 Fetching page to extract tokens...")
        tokens = self._extract_tokens_from_html(url)
        
        if not tokens:
            raise Exception("Failed to extract tokens from page")
        
        logger.info(f"✅ Extracted tokens: jsToken={tokens['jsToken'][:20]}..., logid={tokens['logid']}")
        
        # Step 4: Call Terabox API with tokens
        logger.info("🌐 Calling Terabox API...")
        files = self._get_file_list(shorturl, tokens)
        
        if files:
            logger.info(f"✅ SUCCESS! Found {len(files)} file(s)")
            return {"files": files}
        else:
            raise Exception("No files found in response")
    
    def _convert_url(self, url: str) -> str:
        """Convert any Terabox domain to 1024tera.com"""
        supported_domains = [
            'terabox.com', '1024terabox.com', 'teraboxapp.com',
            'teraboxlink.com', 'terasharelink.com', 'terafileshare.com',
            'teraboxdrive.com', 'dubox.com', '1024tera.cn'
        ]
        
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        
        if domain in supported_domains or '1024tera.com' in domain:
            # Replace domain with 1024tera.com
            return url.replace(parsed.netloc, '1024tera.com')
        
        return url
    
    def _extract_shorturl(self, url: str) -> Optional[str]:
        """Extract shorturl from Terabox URL"""
        patterns = [
            r'/s/([A-Za-z0-9_-]+)',
            r'/sharing/link\?surl=([A-Za-z0-9_-]+)',
            r'surl=([A-Za-z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_tokens_from_html(self, url: str) -> Optional[Dict]:
        """Extract jsToken and logid from HTML page"""
        try:
            response = requests.get(url, headers=self.headers, cookies=self.cookies, timeout=30)
            
            if response.status_code != 200:
                logger.warning(f"⚠️ HTML fetch returned status {response.status_code}")
                return None
            
            html = response.text
            
            # Extract jsToken
            js_token_match = re.search(r'window\.jsToken\s*=\s*"([^"]+)"', html)
            if not js_token_match:
                js_token_match = re.search(r'jsToken":\s*"([^"]+)"', html)
            
            # Extract logid
            logid_match = re.search(r'logid":\s*"([^"]+)"', html)
            if not logid_match:
                logid_match = re.search(r'window\.logid\s*=\s*"([^"]+)"', html)
            
            if js_token_match and logid_match:
                return {
                    'jsToken': js_token_match.group(1),
                    'logid': logid_match.group(1)
                }
            else:
                logger.warning("⚠️ Could not extract tokens from HTML")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error extracting tokens: {e}")
            return None
    
    def _get_file_list(self, shorturl: str, tokens: Dict) -> List[Dict]:
        """Get file list from Terabox API using tokens"""
        api_url = "https://www.1024tera.com/share/list"
        
        params = {
            'shorturl': shorturl,
            'root': '1',
            'jsToken': tokens['jsToken'],
            'web': '1',
            'channel': 'dubox',
            'app_id': '250528',
            'clienttype': '0'
        }
        
        # Add cookies to headers
        headers = self.headers.copy()
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"🔄 API attempt {attempt + 1}/{self.max_retries}")
                
                response = requests.get(
                    api_url,
                    params=params,
                    headers=headers,
                    cookies=self.cookies,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    errno = data.get('errno', -1)
                    logger.info(f"📡 API Response: errno={errno}")
                    
                    if errno == 0:
                        file_list = data.get('list', [])
                        
                        if file_list:
                            files = []
                            for file_info in file_list:
                                # Get download link
                                dlink = file_info.get('dlink', '')
                                
                                if dlink:
                                    files.append({
                                        'name': file_info.get('server_filename', 'Terabox File'),
                                        'size': self._format_size(file_info.get('size', 0)),
                                        'download_url': dlink
                                    })
                            
                            return files
                        else:
                            logger.warning("⚠️ Empty file list in response")
                    else:
                        logger.warning(f"⚠️ API returned errno: {errno}")
                
                # Rate limit - wait before retry
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    
            except Exception as e:
                logger.error(f"❌ API call error: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        
        return []
    
    def _format_size(self, size_bytes):
        """Format bytes to human readable size"""
        try:
            size_bytes = int(size_bytes)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.2f} PB"
        except:
            return "Unknown"

# ===== BACKWARD COMPATIBILITY FUNCTIONS =====

def extract_terabox_data(url: str) -> Dict:
    """Backward compatibility wrapper"""
    api = TeraboxAPI()
    return api.extract_data(url)

def format_size(size_input) -> str:
    """Format bytes to human readable size"""
    try:
        if isinstance(size_input, str):
            if any(unit in size_input.upper() for unit in ['B', 'KB', 'MB', 'GB', 'TB']):
                return size_input
            try:
                size_input = int(size_input)
            except:
                return str(size_input)
        
        size_bytes = int(size_input)
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    except:
        return str(size_input)
        
