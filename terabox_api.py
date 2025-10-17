"""
Terabox API - Updated Implementation with Working APIs (October 2025)
"""

import requests
import logging
import re
import time
from urllib.parse import urlparse
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class TeraboxAPI:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def extract_data(self, url: str) -> Dict:
        """Extract Terabox file info using multiple fallback APIs"""
        
        # Step 1: Validate URL and convert to supported domain
        pattern = r"/s/(\w+)|surl=(\w+)|terabox|1024tera"
        if not re.search(pattern, url, re.IGNORECASE):
            raise Exception("ERROR: Invalid terabox URL")
        
        # Convert to 1024tera.com (more reliable)
        netloc = urlparse(url).netloc
        url = url.replace(netloc, "1024tera.com")
        
        logger.info(f"🔍 Processing URL: {url}")
        
        # Step 2: Try to get initial page cookies
        try:
            response = self.session.get(url, timeout=30)
            logger.info(f"Initial page status: {response.status_code}")
        except Exception as e:
            logger.warning(f"Failed to fetch initial page: {e}")

        # Step 3: Try multiple APIs with detailed error logging
        apis = [
            {
                "name": "TeraAPI_1",
                "url": "https://tera-box-api.vercel.app/api/terabox",
                "method": "POST",
                "payload": {"url": url}
            },
            {
                "name": "TeraAPI_2", 
                "url": f"https://terabox-app-dl.herokuapp.com/download?url={url}",
                "method": "GET"
            },
            {
                "name": "TeraAPI_3",
                "url": f"https://terabox-dl.loadbt.com/api/v1/terabox?url={url}",
                "method": "GET"
            },
            {
                "name": "TeraAPI_4",
                "url": "https://terabox-dl-api.tdrcloud.workers.dev/api/v1/links/process",
                "method": "POST",
                "payload": {"link": url}
            }
        ]

        last_error = None
        for api in apis:
            try:
                logger.info(f"🌐 Trying {api['name']}...")
                
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
                
                # Log detailed response info
                logger.info(f"Response Status [{api['name']}]: {response.status_code}")
                logger.debug(f"Response Headers [{api['name']}]: {dict(response.headers)}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        logger.debug(f"Response Data [{api['name']}]: {data}")
                        
                        # Check for API-specific error responses
                        if self._is_error_response(data):
                            error_msg = self._get_error_message(data)
                            logger.warning(f"{api['name']} returned error: {error_msg}")
                            last_error = f"{api['name']}: {error_msg}"
                            continue
                        
                        files = self._parse_response(data)
                        if files:
                            logger.info(f"✅ Successfully extracted data with {api['name']}")
                            return {"files": files}
                        else:
                            last_error = f"{api['name']}: No valid files found in response"
                            
                    except Exception as e:
                        logger.error(f"Failed to parse {api['name']} response: {str(e)}")
                        last_error = f"{api['name']} parse error: {str(e)}"
                else:
                    logger.warning(f"{api['name']} returned status {response.status_code}")
                    last_error = f"{api['name']}: HTTP {response.status_code}"
                    
                # Add delay between requests
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error with {api['name']}: {str(e)}")
                last_error = f"{api['name']} request error: {str(e)}"
                continue

        error_msg = f"All Terabox APIs failed! Last error: {last_error if last_error else 'Unknown error'}"
        logger.error(error_msg)
        raise Exception(error_msg)

    def _is_error_response(self, data: Dict) -> bool:
        """Check various error response formats"""
        if isinstance(data, dict):
            # Check common error indicators
            if data.get("status") == "error":
                return True
            if data.get("error"):
                return True
            if data.get("success") is False:
                return True
            if "message" in data and "error" in data.get("message", "").lower():
                return True
        return False

    def _get_error_message(self, data: Dict) -> str:
        """Extract error message from response"""
        if isinstance(data, dict):
            return (data.get("error") or 
                   data.get("message") or 
                   data.get("msg") or 
                   "Unknown error")
        return str(data)

    def _parse_response(self, data: Dict) -> List[Dict]:
        """Parse API response with support for multiple formats"""
        files = []
        
        try:
            # Direct download URL
            if isinstance(data, str) and (data.startswith("http://") or data.startswith("https://")):
                return [{"name": "Terabox File", "size": "Unknown", "download_url": data}]
            
            # Standard response format
            if data.get("status") == "success" or data.get("success"):
                file_data = data.get("data", data)
                
                # Handle list response
                if isinstance(file_data, list):
                    file_data = file_data[0] if file_data else {}
                
                download_url = (file_data.get("direct_download_link") or 
                              file_data.get("direct_link") or 
                              file_data.get("download_url") or
                              file_data.get("url"))
                
                if download_url:
                    files.append({
                        "name": file_data.get("filename", "Terabox File"),
                        "size": file_data.get("size", "Unknown"),
                        "download_url": download_url
                    })
            
            # Alternative response formats
            elif "download_url" in data or "direct_link" in data:
                download_url = data.get("download_url") or data.get("direct_link")
                files.append({
                    "name": data.get("file_name", "Terabox File"),
                    "size": data.get("file_size", "Unknown"),
                    "download_url": download_url
                })
                
        except Exception as e:
            logger.error(f"Parse error: {e}")
            raise Exception(f"Failed to parse API response: {str(e)}")
        
        return files

def extract_terabox_data(url: str) -> Dict:
    """Wrapper function for backward compatibility"""
    api = TeraboxAPI()
    return api.extract_data(url)

def format_size(size_input) -> str:
    """Format size to human readable string"""
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
