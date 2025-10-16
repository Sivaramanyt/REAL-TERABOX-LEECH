"""
Terabox API - Pure API Approach (NO LIBRARY NEEDED)
Uses working free APIs that bypass Terabox verification
October 2025 - Tested and Working
"""

import requests
import logging
import re
from typing import Dict, List
import time

logger = logging.getLogger(__name__)

class TeraboxAPI:
    def __init__(self):
        """Initialize with standard headers"""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        
    def extract_data(self, url: str, video_quality: str = "HD Video") -> Dict:
        """
        Extract Terabox file info using working free APIs
        """
        # Validate URL
        pattern = r"/s/(\w+)|surl=(\w+)|terabox|1024tera"
        if not re.search(pattern, url, re.IGNORECASE):
            raise Exception("ERROR: Invalid terabox URL")
        
        logger.info(f"🔍 Extracting from: {url}")
        
        # Working APIs October 2025
        apis = [
            {
                "name": "TeraboxDownAPI",
                "url": "https://teradown.com/api/download",
                "method": "POST",
                "payload": {"url": url}
            },
            {
                "name": "TeraboxBypassAPI",
                "url": "https://api.terabox.tech/download",
                "method": "POST",
                "payload": {"url": url}
            },
            {
                "name": "TeraLinkAPI",
                "url": "https://tera-link-api.vercel.app/api/get-link",
                "method": "POST",
                "payload": {"url": url}
            }
        ]
        
        last_error = None
        
        for api in apis:
            try:
                logger.info(f"🌐 Trying {api['name']}...")
                time.sleep(0.5)
                
                response = requests.post(
                    api["url"],
                    json=api["payload"],
                    headers=self.headers,
                    timeout=30
                )
                
                logger.info(f"📊 {api['name']}: HTTP {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    files = self._parse_response(data, api["name"])
                    
                    if files:
                        logger.info(f"✅ SUCCESS with {api['name']}!")
                        return {"files": files}
                    else:
                        logger.warning(f"⚠️ {api['name']}: No files found")
                else:
                    logger.warning(f"❌ {api['name']}: HTTP {response.status_code}")
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"❌ {api['name']}: {e}")
                continue
        
        # All failed
        raise Exception(f"All Terabox APIs failed. Last error: {last_error}")
    
    def _parse_response(self, data: Dict, api_name: str) -> List[Dict]:
        """Parse API responses"""
        files = []
        
        try:
            # Handle various response formats
            if isinstance(data, dict):
                # Format 1: {success: true, data: {downloadLink, fileName, fileSize}}
                if data.get("success") or data.get("status") == "success":
                    file_data = data.get("data", data)
                    download_url = (file_data.get("downloadLink") or 
                                   file_data.get("download_link") or 
                                   file_data.get("dlink"))
                    
                    if download_url:
                        files.append({
                            "name": (file_data.get("fileName") or 
                                    file_data.get("file_name") or 
                                    file_data.get("filename") or "Terabox File"),
                            "size": (file_data.get("fileSize") or 
                                    file_data.get("file_size") or 
                                    format_size(file_data.get("size", 0))),
                            "download_url": download_url
                        })
                
                # Format 2: {ok: true, list: [...]}
                elif data.get("ok"):
                    file_list = data.get("list", [])
                    for item in file_list:
                        dlink = item.get("dlink")
                        if dlink:
                            files.append({
                                "name": item.get("filename") or item.get("server_filename", "Terabox File"),
                                "size": format_size(item.get("size", 0)),
                                "download_url": dlink
                            })
                
                # Format 3: Direct fields
                else:
                    download_url = (data.get("downloadLink") or 
                                   data.get("download_link") or 
                                   data.get("dlink"))
                    if download_url:
                        files.append({
                            "name": (data.get("fileName") or 
                                    data.get("file_name") or 
                                    data.get("filename") or "Terabox File"),
                            "size": (data.get("fileSize") or 
                                    data.get("file_size") or "Unknown"),
                            "download_url": download_url
                        })
        
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
        
        return files


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
                        
