"""
Terabox API - Based on Z-Mirror Implementation + WDZone
Uses 4 FREE APIs with proper response parsing for all formats
GitHub: https://github.com/Dawn-India/Z-Mirror
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
        
        # Step 3: Try 5 APIs in order (NEW + Z-Mirror + WDZone)
        apis = [
            # NEW: Working API added first
            {
                "name": "TeraboxAPI_Pro",
                "url": "https://terabox-dl.qtcloud.workers.dev/api/get-info",
                "method": "POST",
                "payload": {"url": url}
            },
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
                "payload": {"url": url}  # WDZone uses original URL
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
                    # ENHANCED: Better logging
                    logger.info(f"📄 {api['name']} Full Response: {data}")
                    logger.info(f"🔑 Response Keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                    
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
                        # ENHANCED: Better debugging when no files found
                        logger.warning(f"⚠️ {api['name']}: No files found in response")
                        logger.warning(f"📊 Response structure: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                        if isinstance(data, dict) and len(data) > 0:
                            sample = {k: v for k, v in list(data.items())[:3]}
                            logger.warning(f"📝 Sample data: {sample}")
                        
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
            # Generic error formats
            if "status" in data and data["status"] == "error":
                return True
            if "error" in data:
                return True
        return False

    def _parse_response(self, data: Dict, video_quality: str, api_name: str) -> List[Dict]:
        """Parse API response and extract file info - FIXED FOR ALL FORMATS"""
        files = []
        
        try:
            # NEW: TeraboxAPI_Pro format
            if api_name == "TeraboxAPI_Pro":
                if "ok" in data and data.get("ok") == True:
                    file_list = data.get("list", [])
                    for item in file_list:
                        dlink = item.get("dlink")
                        if dlink:
                            files.append({
                                "name": item.get("filename", "Terabox File"),
                                "size": format_size(item.get("size", 0)),
                                "download_url": dlink
                            })
            
            # WDZone format (emoji keys)
            elif api_name == "WDZone":
                if "✅ Status" in data and data["✅ Status"] == "Success":
                    extracted_info = data.get("📜 Extracted Info")
                    if extracted_info and isinstance(extracted_info, list):
                        for item in extracted_info:
                            download_url = item.get("🔗 Direct Download Link")
                            if download_url:
                                files.append({
                                    "name": item.get("📄 File Name", "Terabox File"),
                                    "size": item.get("📦 File Size", "Unknown"),
                                    "download_url": download_url
                                })
            
            # NepCoderDevs / UdayScriptsX format (FIXED!)
            elif api_name in ["NepCoderDevs", "UdayScriptsX"]:
                # These APIs return: {file_name, direct_link, size, link, thumb, sizebytes}
                if "direct_link" in data and data.get("direct_link"):
                    files.append({
                        "name": data.get("file_name", "Terabox File"),
                        "size": data.get("size", "Unknown"),
                        "download_url": data["direct_link"]
                    })
                # Fallback to "link" if direct_link not present
                elif "link" in data and data.get("link"):
                    files.append({
                        "name": data.get("file_name", "Terabox File"),
                        "size": data.get("size", "Unknown"),
                        "download_url": data["link"]
                    })
            
            # SaveTube format (response list)
            elif isinstance(data, dict) and "response" in data:
                response_data = data["response"]
                if isinstance(response_data, list):
                    for item in response_data:
                        file_info = self._extract_file_info(item, video_quality)
                        if file_info:
                            files.append(file_info)
            
            # Resolutions format
            elif isinstance(data, dict) and "resolutions" in data:
                file_info = self._extract_file_info(data, video_quality)
                if file_info:
                    files.append(file_info)
            
            # Generic download_url format
            elif isinstance(data, dict) and "download_url" in data:
                files.append({
                    "name": data.get("file_name", "Terabox File"),
                    "size": data.get("file_size", "Unknown"),
                    "download_url": data["download_url"]
                })
            
            # Nested data structure
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


# ===== BACKWARD COMPATIBILITY FUNCTIONS =====
# These allow old code to still work with new class structure

def extract_terabox_data(url: str) -> Dict:
    """
    Backward compatibility wrapper for old imports
    Usage: from terabox_api import extract_terabox_data
    """
    api = TeraboxAPI()
    return api.extract_data(url)

def format_size(size_input) -> str:
    """
    Format bytes to human readable size
    Handles both int and string inputs (e.g., "18.08 MB")
    """
    try:
        # If it's already a formatted string (e.g., "125 MB"), return as-is
        if isinstance(size_input, str):
            if any(unit in size_input.upper() for unit in ['B', 'KB', 'MB', 'GB', 'TB']):
                return size_input
            # Try to convert string to int
            try:
                size_input = int(size_input)
            except:
                return str(size_input)
        
        # Convert to int
        size_bytes = int(size_input)
        
        # Format to human readable
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        
        return f"{size_bytes:.2f} PB"
    except:
        return str(size_input)
                            
