"""
Terabox API - Based on Z-Mirror Implementation + WDZone + TeraDL
Uses 4 FREE APIs + TeraDL API (Most Starred - 150 stars) for maximum reliability
GitHub: https://github.com/Dawn-India/Z-Mirror
TeraDL: https://github.com/Dapunta/TeraDL
"""
import requests
import logging
import re
import json
from urllib.parse import urlparse
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class TeraboxAPI:
    def __init__(self):
        """Initialize with 5 APIs for maximum reliability"""
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
        Extract Terabox file info using 4 APIs + TeraDL (Most Reliable)
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
        
        # NEW: Try TeraDL API as final fallback (Most Reliable - 150 stars!)
        try:
            logger.info("🌟 Trying TeraDL API (Dapunta - Most Starred & Reliable)")
            
            teradl_url = "https://teradl.dapuntaratya.com/api"
            
            payload = {
                "url": url  # Use original URL
            }
            
            teradl_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            response = requests.post(teradl_url, json=payload, headers=teradl_headers, timeout=30)
            
            logger.info(f"📡 TeraDL Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"📄 TeraDL Response: {data}")
                
                # Parse TeraDL response - flexible parsing for different formats
                download_url = None
                file_name = "Terabox File"
                file_size = "Unknown"
                
                # Try different response structures
                if isinstance(data, dict):
                    # Format 1: {status: success, data: {...}}
                    if data.get('status') == 'success' and 'data' in data:
                        file_data = data['data']
                        download_url = file_data.get('download_url') or file_data.get('url') or file_data.get('dlink')
                        file_name = file_data.get('file_name') or file_data.get('filename') or file_data.get('title', 'Terabox File')
                        file_size = file_data.get('size') or file_data.get('filesize', 'Unknown')
                    
                    # Format 2: Direct data without status wrapper
                    elif 'download_url' in data or 'url' in data or 'dlink' in data:
                        download_url = data.get('download_url') or data.get('url') or data.get('dlink')
                        file_name = data.get('file_name') or data.get('filename') or data.get('title', 'Terabox File')
                        file_size = data.get('size') or data.get('filesize', 'Unknown')
                    
                    # Format 3: {result: {...}}
                    elif 'result' in data:
                        result = data['result']
                        download_url = result.get('download_url') or result.get('url') or result.get('dlink')
                        file_name = result.get('file_name') or result.get('filename') or result.get('title', 'Terabox File')
                        file_size = result.get('size') or result.get('filesize', 'Unknown')
                
                if download_url:
                    logger.info("✅ SUCCESS with TeraDL API!")
                    return {
                        "files": [{
                            "name": file_name,
                            "size": self._format_size(file_size) if isinstance(file_size, int) else file_size,
                            "download_url": download_url
                        }]
                    }
                else:
                    logger.warning("⚠️ TeraDL API: No download URL found in response")
            else:
                logger.warning(f"⚠️ TeraDL API returned status {response.status_code}")
                
        except Exception as e:
            last_error = str(e)
            logger.warning(f"❌ TeraDL API failed: {e}")
        
        # All methods failed
        error_msg = f"All Terabox methods failed! Last error: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
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
            # WDZone format (emoji keys)
            if api_name == "WDZone":
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
            
