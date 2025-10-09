"""
Terabox API Integration - FIXED
"""

import requests
import logging
from urllib.parse import quote
import re

logger = logging.getLogger(__name__)

TERABOX_API_URL = "https://wdzone-terabox-api.vercel.app/api"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

class TeraboxException(Exception):
    pass

def is_terabox_url(url):
    terabox_domains = ['terabox.com', 'teraboxapp.com', '1024tera.com', '4funbox.com', 'terabox.app', 'terabox.fun', 'teraboxshare.com']
    return any(domain in url.lower() for domain in terabox_domains)

def extract_terabox_data(url):
    try:
        logger.info(f"🔍 Extracting Terabox data from: {url}")
        
        api_url = f"{TERABOX_API_URL}?url={quote(url)}"
        response = requests.get(api_url, headers={"User-Agent": USER_AGENT}, timeout=30)
        
        logger.info(f"📊 API Response Status: {response.status_code}")
        
        if response.status_code != 200:
            raise TeraboxException(f"API returned status code: {response.status_code}")
        
        data = response.json()
        logger.info(f"📄 API Response Keys: {list(data.keys())}")
        
        for key in data.keys():
            if "Error" in key:
                raise TeraboxException(data[key])
        
        has_status = any("Status" in key for key in data.keys())
        if not has_status:
            raise TeraboxException("Invalid API response format")
        
        result = {"type": None, "title": None, "files": [], "total_size": 0}
        
        extracted_info_key = None
        for key in data.keys():
            if "Extracted Info" in key:
                extracted_info_key = key
                break
        
        if not extracted_info_key:
            raise TeraboxException("No extracted info found")
        
        extracted_info = data[extracted_info_key]
        logger.info(f"📄 Extracted Info: {extracted_info[:200]}...")
        
        # USE REGEX to extract parts (handles URLs with query parameters)
        filename = "Terabox_File"
        filesize_str = "Unknown"
        download_url = None
        
        # Extract Title
        title_match = re.search(r'Title:\s*([^,]+?)(?:,\s*Size:|$)', extracted_info)
        if title_match:
            filename = title_match.group(1).strip()
            logger.info(f"📝 Filename: {filename}")
        
        # Extract Size
        size_match = re.search(r'Size:\s*([^,]+?)(?:,\s*Direct Download Link:|$)', extracted_info)
        if size_match:
            filesize_str = size_match.group(1).strip()
            logger.info(f"📦 Size: {filesize_str}")
        
        # Extract Direct Download Link (handles URLs with & and other special chars)
        link_match = re.search(r'Direct Download Link:\s*(https?://[^\s,]+?)(?:,\s*Thumbnails:|$)', extracted_info)
        if link_match:
            download_url = link_match.group(1).strip()
            logger.info(f"🔗 Download URL: {download_url[:100]}...")
        
        if not download_url:
            logger.error(f"❌ Could not extract download link")
            raise TeraboxException("Could not find download link")
        
        result["type"] = "file"
        result["title"] = filename
        result["files"].append({
            "name": filename,
            "url": download_url,
            "size": parse_size(filesize_str),
            "size_str": filesize_str
        })
        result["total_size"] = parse_size(filesize_str)
        
        logger.info(f"✅ Extracted: {filename} ({filesize_str})")
        return result
        
    except requests.exceptions.Timeout:
        raise TeraboxException("Request timed out")
    except TeraboxException:
        raise
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise TeraboxException(f"Error: {str(e)}")

def parse_size(size_str):
    try:
        if isinstance(size_str, int):
            return size_str
        size_str = str(size_str).upper().strip()
        if not size_str or size_str == "UNKNOWN":
            return 0
        import re
        match = re.match(r'([\d.]+)\s*([KMGT]?B)?', size_str)
        if not match:
            return 0
        number = float(match.group(1))
        unit = match.group(2) if match.group(2) else 'B'
        units = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
        return int(number * units.get(unit, 1))
    except:
        return 0

def format_size(size_bytes):
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
        
