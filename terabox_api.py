"""
Terabox API Integration
Extracts download links from Terabox URLs using wdzone API
"""

import requests
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Terabox API endpoint
TERABOX_API_URL = "https://wdzone-terabox-api.vercel.app/api"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

class TeraboxException(Exception):
    """Custom exception for Terabox errors"""
    pass

def is_terabox_url(url):
    """Check if URL is a valid Terabox link"""
    terabox_domains = [
        'terabox.com',
        'teraboxapp.com',
        '1024tera.com',
        '4funbox.com',
        'terabox.app',
        'terabox.fun',
        'teraboxshare.com'
    ]
    
    return any(domain in url.lower() for domain in terabox_domains)

def extract_terabox_data(url):
    """
    Extract file information from Terabox URL
    Returns: dict with file details or raises TeraboxException
    
    API Response Format:
    {
        "✅ Status": "Success",
        "📄 Extracted Info": "Title: file.mp4, Size: 3.20 MB, Direct Download Link: https://...",
        "🔗 ShortLink": "shortlink_url"
    }
    """
    try:
        logger.info(f"🔍 Extracting Terabox data from: {url}")
        
        # Build API request URL
        api_url = f"{TERABOX_API_URL}?url={quote(url)}"
        
        # Make request to Terabox API
        response = requests.get(
            api_url,
            headers={"User-Agent": USER_AGENT},
            timeout=30
        )
        
        logger.info(f"📊 API Response Status: {response.status_code}")
        
        if response.status_code != 200:
            raise TeraboxException(f"API returned status code: {response.status_code}")
        
        # Parse JSON response
        data = response.json()
        logger.info(f"📄 API Response Keys: {list(data.keys())}")
        
        # Check if API returned error
        for key in data.keys():
            if "Error" in key:
                raise TeraboxException(data[key])
        
        # Check for status
        has_status = any("Status" in key for key in data.keys())
        if not has_status:
            raise TeraboxException("Invalid API response format")
        
        # Initialize result structure
        result = {
            "type": None,
            "title": None,
            "files": [],
            "total_size": 0
        }
        
        # Find "Extracted Info" key (it contains all the data)
        extracted_info_key = None
        for key in data.keys():
            if "Extracted Info" in key:
                extracted_info_key = key
                logger.info(f"✅ Found extracted info key: '{key}'")
                break
        
        if not extracted_info_key:
            raise TeraboxException("No extracted info found in API response")
        
        # Get the extracted info string
        extracted_info = data[extracted_info_key]
        logger.info(f"📄 Extracted Info Content: {extracted_info}")
        
        # Parse the extracted info string
        # Format: "Title: filename.mp4, Size: 3.20 MB, Direct Download Link: https://..."
        filename = "Terabox_File"
        filesize_str = "Unknown"
        download_url = None
        
        if "Title:" in extracted_info:
            # Split by comma to get individual parts
            parts = extracted_info.split(", ")
            
            for part in parts:
                part = part.strip()
                
                if part.startswith("Title:"):
                    filename = part.replace("Title:", "").strip()
                    logger.info(f"📝 Filename: {filename}")
                
                elif part.startswith("Size:"):
                    filesize_str = part.replace("Size:", "").strip()
                    logger.info(f"📦 Size: {filesize_str}")
                
                elif "Direct Download Link:" in part:
                    # The download link might have commas in it, so join remaining parts
                    download_url = part.split("Direct Download Link:", 1)[1].strip()
                    logger.info(f"🔗 Download URL: {download_url[:80]}...")
        
        # Validate we got the download URL
        if not download_url:
            logger.error(f"❌ Could not parse download link from: {extracted_info}")
            raise TeraboxException("Could not find download link in extracted info")
        
        # Build result
        result["type"] = "file"
        result["title"] = filename
        result["files"].append({
            "name": filename,
            "url": download_url,
            "size": parse_size(filesize_str),
            "size_str": filesize_str
        })
        result["total_size"] = parse_size(filesize_str)
        
        logger.info(f"✅ Successfully extracted: {filename} ({filesize_str})")
        return result
        
    except requests.exceptions.Timeout:
        raise TeraboxException("Request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        raise TeraboxException(f"Network error: {str(e)}")
    except ValueError as e:
        raise TeraboxException(f"Invalid JSON response: {str(e)}")
    except TeraboxException:
        raise  # Re-raise our custom exceptions
    except Exception as e:
        logger.error(f"❌ Terabox extraction error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise TeraboxException(f"Unexpected error: {str(e)}")

def parse_size(size_str):
    """Convert size string to bytes"""
    try:
        if isinstance(size_str, int):
            return size_str
        
        size_str = str(size_str).upper().strip()
        
        # Handle "Unknown" or empty strings
        if not size_str or size_str == "UNKNOWN":
            return 0
        
        # Extract number and unit
        import re
        match = re.match(r'([\d.]+)\s*([KMGT]?B)?', size_str)
        if not match:
            return 0
        
        number = float(match.group(1))
        unit = match.group(2) if match.group(2) else 'B'
        
        # Convert to bytes
        units = {
            'B': 1,
            'KB': 1024,
            'MB': 1024**2,
            'GB': 1024**3,
            'TB': 1024**4
        }
        return int(number * units.get(unit, 1))
        
    except Exception as e:
        logger.warning(f"Failed to parse size '{size_str}': {e}")
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
            
