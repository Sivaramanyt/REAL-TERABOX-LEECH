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
        logger.info(f"📄 Full API Response: {str(data)[:500]}")
        
        # Check if API returned error - search for "Error" in any key
        for key in data.keys():
            if "Error" in key:
                raise TeraboxException(data[key])
        
        # Check for status - search for "Status" in any key
        has_status = any("Status" in key for key in data.keys())
        if not has_status:
            raise TeraboxException("Invalid API response format")
        
        # Parse response
        result = {
            "type": None,
            "title": None,
            "files": [],
            "total_size": 0
        }
        
        # DYNAMIC KEY DETECTION - Find keys by searching for keywords
        direct_link_key = None
        extracted_info_key = None
        file_name_key = None
        download_link_key = None
        file_size_key = None
        folder_contents_key = None
        
        for key in data.keys():
            # Look for direct download link (new format)
            if "Direct Download Link" in key:
                direct_link_key = key
                logger.info(f"✅ Found download link key: '{key}'")
            
            # Look for extracted info (new format)
            if "Extracted Info" in key:
                extracted_info_key = key
                logger.info(f"✅ Found extracted info key: '{key}'")
            
            # Look for file name (old format)
            if "File Name" in key and "Folder" not in key:
                file_name_key = key
                logger.info(f"✅ Found file name key: '{key}'")
            
            # Look for download link (old format)
            if "Download Link" in key and "Direct" not in key:
                download_link_key = key
                logger.info(f"✅ Found download link key (old): '{key}'")
            
            # Look for file size
            if "File Size" in key:
                file_size_key = key
                logger.info(f"✅ Found file size key: '{key}'")
            
            # Look for folder contents
            if "Folder Contents" in key:
                folder_contents_key = key
                logger.info(f"✅ Found folder contents key: '{key}'")
        
        # FORMAT 1: NEW API FORMAT
        # Has: Direct Download Link + Extracted Info
        if direct_link_key and direct_link_key in data:
            result["type"] = "file"
            
            # Extract filename and size from extracted info
            extracted_info = data.get(extracted_info_key, "") if extracted_info_key else ""
            filename = "Terabox_File"
            filesize_str = "Unknown"
            
            # Parse: "Title: filename.mp4, Size: 3.20 MB"
            if extracted_info and "Title:" in extracted_info:
                try:
                    parts = extracted_info.split(",")
                    for part in parts:
                        part = part.strip()
                        if "Title:" in part:
                            filename = part.replace("Title:", "").strip()
                        elif "Size:" in part:
                            filesize_str = part.replace("Size:", "").strip()
                    
                    logger.info(f"📝 Parsed - Filename: {filename}, Size: {filesize_str}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to parse extracted info: {e}")
            
            result["title"] = filename
            result["files"].append({
                "name": filename,
                "url": data[direct_link_key],
                "size": parse_size(filesize_str),
                "size_str": filesize_str
            })
            result["total_size"] = parse_size(filesize_str)
            
            logger.info(f"✅ Successfully extracted file: {filename} ({filesize_str})")
        
        # FORMAT 2: OLD API FORMAT
        # Has: File Name + Download Link
        elif file_name_key and download_link_key:
            result["type"] = "file"
            result["title"] = data[file_name_key]
            
            size_str = data.get(file_size_key, "Unknown") if file_size_key else "Unknown"
            
            result["files"].append({
                "name": data[file_name_key],
                "url": data[download_link_key],
                "size": parse_size(size_str),
                "size_str": size_str
            })
            result["total_size"] = result["files"][0]["size"]
            
            logger.info(f"✅ Extracted file (old format): {data[file_name_key]}")
        
        # FORMAT 3: FOLDER FORMAT
        elif folder_contents_key:
            result["type"] = "folder"
            
            # Find folder name key
            folder_name_key = None
            for key in data.keys():
                if "Folder Name" in key:
                    folder_name_key = key
                    break
            
            result["title"] = data.get(folder_name_key, "Terabox Folder") if folder_name_key else "Terabox Folder"
            
            for item in data[folder_contents_key]:
                if isinstance(item, dict):
                    # Find keys dynamically for each item
                    item_download_link = None
                    item_name = "Unknown"
                    item_size = "Unknown"
                    
                    for key in item.keys():
                        if "Download Link" in key:
                            item_download_link = item[key]
                        if "File Name" in key or "Title" in key:
                            item_name = item[key]
                        if "Size" in key:
                            item_size = item[key]
                    
                    if item_download_link:
                        file_size = parse_size(item_size)
                        result["files"].append({
                            "name": item_name,
                            "url": item_download_link,
                            "size": file_size,
                            "size_str": item_size
                        })
                        result["total_size"] += file_size
            
            logger.info(f"✅ Extracted folder with {len(result['files'])} files")
        
        # Validate we got files
        if not result["files"]:
            logger.error(f"❌ No files extracted!")
            logger.error(f"❌ Available keys: {list(data.keys())}")
            logger.error(f"❌ Found keys: direct_link={direct_link_key}, extracted_info={extracted_info_key}")
            logger.error(f"❌ Full response: {data}")
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
                
