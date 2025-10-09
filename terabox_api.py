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
        'terabox.fun'
    ]
    
    return any(domain in url.lower() for domain in terabox_domains)

def extract_terabox_data(url):
    """
    Extract file information from Terabox URL
    Returns: dict with file details or raises TeraboxException
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
        logger.info(f"📄 API Response: {str(data)[:200]}")
        
        # Check if API returned error
        if "❌ Error" in data:
            raise TeraboxException(data["❌ Error"])
        
        if "✅ Status" not in data:
            raise TeraboxException("Invalid API response format")
        
        # Parse response based on type (file or folder)
        result = {
            "type": None,
            "title": None,
            "files": [],
            "total_size": 0
        }
        
        # Single file response
        if "📄 File Name" in data and "🔗 Download Link" in data:
            result["type"] = "file"
            result["title"] = data["📄 File Name"]
            result["files"].append({
                "name": data["📄 File Name"],
                "url": data["🔗 Download Link"],
                "size": parse_size(data.get("📦 File Size", "0")),
                "size_str": data.get("📦 File Size", "Unknown")
            })
            result["total_size"] = result["files"][0]["size"]
        
        # Folder response
        elif "📁 Folder Contents" in data:
            result["type"] = "folder"
            result["title"] = data.get("📁 Folder Name", "Terabox Folder")
            
            for item in data["📁 Folder Contents"]:
                if isinstance(item, dict) and "Download Link" in item:
                    file_size = parse_size(item.get("File Size", "0"))
                    result["files"].append({
                        "name": item.get("File Name", "Unknown"),
                        "url": item.get("Download Link"),
                        "size": file_size,
                        "size_str": item.get("File Size", "Unknown")
                    })
                    result["total_size"] += file_size
        
        # Validate we got files
        if not result["files"]:
            raise TeraboxException("No downloadable files found in response")
        
        logger.info(f"✅ Extracted {len(result['files'])} file(s) successfully")
        return result
        
    except requests.exceptions.Timeout:
        raise TeraboxException("Request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        raise TeraboxException(f"Network error: {str(e)}")
    except ValueError as e:
        raise TeraboxException(f"Invalid JSON response: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Terabox extraction error: {e}")
        raise TeraboxException(f"Unexpected error: {str(e)}")

def parse_size(size_str):
    """Convert size string to bytes"""
    try:
        if isinstance(size_str, int):
            return size_str
        
        size_str = str(size_str).upper().strip()
        
        # Extract number and unit
        import re
        match = re.match(r'([\d.]+)\s*([KMGT]?B)?', size_str)
        if not match:
            return 0
        
        number = float(match.group(1))
        unit = match.group(2) if match.group(2) else 'B'
        
        # Convert to bytes
        units = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
        return int(number * units.get(unit, 1))
        
    except:
        return 0

def format_size(size_bytes):
    """Convert bytes to human-readable format"""
    try:
        size_bytes = int(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    except:
        return "Unknown"
