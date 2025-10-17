"""
Enhanced Terabox API with browser emulation and improved error handling
"""

import requests
import logging
import re
import time
import random
from typing import Dict, List
from fake_useragent import UserAgent
from http.cookies import SimpleCookie

logger = logging.getLogger(__name__)

class TeraboxAPI:
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'TE': 'trailers'
        })
        
    def _rotate_user_agent(self):
        """Rotate user agent for each request"""
        self.session.headers['User-Agent'] = self.ua.random

    def _extract_cookies(self, response):
        """Extract and parse cookies from response"""
        cookies = SimpleCookie()
        if 'Set-Cookie' in response.headers:
            cookies.load(response.headers['Set-Cookie'])
            for key, morsel in cookies.items():
                self.session.cookies.set(key, morsel.value)

    def _add_delay(self):
        """Add random delay between requests"""
        time.sleep(random.uniform(2, 5))

    def extract_data(self, url: str) -> Dict:
        """Enhanced data extraction with better error handling"""
        
        pattern = r"/s/(\w+)|surl=(\w+)|terabox|1024tera"
        if not re.search(pattern, url, re.IGNORECASE):
            raise Exception("ERROR: Invalid terabox URL")
        
        logger.info(f"🔍 Processing Terabox URL: {url}")
        
        # First get the main page to establish cookies
        try:
            self._rotate_user_agent()
            response = self.session.get(url, timeout=30)
            self._extract_cookies(response)
            logger.debug(f"Initial page fetch status: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to fetch initial page: {e}")
            raise Exception(f"Initial page fetch failed: {str(e)}")

        self._add_delay()

        # APIs to try with better error logging
        apis = [
            {
                "name": "Direct_API",
                "url": f"https://www.terabox.com/api/download",
                "method": "POST",
                "payload": {"url": url, "type": "url"}
            },
            {
                "name": "NRBots_API_1",
                "url": f"https://terabox-dl.qtcloud.workers.dev/api/get-info",
                "method": "POST",
                "payload": {"url": url}
            },
            {
                "name": "NRBots_API_2", 
                "url": f"https://teraboxapp.wdshot.workers.dev/?url={url}",
                "method": "GET"
            },
            {
                "name": "Cloudflare_API",
                "url": f"https://terabox-api.pages.dev/api?url={url}",
                "method": "GET"
            }
        ]

        last_error = None
        for api in apis:
            try:
                logger.info(f"🌐 Trying {api['name']}...")
                self._rotate_user_agent()
                
                if api["method"] == "POST":
                    response = self.session.post(
                        api["url"],
                        json=api.get("payload"),
                        timeout=30
                    )
                else:
                    response = self.session.get(
                        api["url"],
                        timeout=30
                    )
                
                logger.debug(f"API Response Status: {response.status_code}")
                logger.debug(f"API Response Headers: {response.headers}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        files = self._parse_response(data)
                        if files:
                            logger.info(f"✅ Successfully extracted data with {api['name']}")
                            return {"files": files}
                    except Exception as e:
                        logger.error(f"Failed to parse {api['name']} response: {e}")
                        logger.debug(f"Response content: {response.text[:500]}...")
                        last_error = f"Parse error from {api['name']}: {str(e)}"
                else:
                    logger.warning(f"{api['name']} returned status {response.status_code}")
                    last_error = f"HTTP {response.status_code} from {api['name']}"
                
                self._add_delay()
                
            except Exception as e:
                logger.error(f"Error with {api['name']}: {e}")
                last_error = f"Request error with {api['name']}: {str(e)}"
                continue

        raise Exception(f"All APIs failed. Last error: {last_error}")

    def _parse_response(self, data: Dict) -> List[Dict]:
        """Enhanced response parser with better error handling"""
        files = []
        
        try:
            # Log the raw response for debugging
            logger.debug(f"Parsing response data: {data}")
            
            if isinstance(data, str):
                logger.warning("Received string instead of JSON, attempting to handle...")
                return [{"name": "Unknown", "size": "Unknown", "download_url": data}]
            
            # Format 1: Standard response
            if data.get("success") or data.get("ok"):
                file_list = data.get("list", [data])
                
                for item in file_list:
                    download_url = (item.get("direct_link") or 
                                  item.get("dlink") or 
                                  item.get("downloadLink") or 
                                  item.get("download_link") or
                                  item.get("link"))
                    
                    if download_url:
                        name = (item.get("file_name") or 
                               item.get("filename") or 
                               item.get("server_filename") or 
                               "Terabox File")
                        
                        size = item.get("size", "Unknown")
                        if isinstance(size, (int, float)):
                            size = self._format_size(size)
                        
                        files.append({
                            "name": name,
                            "size": size,
                            "download_url": download_url.replace('\\/', '/')
                        })
            
            # Format 2: Direct fields
            else:
                download_url = (data.get("direct_link") or 
                              data.get("dlink") or 
                              data.get("downloadLink") or
                              data.get("link"))
                
                if download_url:
                    files.append({
                        "name": (data.get("file_name") or 
                                data.get("filename") or 
                                "Terabox File"),
                        "size": data.get("size", "Unknown"),
                        "download_url": download_url.replace('\\/', '/')
                    })
        
        except Exception as e:
            logger.error(f"Parse error: {e}")
            logger.debug(f"Failed to parse data: {data}")
            raise Exception(f"Failed to parse API response: {str(e)}")
        
        return files

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

def extract_terabox_data(url: str) -> Dict:
    api = TeraboxAPI()
    return api.extract_data(url)
