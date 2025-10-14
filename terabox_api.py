"""
Terabox API - Based on Z-Mirror Implementation + WDZone
Uses Cloudflare Workers + Vercel (ALL FREE APIs)
https://github.com/Dawn-India/Z-Mirror
"""

import requests
import logging
import re
from urllib.parse import urlparse
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class TeraboxAPI:
    def __init__(self):
        """Initialize with 4 FREE APIs for maximum reliability"""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/json",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        }
    
    def extract_data(self, url: str, video_quality: str = "HD Video") -> Dict:
        """
        Extract Terabox file info using 4 fallback APIs
        
        Args:
            url: Terabox share URL
            video_quality: Preferred quality (HD Video, Fast Download, etc.)
        
        Returns:
            Dict with files list containing name, size, and download_url
        """
        
        # Step 1: Validate URL
        pattern = r"/s/(\w+)|sur1=(\w+)"
        if not re.search(pattern, url):
            raise Exception("ERROR: Invalid terabox URL")
        
        logger.info(f"🔍 Extracting from: {url}")
        
        # Step 2: Replace domain with 1024tera.com (Z-Mirror method)
        netloc = urlparse(url).netloc
        terabox_url = url.replace(netloc, "1024tera.com")
        
        logger.info(f"🔄 Converted URL: {terabox_url}")
        
        # Step 3: Try 4 APIs in order (Z-Mirror + WDZone)
        apis = [
            {
                "name": "SaveTube",
                "url": "https://ytshorts.savetube.me/api/v1/terabox-downloader",
                "method": "POST",
                "payload": {"url": terabox_url}
            },
            {
                "name": "NepCoderDevs",
                "url": f"https://teraboxvideodownloader.nepcoderdevs.workers.dev/?url={terabox_url}",
                "method": "GET",
                "payload": None
            },
            {
                "name": "UdayScriptsX",
                "url": f"https://terabox.udayscriptsx.workers.dev/?url={terabox_url}",
                "method": "GET",
                "payload": None
            },
            {
                "name": "WDZone",
                "url": "https://wdzone-terabox-api.vercel.app/api",
                "method": "POST",
                "payload": {"url": url}  # WDZone uses original URL, not converted
            }
        ]
        
        last_error = None
        
        for api in apis:
            try:
                logger.info(f"🌐 Trying API: {api['name']}")
                
                if api["method"] == "POST":
                    response = requests.post(
                        api["url"],
                        headers=self.headers,
                        json=api["payload"],
                        timeout=30
                    )
                else:  # GET
                    response = requests.get(
                        api["url"],
                        timeout=30
                    )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"📄 {api['name']} Response: {data}")
                    
                    # Check for error responses
                    if self._is_error_response(data):
                        logger.warning(f"⚠️ {api['name']}: Error in response - {data}")
                        continue
                    
                    # Parse the response
                    files = self._parse_response(data, video_quality, api["name"])
                    
                    if files:
                        logger.info(f"✅ SUCCESS with {api['name']}!")
                        return {"files": files}
                    else:
                        logger.warning(f"⚠️ {api['name']}: No files found in response")
                        
            except Exception as e:
                last_error = str(e)
                logger.warning(f"❌ {api['name']} failed: {e}")
                continue
        
        # All APIs failed
        error_msg = f"All Terabox APIs failed! Last error: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    def _is_error_response(self, data: Dict) -> bool:
        """Check if response contains error"""
        if isinstance(data, dict):
            # WDZone error format
            if "❌ Status" in data and data["❌ Status"] == "Error":
                return True
            # Generic error format
            if "status" in data and data["status"] == "error":
                return True
            if "error" in data:
                return True
        return False
    
    def _parse_response(self, data: Dict, video_quality: str, api_name: str) -> List[Dict]:
        """Parse API response and extract file info"""
        files = []
        
        try:
            # WDZone format
            if api_name == "WDZone":
                if "✅ Status" in data and data["✅ Status"] == "Success":
                    extracted_info = data.get("📜 Extracted Info")
                    if extracted_info and isinstance(extracted_info, list):
                        for item in extracted_info:
                            files.append({
                                "name": item.get("📄 File Name", "Terabox File"),
                                "size": item.get("📦 File Size", "Unknown"),
                                "download_url": item.get("🔗 Direct Download Link")
                            })
            
            # Format 1: Direct response list (SaveTube)
            elif isinstance(data, dict) and "response" in data:
                response_data = data["response"]
                if isinstance(response_data, list):
                    for item in response_data:
                        file_info = self._extract_file_info(item, video_quality)
                        if file_info:
                            files.append(file_info)
            
            # Format 2: Single file with resolutions
            elif isinstance(data, dict) and "resolutions" in data:
                file_info = self._extract_file_info(data, video_quality)
                if file_info:
                    files.append(file_info)
            
            # Format 3: Direct download_url
            elif isinstance(data, dict) and "download_url" in data:
                files.append({
                    "name": data.get("file_name", "Terabox File"),
                    "size": data.get("file_size", "Unknown"),
                    "download_url": data["download_url"]
                })
            
            # Format 4: Nested data structure
            elif isinstance(data, dict) and "data" in data:
                data_content = data["data"]
                if isinstance(data_content, list):
                    for item in data_content:
                        file_info = self._extract_file_info(item, video_quality)
                        if file_info:
                            files.append(file_info)
        
        except Exception as e:
            logger.error(f"❌ Error parsing response: {e}")
        
        return files
    
    def _extract_file_info(self, item: Dict, preferred_quality: str) -> Optional[Dict]:
        """Extract file info from a single item"""
        try:
            # Check if item has resolutions
            if "resolutions" in item:
                resolutions = item["resolutions"]
                
                # Try to get preferred quality
                download_url = resolutions.get(preferred_quality)
                
                # Fallback to available qualities
                if not download_url:
                    for quality in ["HD Video", "Fast Download", "SD Video"]:
                        download_url = resolutions.get(quality)
                        if download_url:
                            break
                
                if download_url:
                    return {
                        "name": item.get("title", "Terabox File"),
                        "size": item.get("size", "Unknown"),
                        "download_url": download_url
                    }
            
            # Direct URL in item
            elif "url" in item:
                return {
                    "name": item.get("title") or item.get("filename", "Terabox File"),
                    "size": item.get("size", "Unknown"),
                    "download_url": item["url"]
                }
        
        except Exception as e:
            logger.error(f"❌ Error extracting file info: {e}")
        
        return None
    
