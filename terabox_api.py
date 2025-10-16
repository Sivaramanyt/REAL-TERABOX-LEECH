"""
Terabox API - Direct Scraper Method (No Third-Party APIs)
Works by directly accessing Terabox's internal API
"""

import requests
import logging
import re
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)

class TeraboxAPI:
    def __init__(self):
        """Initialize with direct Terabox scraping"""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://www.terabox.com/",
            "Origin": "https://www.terabox.com"
        }
        
    def extract_data(self, url: str, video_quality: str = "HD Video") -> Dict:
        """
        Extract Terabox file info using direct Terabox API access
        
        Args:
            url: Terabox share URL
            video_quality: Preferred quality (not used in direct method)
            
        Returns:
            Dict with files list containing name, size, and download_url
        """
        try:
            # Step 1: Extract share ID from URL
            logger.info(f"🔍 Processing Terabox URL: {url}")
            
            # Extract surl parameter
            if '/s/' in url:
                surl = url.split('/s/')[-1].split('?')[0]
            elif 'surl=' in url:
                surl = parse_qs(urlparse(url).query).get('surl', [''])[0]
            else:
                raise Exception("Invalid Terabox URL format")
            
            logger.info(f"📋 Share ID (surl): {surl}")
            
            # Step 2: Get file list from Terabox API
            api_url = "https://www.terabox.com/api/shorturlinfo"
            params = {
                "shorturl": surl,
                "root": "1"
            }
            
            logger.info(f"🌐 Calling Terabox API directly...")
            response = requests.get(api_url, params=params, headers=self.headers, timeout=30)
            
            if response.status_code != 200:
                raise Exception(f"Terabox API returned status {response.status_code}")
            
            data = response.json()
            logger.info(f"📄 API Response: {json.dumps(data, indent=2)[:500]}...")
            
            # Step 3: Check for errors
            errno = data.get('errno', -1)
            if errno != 0:
                error_msg = f"Terabox API error: errno={errno}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Step 4: Extract file information
            files = []
            file_list = data.get('list', [])
            
            if not file_list:
                raise Exception("No files found in Terabox link")
            
            for item in file_list:
                # Get direct download link
                fs_id = item.get('fs_id')
                dlink = item.get('dlink', '')
                
                if not dlink and fs_id:
                    # Try to get download link
                    dlink = self._get_download_link(surl, fs_id)
                
                if dlink:
                    files.append({
                        "name": item.get('server_filename', 'Terabox File'),
                        "size": format_size(item.get('size', 0)),
                        "download_url": dlink,
                        "fs_id": fs_id
                    })
                    logger.info(f"✅ Found file: {item.get('server_filename')}")
            
            if not files:
                raise Exception("Could not extract download links")
            
            logger.info(f"✅ Successfully extracted {len(files)} file(s)")
            return {"files": files}
            
        except Exception as e:
            error_msg = f"Terabox extraction failed: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def _get_download_link(self, surl: str, fs_id: str) -> Optional[str]:
        """Get direct download link for a file"""
        try:
            api_url = "https://www.terabox.com/api/download"
            params = {
                "surl": surl,
                "fid_list": f"[{fs_id}]"
            }
            
            response = requests.get(api_url, params=params, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('errno') == 0:
                    dlink = data.get('dlink', '')
                    if dlink:
                        return dlink
        except Exception as e:
            logger.warning(f"Could not get download link: {e}")
        
        return None


# ===== BACKWARD COMPATIBILITY FUNCTIONS =====

def extract_terabox_data(url: str) -> Dict:
    """
    Backward compatibility wrapper
    """
    api = TeraboxAPI()
    return api.extract_data(url)

def format_size(size_input) -> str:
    """
    Format bytes to human readable size
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
            
