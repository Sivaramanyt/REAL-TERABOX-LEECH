"""
Terabox API - Using terabox-downloader Library (FIXED)
Requires: pip install terabox-downloader
"""

import logging
from typing import Dict, List
import re

logger = logging.getLogger(__name__)

# Try to import the library
try:
    from TeraboxDL import TeraboxDL
    LIBRARY_AVAILABLE = True
    logger.info("✅ terabox-downloader library loaded successfully")
except ImportError:
    LIBRARY_AVAILABLE = False
    logger.error("❌ terabox-downloader not installed!")

class TeraboxAPI:
    def __init__(self):
        """Initialize with terabox library"""
        if LIBRARY_AVAILABLE:
            try:
                # Initialize without cookie (default)
                self.downloader = TeraboxDL()
                logger.info("✅ Terabox downloader initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize downloader: {e}")
                self.downloader = None
        else:
            self.downloader = None
        
    def extract_data(self, url: str, video_quality: str = "HD Video") -> Dict:
        """
        Extract Terabox file info using terabox-downloader library
        """
        if not LIBRARY_AVAILABLE or not self.downloader:
            raise Exception("Terabox library not available.")
        
        # Validate URL
        pattern = r"/s/(\w+)|surl=(\w+)|terabox|1024tera"
        if not re.search(pattern, url, re.IGNORECASE):
            raise Exception("ERROR: Invalid terabox URL")
        
        try:
            logger.info(f"🔍 Extracting from: {url}")
            
            # Use the correct method without direct_url parameter
            file_info = self.downloader.get_file_info(url)
            
            if not file_info:
                raise Exception("No data returned from Terabox")
            
            logger.info(f"📄 Got file info: {type(file_info)}")
            
            # Extract file information based on response structure
            files = []
            
            # Handle dict response
            if isinstance(file_info, dict):
                # Check for error
                if "error" in file_info or file_info.get("errno") != 0:
                    raise Exception(file_info.get("error") or "Terabox returned an error")
                
                # Try different key names for download URL
                download_url = (file_info.get("download_link") or 
                               file_info.get("dlink") or 
                               file_info.get("downloadLink") or
                               file_info.get("direct_link"))
                
                if download_url:
                    files.append({
                        "name": (file_info.get("file_name") or 
                                file_info.get("filename") or 
                                file_info.get("server_filename") or "Terabox File"),
                        "size": (file_info.get("file_size") or 
                                file_info.get("size") or "Unknown"),
                        "download_url": download_url
                    })
                    logger.info(f"✅ Found file: {file_info.get('file_name', 'Unknown')}")
                else:
                    # Check if there's a list of files inside
                    file_list = file_info.get("list", [])
                    if file_list:
                        for item in file_list:
                            dlink = (item.get("dlink") or 
                                   item.get("download_link") or 
                                   item.get("downloadLink"))
                            if dlink:
                                files.append({
                                    "name": (item.get("filename") or 
                                            item.get("server_filename") or 
                                            item.get("file_name") or "Terabox File"),
                                    "size": format_size(item.get("size", 0)),
                                    "download_url": dlink
                                })
            
            # Handle list response
            elif isinstance(file_info, list):
                for item in file_info:
                    download_url = (item.get("dlink") or 
                                   item.get("download_link") or 
                                   item.get("downloadLink"))
                    if download_url:
                        files.append({
                            "name": (item.get("filename") or 
                                    item.get("server_filename") or 
                                    item.get("file_name") or "Terabox File"),
                            "size": format_size(item.get("size", 0)),
                            "download_url": download_url
                        })
            
            if not files:
                raise Exception("Could not extract download links from response")
            
            logger.info(f"✅ Successfully extracted {len(files)} file(s)")
            return {"files": files}
            
        except Exception as e:
            error_msg = f"Terabox extraction failed: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)


# ===== BACKWARD COMPATIBILITY FUNCTIONS =====

def extract_terabox_data(url: str) -> Dict:
    """Backward compatibility wrapper"""
    api = TeraboxAPI()
    return api.extract_data(url)

def format_size(size_input) -> str:
    """Format bytes to human readable size"""
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
                                                         
