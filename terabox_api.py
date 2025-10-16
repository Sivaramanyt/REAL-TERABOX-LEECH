"""
Terabox API - Using terabox-downloader Library (Correct Package)
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
        """Initialize with terabox library (requires cookie)"""
        if LIBRARY_AVAILABLE:
            try:
                # Initialize without cookie (will try direct access)
                # If cookie is needed, get it from environment variable
                import os
                cookie = os.getenv("TERABOX_COOKIE", "lang=en; ndus=default;")
                self.downloader = TeraboxDL(cookie)
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
            raise Exception("Terabox library not available. Please ensure terabox-downloader is installed.")
        
        # Validate URL
        pattern = r"/s/(\w+)|surl=(\w+)|terabox|1024tera"
        if not re.search(pattern, url, re.IGNORECASE):
            raise Exception("ERROR: Invalid terabox URL")
        
        try:
            logger.info(f"🔍 Extracting from: {url}")
            
            # Use the library to get file info
            file_info = self.downloader.get_file_info(url, direct_url=True)
            
            if not file_info:
                raise Exception("No data returned from Terabox")
            
            # Check for error in response
            if "error" in file_info:
                raise Exception(file_info["error"])
            
            logger.info(f"📄 Library returned data successfully")
            
            # Extract file information
            files = []
            
            download_url = file_info.get("download_link")
            if download_url:
                files.append({
                    "name": file_info.get("file_name", "Terabox File"),
                    "size": file_info.get("file_size", "Unknown"),
                    "download_url": download_url
                })
                logger.info(f"✅ Found file: {file_info.get('file_name', 'Unknown')}")
            
            if not files:
                raise Exception("Could not extract download link from Terabox response")
            
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
        
