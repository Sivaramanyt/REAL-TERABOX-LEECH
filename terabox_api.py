"""
Terabox API - Based on Working Telegram Bots (@teranr4bot method)
Uses 4 FREE APIs + TeraDL + NDUS Cookie (r0ld3x method) for maximum reliability
GitHub: https://github.com/r0ld3x/terabox-downloader-bot
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
        """Initialize with multiple methods for maximum reliability"""
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
        Extract Terabox file info using multiple methods
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
        
        # Step 3: Try 4 APIs in order
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
                "payload": {"url": url}
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
                else:
                    response = requests.get(
                        api["url"],
                        timeout=30
                    )
                    
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"📄 {api['name']} Response: {data}")
                    
                    if self._is_error_response(data):
                        logger.warning(f"⚠️ {api['name']}: Error in response")
                        continue
                    
                    files = self._parse_response(data, video_quality, api["name"])
                    if files:
                        logger.info(f"✅ SUCCESS with {api['name']}!")
                        return {"files": files}
                    else:
                        logger.warning(f"⚠️ {api['name']}: No files found")
                        
            except Exception as e:
                last_error = str(e)
                logger.warning(f"❌ {api['name']} failed: {e}")
                continue
        
        # NEW: NDUS Cookie Method (Used by @teranr4bot and working bots)
        try:
            logger.info("🔐 Trying NDUS Cookie Method (Working Bots Method)")
            from config import TERABOX_COOKIE
            
            if TERABOX_COOKIE:
                # Extract ndus value from cookie string
                ndus_value = None
                
                # Handle different cookie formats
                if 'ndus=' in TERABOX_COOKIE:
                    for item in TERABOX_COOKIE.split(';'):
                        if 'ndus=' in item:
                            ndus_value = item.split('ndus=')[1].strip()
                            break
                elif '=' not in TERABOX_COOKIE:
                    # Assume it's just the ndus value itself
                    ndus_value = TERABOX_COOKIE.strip()
                
                if ndus_value:
                    logger.info(f"🔑 Using NDUS token: {ndus_value[:20]}...")
                    
                    # Extract shorturl from the Terabox URL
                    shorturl_match = re.search(r'/s/(\w+)', url)
                    if not shorturl_match:
                        raise Exception("Could not extract shorturl from URL")
                    
                    shorturl = shorturl_match.group(1)
                    
                    # Use official Terabox API (same as working bots)
                    api_url = f"https://www.terabox.com/api/shorturlinfo?shorturl={shorturl}&root=1"
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                        'Accept': 'application/json, text/plain, */*',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Cookie': f'ndus={ndus_value}',
                        'Referer': url
                    }
                    
                    response = requests.get(api_url, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        logger.info(f"📡 NDUS API Response: errno={data.get('errno')}")
                        
                        if data.get('errno') == 0:
                            file_list = data.get('list', [])
                            
                            if file_list and len(file_list) > 0:
                                file_info = file_list[0]
                                
                                # Get direct download link
                                dlink = file_info.get('dlink', '')
                                
                                if dlink:
                                    logger.info("✅ SUCCESS with NDUS Cookie Method!")
                                    return {
                                        "files": [{
                                            "name": file_info.get('server_filename', 'Terabox File'),
                                            "size": self._format_size(file_info.get('size', 0)),
                                            "download_url": dlink
                                        }]
                                    }
                                else:
                                    logger.warning("⚠️ NDUS: No download link in response")
                            else:
                                logger.warning("⚠️ NDUS: Empty file list")
                        else:
                            logger.warning(f"⚠️ NDUS API returned errno: {data.get('errno')}")
                    else:
                        logger.warning(f"⚠️ NDUS API returned status {response.status_code}")
                else:
                    logger.warning("⚠️ Could not extract ndus value from TERABOX_COOKIE")
            else:
                logger.warning("⚠️ TERABOX_COOKIE not configured")
                
        except Exception as e:
            last_error = str(e)
            logger.warning(f"❌ NDUS Cookie method failed: {e}")
        
        # Try TeraDL API as additional fallback
        try:
            logger.info("🌟 Trying TeraDL API (Fallback)")
            
            teradl_url = "https://teradl.dapuntaratya.com/api"
            payload = {"url": url}
            
            teradl_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            response = requests.post(teradl_url, json=payload, headers=teradl_headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                download_url = None
                file_name = "Terabox File"
                file_size = "Unknown"
                
                if isinstance(data, dict):
                    if data.get('status') == 'success' and 'data' in data:
                        file_data = data['data']
                        download_url = file_data.get('download_url') or file_data.get('url') or file_data.get('dlink')
                        file_name = file_data.get('file_name') or file_data.get('filename') or file_data.get('title', 'Terabox File')
                        file_size = file_data.get('size') or file_data.get('filesize', 'Unknown')
                    elif 'download_url' in data or 'url' in data or 'dlink' in data:
                        download_url = data.get('download_url') or data.get('url') or data.get('dlink')
                        file_name = data.get('file_name') or data.get('filename') or data.get('title', 'Terabox File')
                        file_size = data.get('size') or data.get('filesize', 'Unknown')
                
                if download_url:
                    logger.info("✅ SUCCESS with TeraDL API!")
                    return {
                        "files": [{
                            "name": file_name,
                            "size": self._format_size(file_size) if isinstance(file_size, int) else file_size,
                            "download_url": download_url
                        }]
                    }
                        
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
            if "❌ Status" in data and data["❌ Status"] == "Error":
                return True
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
                            download_url = item.get("🔗 Direct Download Link")
                            if download_url:
                                files.append({
                                    "name": item.get("📄 File Name", "Terabox File"),
                                    "size": item.get("📦 File Size", "Unknown"),
                                    "download_url": download_url
                                })
            
            # NepCoderDevs / UdayScriptsX format
            elif api_name in ["NepCoderDevs", "UdayScriptsX"]:
                if "direct_link" in data and data.get("direct_link"):
                    files.append({
                        "name": data.get("file_name", "Terabox File"),
                        "size": data.get("size", "Unknown"),
                        "download_url": data["direct_link"]
                    })
                elif "link" in data and data.get("link"):
                    files.append({
                        "name": data.get("file_name", "Terabox File"),
                        "size": data.get("size", "Unknown"),
                        "download_url": data["link"]
                    })
            
            # SaveTube format
            elif isinstance(data, dict) and "response" in data:
                response_data = data["response"]
                if isinstance(response_data, list):
                    for item in response_data:
                        file_info = self._extract_file_info(item, video_quality)
                        if file_info:
                            files.append(file_info)
            
            # Generic formats
            elif isinstance(data, dict):
                if "resolutions" in data:
                    file_info = self._extract_file_info(data, video_quality)
                    if file_info:
                        files.append(file_info)
                elif "download_url" in data:
                    files.append({
                        "name": data.get("file_name", "Terabox File"),
                        "size": data.get("file_size", "Unknown"),
                        "download_url": data["download_url"]
                    })
                elif "data" in data and isinstance(data["data"], list):
                    for item in data["data"]:
                        file_info = self._extract_file_info(item, video_quality)
                        if file_info:
                            files.append(file_info)
                            
        except Exception as e:
            logger.error(f"❌ Error parsing response: {e}")
            
        return files
    
    def _extract_file_info(self, item: Dict, preferred_quality: str) -> Optional[Dict]:
        """Extract file info from a single item"""
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

# Backward compatibility functions
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
        
