"""
Terabox API - Using Working Community APIs (October 2025)
Bypasses Terabox's verify_v2 requirement
"""

import requests
import logging
import re
from typing import Dict, List
import json

logger = logging.getLogger(__name__)

class TeraboxAPI:
    def __init__(self):
        """Initialize with working bypass APIs"""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        
    def extract_data(self, url: str, video_quality: str = "HD Video") -> Dict:
        """
        Extract Terabox file info using bypass APIs
        """
        try:
            logger.info(f"🔍 Processing Terabox URL: {url}")
            
            # Try multiple working APIs
            apis = [
                {
                    "name": "Terabox Bypass API v1",
                    "url": "https://teradl-api.deno.dev/download",
                    "method": "POST",
                    "payload": {"url": url}
                },
                {
                    "name": "Terabox Bypass API v2", 
                    "url": "https://terabox-dl-v2.vercel.app/api",
                    "method": "POST",
                    "payload": {"url": url}
                },
                {
                    "name": "Terabox Bypass API v3",
                    "url": "https://terabox-api-rust.vercel.app/api/download",
                    "method": "POST",
                    "payload": {"link": url}
                }
            ]
            
            for api in apis:
                try:
                    logger.info(f"🌐 Trying {api['name']}...")
                    
                    response = requests.post(
                        api["url"],
                        json=api["payload"],
                        headers=self.headers,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        logger.info(f"📄 Response from {api['name']}: {json.dumps(data)[:200]}...")
                        
                        # Parse different response formats
                        files = self._parse_response(data, api["name"])
                        
                        if files:
                            logger.info(f"✅ SUCCESS with {api['name']}!")
                            return {"files": files}
                    else:
                        logger.warning(f"❌ {api['name']}: HTTP {response.status_code}")
                        
                except Exception as e:
                    logger.warning(f"❌ {api['name']} failed: {e}")
                    continue
            
            # All APIs failed
            raise Exception("All Terabox APIs failed. The link may be invalid or expired.")
            
        except Exception as e:
            error_msg = f"Terabox extraction failed: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def _parse_response(self, data: Dict, api_name: str) -> List[Dict]:
        """Parse API responses"""
        files = []
        
        try:
            # Format 1: {success: true, data: {download_link, file_name, size}}
            if isinstance(data, dict) and data.get("success"):
                file_data = data.get("data", {})
                download_url = file_data.get("download_link") or file_data.get("downloadLink") or file_data.get("dlink")
                if download_url:
                    files.append({
                        "name": file_data.get("file_name") or file_data.get("fileName", "Terabox File"),
                        "size": format_size(file_data.get("size", 0)),
                        "download_url": download_url
                    })
            
            # Format 2: {ok: true, list: [{dlink, filename, size}]}
            elif isinstance(data, dict) and data.get("ok"):
                file_list = data.get("list", [])
                for item in file_list:
                    dlink = item.get("dlink")
                    if dlink:
                        files.append({
                            "name": item.get("filename") or item.get("server_filename", "Terabox File"),
                            "size": format_size(item.get("size", 0)),
                            "download_url": dlink
                        })
            
            # Format 3: Direct format {downloadLink, fileName, fileSize}
            elif isinstance(data, dict):
                download_url = data.get("downloadLink") or data.get("download_link") or data.get("dlink")
                if download_url:
                    files.append({
                        "name": data.get("fileName") or data.get("file_name") or data.get("filename", "Terabox File"),
                        "size": data.get("fileSize") or data.get("file_size") or format_size(data.get("size", 0)),
                        "download_url": download_url
                    })
            
            # Format 4: Array of files
            elif isinstance(data, list):
                for item in data:
                    download_url = item.get("downloadLink") or item.get("download_link") or item.get("dlink")
                    if download_url:
                        files.append({
                            "name": item.get("fileName") or item.get("file_name") or item.get("filename", "Terabox File"),
                            "size": format_size(item.get("size", 0)),
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
                    
