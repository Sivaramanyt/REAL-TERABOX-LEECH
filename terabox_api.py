"""
Terabox API - Extract file info using wdzone-terabox-api.vercel.app
ORIGINAL WORKING VERSION
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
    """Convert size string like '41.23 MB' to bytes"""
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
    Returns: dict with filename, size, download_url
    """
    try:
        logger.info(f"🔍 Extracting data from: {url}")
        
        # Call API
        api_url = f"https://wdzone-terabox-api.vercel.app/api?url={url}"
        
        response = requests.get(api_url, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get('success'):
            error_msg = data.get('message', 'Unknown error from API')
            raise Exception(f"API Error: {error_msg}")
        
        file_data = data.get('data', {})
        
        if not file_data:
            raise Exception("No file data returned from API")
        
        # Extract info
        filename = file_data.get('filename', 'unknown.file')
        filesize_str = file_data.get('filesize', '0 B')
        direct_link = file_data.get('directLink', '')
        
        if not direct_link:
            raise Exception("No download link found")
        
        # Parse size
        file_size = parse_size_string(filesize_str)
        
        result = {
            'filename': filename,
            'size': file_size,
            'size_readable': format_size(file_size),
            'download_url': direct_link,
            'thumb': file_data.get('thumb', ''),
            'resolutions': file_data.get('resolutions', {}),
        }
        
        logger.info(f"✅ Extracted: {filename} ({format_size(file_size)})")
        
        return result
        
    except requests.Timeout:
        raise Exception("API request timed out after 60s")
    except requests.RequestException as e:
        raise Exception(f"Network error: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to extract data: {str(e)}")
            
