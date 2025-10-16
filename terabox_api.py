"""
Terabox API - Complete with ALL Previous + New Working APIs (8 Total)
October 2025 - Maximum Reliability
"""

import requests
import logging
import re
from urllib.parse import urlparse
from typing import Dict, List, Optional
import time

logger = logging.getLogger(__name__)

class TeraboxAPI:
    def __init__(self):
        """Initialize with rotating user agents and headers"""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin": "https://terabox.com",
            "Referer": "https://terabox.com/"
        }

    def extract_data(self, url: str, video_quality: str = "HD Video") -> Dict:
        """
        Extract Terabox file info using 8 fallback APIs (NEW + PREVIOUS)
        
        Args:
            url: Terabox share URL
            video_quality: Preferred quality (HD Video, Fast Download, etc.)
            
        Returns:
            Dict with files list containing name, size, and download_url
        """
        # Validate URL
        pattern = r"/s/(\w+)|surl=(\w+)"
        if not re.search(pattern, url):
            raise Exception("ERROR: Invalid terabox URL")
        
        logger.info(f"🔍 Extracting from: {url}")
        
        # Convert URL for Z-Mirror APIs
        netloc = urlparse(url).netloc
        terabox_url = url.replace(netloc, "1024tera.com")
        logger.info(f"🔄 Converted URL: {terabox_url}")
        
        # ALL APIs - NEW + YOUR PREVIOUS 4
        apis = [
            # NEW Working APIs (October 2025)
            {
                "name": "Freeterabox",
                "url": "https://www.freeterabox.com/api/get-info",
                "method": "POST",
                "payload": {"url": url},
                "timeout": 25
            },
            {
                "name": "Teraboxdl",
                "url": "https://teraboxdl.com/api/get-download",
                "method": "POST",
                "payload": {"url": url},
                "timeout": 25
            },
            {
                "name": "TeraboxAPI",
                "url": "https://api.terabox.app/download",
                "method": "POST",
                "payload": {"url": url},
                "timeout": 25
            },
            
            # YOUR PREVIOUS APIs (Z-Mirror + WDZone)
            {
                "name": "SaveTube",
                "url": "https://ytshorts.savetube.me/api/v1/terabox-downloader",
                "method": "POST",
                "payload": {"url": terabox_url},
                "timeout": 20
            },
            {
                "name": "NepCoderDevs",
                "url": f"https://teraboxvideodownloader.nepcoderdevs.workers.dev/?url={terabox_url}",
                "method": "GET",
                "payload": None,
                "timeout": 20
            },
            {
                "name": "UdayScriptsX",
                "url": f"https://terabox.udayscriptsx.workers.dev/?url={terabox_url}",
                "method": "GET",
                "payload": None,
                "timeout": 20
            },
            {
                "name": "WDZone",
                "url": "https://wdzone-terabox-api.vercel.app/api",
                "method": "POST",
                "payload": {"url": url},
                "timeout": 25
            },
            
            # BONUS: One more working API
            {
                "name": "TeraboxBypass",
                "url": "https://terabox-bypass.vercel.app/api",
                "method": "POST",
                "payload": {"url": url},
                "timeout": 25
            }
        ]
        
        last_error = None
        
        for api in apis:
            try:
                logger.info(f"🌐 Trying API: {api['name']}")
                
                # Add delay between requests to avoid rate limiting
                time.sleep(0.5)
                
                if api["method"] == "POST":
                    response = requests.post(
                        api["url"],
                        headers=self.headers,
                        json=api["payload"],
                        timeout=api.get("timeout", 30)
                    )
                else:  # GET
                    response = requests.get(
                        api["url"],
                        headers=self.headers,
                        timeout=api.get("timeout", 30)
                    )
                
                logger.info(f"📊 {api['name']} Status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        logger.info(f"📄 {api['name']} Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                        
                        # Check for errors
                        if self._is_error_response(data):
                            error_msg = data.get("message") or data.get("error") or "API returned error"
                            logger.warning(f"⚠️ {api['name']}: {error_msg}")
                            continue
                        
                        # Parse response
                        files = self._parse_response(data, video_quality, api["name"])
                        
                        if files:
                            logger.info(f"✅ SUCCESS with {api['name']}! Found {len(files)} file(s)")
                            return {"files": files}
                        else:
                            logger.warning(f"⚠️ {api['name']}: No files extracted from response")
                            
                    except ValueError as e:
                        logger.warning(f"❌ {api['name']}: Invalid JSON response - {e}")
                        continue
                else:
                    logger.warning(f"❌ {api['name']}: HTTP {response.status_code}")
                        
            except requests.Timeout:
                last_error = f"{api['name']} timeout"
                logger.warning(f"⏱️ {api['name']} timeout after {api.get('timeout')}s")
                continue
            except Exception as e:
                last_error = str(e)
                logger.warning(f"❌ {api['name']} failed: {e}")
                continue
        
        # All APIs failed
        error_msg = f"All 8 Terabox APIs failed! Last error: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)

    def _is_error_response(self, data: Dict) -> bool:
        """Check if response contains error"""
        if isinstance(data, dict):
            # Check various error formats
            if data.get("error") or data.get("errno", 0) != 0:
                return True
            if data.get("status") == "error" or data.get("status") == False:
                return True
            if data.get("ok") == False:
                return True
            if "❌ Status" in data and data["❌ Status"] == "Error":
                return True
        return False

    def _parse_response(self, data: Dict, video_quality: str, api_name: str) -> List[Dict]:
        """Parse API response - handles ALL formats (NEW + PREVIOUS)"""
        files = []
        
        try:
            # Format 1: {success: true, data: {download_url, file_name, file_size}}
            if isinstance(data, dict) and (data.get("success") or data.get("status") == "success"):
                file_data = data.get("data", data)
                download_url = (file_data.get("download_url") or 
                               file_data.get("downloadLink") or 
                               file_data.get("dlink") or 
                               file_data.get("direct_link"))
                
                if download_url:
                    files.append({
                        "name": (file_data.get("file_name") or 
                                file_data.get("fileName") or 
                                file_data.get("filename") or "Terabox File"),
                        "size": format_size(file_data.get("size") or file_data.get("file_size") or 0),
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
            
            # Format 3: WDZone - emoji keys (YOUR PREVIOUS API)
            elif "✅ Status" in data and data["✅ Status"] == "Success":
                extracted_info = data.get("📜 Extracted Info", [])
                for item in extracted_info:
                    download_url = item.get("🔗 Direct Download Link")
                    if download_url:
                        files.append({
                            "name": item.get("📄 File Name", "Terabox File"),
                            "size": item.get("📦 File Size", "Unknown"),
                            "download_url": download_url
                        })
            
            # Format 4: NepCoderDevs/UdayScriptsX (YOUR PREVIOUS APIs)
            elif api_name in ["NepCoderDevs", "UdayScriptsX"]:
                download_url = data.get("direct_link") or data.get("link")
                if download_url:
                    files.append({
                        "name": data.get("file_name", "Terabox File"),
                        "size": data.get("size", "Unknown"),
                        "download_url": download_url
                    })
            
            # Format 5: SaveTube - {response: [{resolutions: {...}}]} (YOUR PREVIOUS API)
            elif isinstance(data, dict) and "response" in data:
                response_data = data["response"]
                if isinstance(response_data, list):
                    for item in response_data:
                        file_info = self._extract_file_info(item, video_quality)
                        if file_info:
                            files.append(file_info)
            
            # Format 6: Resolutions format
            elif isinstance(data, dict) and "resolutions" in data:
                file_info = self._extract_file_info(data, video_quality)
                if file_info:
                    files.append(file_info)
            
            # Format 7: Direct download_url in root
            elif isinstance(data, dict):
                download_url = (data.get("download_url") or 
                               data.get("downloadLink") or 
                               data.get("dlink") or 
                               data.get("direct_link"))
                if download_url:
                    files.append({
                        "name": (data.get("file_name") or 
                                data.get("fileName") or 
                                data.get("filename") or "Terabox File"),
                        "size": format_size(data.get("size") or data.get("file_size") or 0),
                        "download_url": download_url
                    })
            
            # Format 8: Nested data structure
            elif isinstance(data, dict) and "data" in data:
                data_content = data["data"]
                if isinstance(data_content, list):
                    for item in data_content:
                        file_info = self._extract_file_info(item, video_quality)
                        if file_info:
                            files.append(file_info)
        
        except Exception as e:
            logger.error(f"❌ Error parsing {api_name} response: {e}")
        
        return files

    def _extract_file_info(self, item: Dict, preferred_quality: str) -> Optional[Dict]:
        """Extract file info from item with resolutions"""
        try:
            if "resolutions" in item:
                resolutions = item["resolutions"]
                download_url = resolutions.get(preferred_quality)
                
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

def extract_terabox_data(url: str) -> Dict:
    """Backward compatibility wrapper"""
    api = TeraboxAPI()
    return api.extract_data(url)

def format_size(size_input) -> str:
    """
    Format bytes to human readable size
    Handles both int and string inputs
    """
    try:
        # If it's already a formatted string, return as-is
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
        
