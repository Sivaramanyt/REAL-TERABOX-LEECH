"""
Terabox API Integration - WORKING VERSION
Based on processor-1.py with ALL DOMAINS
"""

import requests
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

TERABOX_API_URL = "https://wdzone-terabox-api.vercel.app/api"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0"

class TeraboxException(Exception):
    pass

def is_terabox_url(url):
    """Check if URL is a valid Terabox link - UPDATED with ALL domains"""
    terabox_domains = [
        # Original domains
        'terabox.com',
        'teraboxapp.com',
        '1024tera.com',
        '4funbox.com',
        'terabox.app',
        'terabox.fun',
        
        # NEW domains added
        'teraboxshare.com',
        'teraboxurl.com',
        '1024terabox.com',
        'terafileshare.com',
        'teraboxlink.com',
        'terasharelink.com'
    ]
    
    return any(domain in url.lower() for domain in terabox_domains)

def extract_terabox_data(url):
    """
    Extract file info using wdzone-terabox-api
    API returns: {"✅ Status": "Success", "📜 Extracted Info": [{...}]}
    """
    try:
        logger.info(f"🔍 Processing URL: {url}")
        
        api_url = f"{TERABOX_API_URL}?url={quote(url)}"
        response = requests.get(api_url, headers={'User-Agent': USER_AGENT}, timeout=30)
        
        if response.status_code != 200:
            raise TeraboxException(f"API request failed: {response.status_code}")
        
        req = response.json()
        logger.info(f"📄 API response keys: {list(req.keys())}")
        
        # Extract the array of file info
        extracted_info = None
        
        if "✅ Status" in req and req["✅ Status"] == "Success":
            extracted_info = req.get("📜 Extracted Info", [])
        elif "Status" in req and req["Status"] == "Success":
            extracted_info = req.get("Extracted Info", [])
        else:
            if "❌ Status" in req:
                error_msg = req.get("📜 Message", "Unknown error")
                raise TeraboxException(f"API Error: {error_msg}")
            raise TeraboxException("Invalid API response format")
        
        if not extracted_info or len(extracted_info) == 0:
            raise TeraboxException("No files found in response")
        
        # Get first file from array
        data = extracted_info[0]
        logger.info(f"📄 File data keys: {list(data.keys())}")
        
        # Extract file details
        filename = data.get("📂 Title") or data.get("Title", "Terabox_File")
        size_str = data.get("📏 Size") or data.get("Size", "0 B")
        download_url = data.get("🔽 Direct Download Link") or data.get("Direct Download Link", "")
        
        if not download_url:
            raise TeraboxException("No download URL found in file data")
        
        # Parse size
        file_size = parse_size(size_str)
        
        result = {
            "type": "file",
            "title": filename,
            "files": [{
                "name": filename,
                "url": download_url,
                "size": file_size,
                "size_str": size_str
            }],
            "total_size": file_size
        }
        
        logger.info(f"✅ Extracted: {filename} ({size_str}) - {download_url[:60]}...")
        return result
        
    except requests.exceptions.Timeout:
        raise TeraboxException("Request timed out")
    except TeraboxException:
        raise
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise TeraboxException(f"Unexpected error: {str(e)}")

def parse_size(size_str):
    """Convert size string to bytes"""
    try:
        size_str = str(size_str).replace(" ", "").upper()
        
        if "TB" in size_str:
            return int(float(size_str.replace("TB", "")) * 1024 * 1024 * 1024 * 1024)
        elif "GB" in size_str:
            return int(float(size_str.replace("GB", "")) * 1024 * 1024 * 1024)
        elif "MB" in size_str:
            return int(float(size_str.replace("MB", "")) * 1024 * 1024)
        elif "KB" in size_str:
            return int(float(size_str.replace("KB", "")) * 1024)
        else:
            return int(float(size_str.replace("B", "")))
    except:
        return 0

def format_size(size_bytes):
    """Convert bytes to human-readable format"""
    try:
        size_bytes = int(size_bytes)
        if size_bytes == 0:
            return "Unknown"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    except:
        return "Unknown"
        
