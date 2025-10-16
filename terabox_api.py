"""
Terabox API - Using terabox-downloader-py Library (RELIABLE METHOD)
This bypasses all broken third-party APIs by using direct Terabox access
"""

import logging
from typing import Dict, List
import re

logger = logging.getLogger(__name__)

# Try to import the library
try:
    from terabox import TeraBoxDownloader
    LIBRARY_AVAILABLE = True
except ImportError:
    LIBRARY_AVAILABLE = False
    logger.error("❌ terabox-downloader-py not installed! Run: pip install terabox-downloader-py")

class TeraboxAPI:
    def __init__(self):
        """Initialize with terabox library"""
        if LIBRARY_AVAILABLE:
            self.downloader = TeraBoxDownloader()
            logger.info("✅ Terabox downloader initialized")
        else:
            logger.error("❌ Terabox library not available")
        
    def extract_data(self, url: str, video_quality: str = "HD Video") -> Dict:
        """
        Extract Terabox file info using reliable library method
        """
        if not LIBRARY_AVAILABLE:
            raise Exception("terabox-downloader-py library not installed. Please add it to requirements.txt and redeploy.")
        
        # Validate URL
        pattern = r"/s/(\w+)|surl=(\w+)"
        if not re.search(pattern, url):
            raise Exception("ERROR: Invalid terabox URL")
        
        try:
            logger.info(f"🔍 Extracting from: {url}")
            
            # Use the library to get file info
            result = self.downloader.get_info(url)
            
            if not result:
                raise Exception("No data returned from Terabox")
            
            logger.info(f"📄 Library response: {result}")
            
            # Extract files from result
            files = []
            file_list = result.get('list', [])
            
            if not file_list:
                # Try alternative response formats
                if isinstance(result, dict):
                    # Single file format
                    download_url = result.get('dlink') or result.get('downloadLink')
                    if download_url:
                        files.append({
                            "name": result.get('filename') or result.get('server_filename', 'Terabox File'),
                            "size": format_size(result.get('size', 0)),
                            "download_url": download_url
                        })
            else:
                # Multiple files format
                for item in file_list:
                    download_url = item.get('dlink') or item.get('downloadLink')
                    if download_url:
                        files.append({
                            "name": item.get('filename') or item.get('server_filename', 'Terabox File'),
                            "size": format_size(item.get('size', 0)),
                            "download_url": download_url
                        })
            
            if not files:
                raise Exception("Could not extract download links from Terabox")
            
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
    
