"""
Terabox API - Using UdayScriptsX Workers API (FIXED URL Handling)
"""

import requests
import logging
import re
from urllib.parse import urlparse
from typing import Dict, List

logger = logging.getLogger(__name__)

class TeraboxAPI:
    def __init__(self):
        """Initialize with basic headers"""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }

    def extract_data(self, url: str, video_quality: str = "HD Video") -> Dict:
        """
        Extract Terabox file info using UdayScriptsX API
        """
        # Validate URL
        pattern = r"/s/(\w+)|surl=(\w+)|terabox|1024tera"
        if not re.search(pattern, url, re.IGNORECASE):
            raise Exception("ERROR: Invalid terabox URL")
        
        logger.info(f"🔍 Extracting from: {url}")
        
        # FIXED: Convert URL properly - only change domain, not subdomain
        netloc = urlparse(url).netloc
        
        # Convert various Terabox domains to 1024tera.com
        if "terabox" in netloc.lower():
            # terabox.com -> 1024tera.com
            # www.terabox.com -> 1024tera.com  
            # 1024terabox.com -> 1024tera.com
            converted_url = url.replace(netloc, "1024tera.com")
        else:
            # Already in correct format
            converted_url = url
            
        logger.info(f"🔄 Converted URL: {converted_url}")
        
        try:
            # Call UdayScriptsX API
            api_url = f"https://terabox.udayscriptsx.workers.dev/?url={converted_url}"
            logger.info(f"🌐 Calling API: {api_url}")
            
            response = requests.get(api_url, headers=self.headers, timeout=30)
            
            logger.info(f"📊 API Response: HTTP {response.status_code}")
            
            if response.status_code != 200:
                # Log response body for debugging
                try:
                    error_data = response.text
                    logger.error(f"API Error Response: {error_data}")
                except:
                    pass
                raise Exception(f"API returned HTTP {response.status_code}")
            
            data = response.json()
            logger.info(f"📄 Response data: {data}")
            
            # Parse response
            files = []
            
            # UdayScriptsX returns: {file_name, direct_link, size, link, thumb, sizebytes}
            download_url = data.get("direct_link") or data.get("link")
            
            if not download_url:
                raise Exception(f"No download link found in API response: {data}")
            
            files.append({
                "name": data.get("file_name", "Terabox File"),
                "size": data.get("size", "Unknown"),
                "download_url": download_url
            })
            
            logger.info(f"✅ SUCCESS! Found file: {data.get('file_name', 'Unknown')}")
            return {"files": files}
            
        except Exception as e:
            error_msg = f"Terabox extraction failed: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)


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
            
