"""
Terabox API - Working Implementation (October 2025)
Uses anasty17's method with multiple API fallbacks
"""

import requests
import logging
import re
import time
import json
from urllib.parse import urlparse, quote
from typing import Dict, List

logger = logging.getLogger(__name__)

class TeraboxAPI:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "DNT": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.terabox.com/"
        }
        self.session.headers.update(self.headers)

    def extract_data(self, url: str) -> Dict:
        """Extract Terabox file info using working APIs"""
        
        # Step 1: Validate URL
        pattern = r"/s/(\w+)|surl=(\w+)|terabox|1024tera"
        if not re.search(pattern, url, re.IGNORECASE):
            raise Exception("ERROR: Invalid terabox URL")

        # Step 2: Get share ID from URL
        share_id = re.search(r"[?&]surl=([^&]+)|/s/([^/]+)", url)
        if not share_id:
            raise Exception("ERROR: Could not extract share ID from URL")
        share_id = share_id.group(1) or share_id.group(2)

        # Step 3: Convert to supported domains
        domains = ["1024tera.com", "teraboxapp.com", "4funbox.com", "terabox.com"]
        urls = [f"https://www.{domain}/s/{share_id}" for domain in domains]
        
        logger.info(f"🔍 Processing share ID: {share_id}")

        # Step 4: Try multiple API endpoints
        apis = [
            {
                "name": "TeraAPI_1",
                "url": f"https://www.1024tera.com/api/share/download?shareid={share_id}",
                "method": "GET",
                "convert_url": False
            },
            {
                "name": "TeraAPI_2",
                "url": "https://terabox-dl.anasty17.workers.dev/api/json",
                "method": "POST",
                "payload": {"url": urls[0]},
                "convert_url": False
            },
            {
                "name": "TeraAPI_3",
                "url": "https://terabox-dl.nx.workers.dev/api/v2/links",
                "method": "POST", 
                "payload": {"link": urls[1]},
                "convert_url": False
            },
            {
                "name": "TeraAPI_4",
                "url": f"https://www.teraboxapp.com/share/download?surl={share_id}&pwd=",
                "method": "GET",
                "convert_url": False
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
                        timeout=30,
                        allow_redirects=True
                    )
                else:
                    response = self.session.get(
                        api["url"],
                        timeout=30,
                        allow_redirects=True
                    )
                
                logger.info(f"Response Status [{api['name']}]: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        logger.debug(f"Response Data [{api['name']}]: {data}")
                        
                        if not self._is_error_response(data):
                            files = self._parse_response(data, api["name"])
                            if files:
                                logger.info(f"✅ Success with {api['name']}")
                                return {"files": files}
                            else:
                                last_error = f"{api['name']}: No valid files found"
                        else:
                            error_msg = self._get_error_message(data)
                            logger.warning(f"{api['name']} returned error: {error_msg}")
                            last_error = f"{api['name']}: {error_msg}"
                            
                    except Exception as e:
                        logger.error(f"Failed to parse {api['name']} response: {str(e)}")
                        last_error = f"{api['name']} parse error: {str(e)}"
                else:
                    logger.warning(f"{api['name']} returned status {response.status_code}")
                    last_error = f"{api['name']}: HTTP {response.status_code}"
                
            except Exception as e:
                logger.error(f"Error with {api['name']}: {str(e)}")
                last_error = f"{api['name']} error: {str(e)}"
                continue

            time.sleep(2)  # Delay between APIs

        error_msg = f"All Terabox APIs failed! Last error: {last_error if last_error else 'Unknown error'}"
        logger.error(error_msg)
        raise Exception(error_msg)

    def _is_error_response(self, data: Dict) -> bool:
        """Check for error responses"""
        if isinstance(data, dict):
            # Check error indicators
            if data.get("errno", 0) != 0:
                return True
            if data.get("error"):
                return True
            if data.get("status") == "error":
                return True
            if data.get("success") is False:
                return True
        return False

    def _get_error_message(self, data: Dict) -> str:
        """Extract error message from response"""
        if isinstance(data, dict):
            return (data.get("errmsg") or 
                   data.get("error") or
                   data.get("message") or
                   "Unknown error")
        return str(data)

    def _parse_response(self, data: Dict, api_name: str) -> List[Dict]:
        """Parse API response based on API format"""
        files = []
        
        try:
            # Handle different API response formats
            if api_name == "TeraAPI_1":
                if "list" in data:
                    file_list = data["list"]
                    if isinstance(file_list, list) and file_list:
                        file_info = file_list[0]
                        download_url = file_info.get("dlink")
                        if download_url:
                            files.append({
                                "name": file_info.get("server_filename", "Terabox File"),
                                "size": self._format_size(file_info.get("size", 0)),
                                "download_url": download_url
                            })
                            
            elif api_name == "TeraAPI_2":
                download_url = data.get("download_url")
                if download_url:
                    files.append({
                        "name": data.get("filename", "Terabox File"),
                        "size": data.get("size", "Unknown"),
                        "download_url": download_url
                    })
                    
            elif api_name in ["TeraAPI_3", "TeraAPI_4"]:
                if "data" in data:
                    file_data = data["data"]
                    download_url = (file_data.get("redirect_url") or 
                                  file_data.get("download_url") or
                                  file_data.get("dlink"))
                    if download_url:
                        files.append({
                            "name": file_data.get("filename", "Terabox File"),
                            "size": file_data.get("size", "Unknown"),
                            "download_url": download_url
                        })
            
        except Exception as e:
            logger.error(f"Parse error for {api_name}: {e}")
            raise Exception(f"Failed to parse {api_name} response: {str(e)}")
        
        return files

    def _format_size(self, size_bytes: int) -> str:
        """Format size to human readable string"""
        try:
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.2f} PB"
        except:
            return "Unknown"

def extract_terabox_data(url: str) -> Dict:
    """Wrapper function for backward compatibility"""
    api = TeraboxAPI()
    return api.extract_data(url)
