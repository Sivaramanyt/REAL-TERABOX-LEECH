"""
Terabox API - FIXED for emoji field names
"""

import requests
import re
import logging

logger = logging.getLogger(__name__)

def format_size(bytes_size):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"

def parse_size_string(size_str):
    """Convert size string like '8.64 MB' to bytes"""
    size_str = str(size_str).strip()
    match = re.match(r'([\d.]+)\s*([KMGT]?B)', size_str, re.IGNORECASE)
    if not match:
        return 0
    
    size = float(match.group(1))
    unit = match.group(2).upper()
    
    units = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
    return int(size * units.get(unit, 1))

def extract_terabox_data(url):
    """
    Extract file data from Terabox using wdzone-terabox-api
    FIXED: Handles emoji field names
    """
    try:
        logger.info(f"🔍 Extracting data from: {url}")
        
        # Call API
        api_url = f"https://wdzone-terabox-api.vercel.app/api?url={url}"
        
        response = requests.get(api_url, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        logger.info(f"📄 API Response: {str(data)[:200]}")
        
        # Check for success - handle both formats
        status_key = None
        for key in data.keys():
            if 'status' in key.lower():
                status_key = key
                break
        
        if not status_key or 'success' not in data.get(status_key, '').lower():
            raise Exception(f"API returned error")
        
        # Find the file info key (with emoji)
        file_info_key = None
        for key in data.keys():
            if 'info' in key.lower() or 'extracted' in key.lower():
                file_info_key = key
                break
        
        if not file_info_key:
            raise Exception("No file info found in response")
        
        file_list = data.get(file_info_key, [])
        
        if not file_list or len(file_list) == 0:
            raise Exception("No files found in response")
        
        file_data = file_list[0]
        
        # Extract data with emoji keys
        filename = None
        filesize_str = None
        direct_link = None
        
        for key, value in file_data.items():
            if 'title' in key.lower() or 'name' in key.lower():
                filename = value
            elif 'size' in key.lower():
                filesize_str = value
            elif 'link' in key.lower() or 'download' in key.lower():
                direct_link = value
        
        if not filename:
            filename = 'unknown.file'
        if not filesize_str:
            filesize_str = '0 B'
        if not direct_link:
            raise Exception("No download link found")
        
        # Parse size
        file_size = parse_size_string(filesize_str)
        
        result = {
            'filename': filename,
            'size': file_size,
            'size_readable': format_size(file_size),
            'download_url': direct_link,
            'thumb': '',
            'resolutions': {},
        }
        
        logger.info(f"✅ Extracted: {filename} ({format_size(file_size)})")
        
        return result
        
    except requests.Timeout:
        raise Exception("API request timed out after 60s")
    except requests.RequestException as e:
        raise Exception(f"Network error: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to extract data: {str(e)}")
        
