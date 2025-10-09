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
        logger.info(f"📄 API Response: {str(data)[:300]}")
        
        # Check if API returned error
        if "❌ Error" in data:
            raise TeraboxException(data["❌ Error"])
        
        # Check for status - handle both formats (with and without space)
        status_key = "✅ Status" if "✅ Status" in data else "✅Status"
        if status_key not in data:
            raise TeraboxException("Invalid API response format")
        
        # Parse response - HANDLES MULTIPLE API FORMATS
        result = {
            "type": None,
            "title": None,
            "files": [],
            "total_size": 0
        }
        
        # FORMAT 1: NEW API FORMAT (Current) - WITH SPACES AFTER EMOJIS
        # Response: {"✅ Status": "Success", "📄 Extracted Info": "Title: file.mp4, Size: 3.20 MB", "🔗 Direct Download Link": "url"}
        
        # Try both key formats (with and without space after emoji)
        direct_link_key = None
        extracted_info_key = None
        
        # Check for direct download link key
        if "🔗 Direct Download Link" in data:
            direct_link_key = "🔗 Direct Download Link"
        elif "🔗Direct Download Link" in data:
            direct_link_key = "🔗Direct Download Link"
        
        # Check for extracted info key
        if "📄 Extracted Info" in data:
            extracted_info_key = "📄 Extracted Info"
        elif "📄Extracted Info" in data:
            extracted_info_key = "📄Extracted Info"
        
        if direct_link_key and direct_link_key in data:
            result["type"] = "file"
            
            # Extract filename and size from "📄 Extracted Info"
            extracted_info = data.get(extracted_info_key, "") if extracted_info_key else ""
            filename = "Terabox_File"
            filesize_str = "Unknown"
            
            # Parse: "Title: filename.mp4, Size: 3.20 MB"
            if extracted_info and "Title:" in extracted_info:
                try:
                    # Split by comma to separate title and size
                    parts = extracted_info.split(",")
                    
                    for part in parts:
                        part = part.strip()
                        if "Title:" in part:
                            filename = part.replace("Title:", "").strip()
                        elif "Size:" in part:
                            filesize_str = part.replace("Size:", "").strip()
                except Exception as e:
                    logger.warning(f"Failed to parse extracted info: {e}")
            
            result["title"] = filename
            result["files"].append({
                "name": filename,
                "url": data[direct_link_key],
                "size": parse_size(filesize_str),
                "size_str": filesize_str
            })
            result["total_size"] = parse_size(filesize_str)
            
            logger.info(f"✅ Extracted file: {filename} ({filesize_str})")
        
        # FORMAT 2: OLD API FORMAT (Backward compatibility)
        elif "📄 File Name" in data and "🔗 Download Link" in data:
            result["type"] = "file"
            result["title"] = data["📄 File Name"]
            result["files"].append({
                "name": data["📄 File Name"],
                "url": data["🔗 Download Link"],
                "size": parse_size(data.get("📦 File Size", "0")),
                "size_str": data.get("📦 File Size", "Unknown")
            })
            result["total_size"] = result["files"][0]["size"]
            
            logger.info(f"✅ Extracted file (old format): {data['📄 File Name']}")
        
        # FORMAT 3: FOLDER FORMAT
        elif "📁 Folder Contents" in data:
            result["type"] = "folder"
            result["title"] = data.get("📁 Folder Name", "Terabox Folder")
            
            for item in data["📁 Folder Contents"]:
                if isinstance(item, dict):
                    # Check for both old and new formats
                    download_link = (item.get("Download Link") or 
                                   item.get("🔗 Direct Download Link") or 
                                   item.get("🔗Direct Download Link"))
                    file_name = item.get("File Name") or item.get("Title", "Unknown")
                    file_size_str = item.get("File Size") or item.get("Size", "Unknown")
                    
                    if download_link:
                        file_size = parse_size(file_size_str)
                        result["files"].append({
                            "name": file_name,
                            "url": download_link,
                            "size": file_size,
                            "size_str": file_size_str
                        })
                        result["total_size"] += file_size
            
            logger.info(f"✅ Extracted folder with {len(result['files'])} files")
        
        # Validate we got files
        if not result["files"]:
            logger.error(f"❌ No files extracted. Full API response: {data}")
            raise TeraboxException("No downloadable files found in response")
        
        logger.info(f"✅ Successfully extracted {len(result['files'])} file(s)")
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
        
