"""
Terabox Processor - FIXED based on anasty17's working method
"""

import os
import requests
import asyncio
import time
from pathlib import Path
import re

MICRO_CHUNK_SIZE = 8192  # 8KB chunks (anasty17 uses this)
UPDATE_INTERVAL = 100 * 1024  # 100KB

def format_size(size_bytes):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def speed_string_to_bytes(size_str):
    """Convert size string to bytes"""
    size_str = str(size_str).replace(" ", "").upper()
    try:
        if "KB" in size_str:
            return float(size_str.replace("KB", "")) * 1024
        elif "MB" in size_str:
            return float(size_str.replace("MB", "")) * 1024 * 1024
        elif "GB" in size_str:
            return float(size_str.replace("GB", "")) * 1024 * 1024 * 1024
        elif "TB" in size_str:
            return float(size_str.replace("TB", "")) * 1024 * 1024 * 1024 * 1024
        elif "B" in size_str:
            return float(size_str.replace("B", ""))
        else:
            return int(size_str)
    except:
        return 0

def extract_terabox_info(url):
    """
    Extract file info using wdzone-terabox-api (FIXED - anasty17 method)
    """
    try:
        print(f"🔍 Processing URL: {url}")
        
        # Clean URL first
        url = url.strip()
        
        # Use requests with proper headers (like anasty17 does)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        # Build API URL
        api_url = f"https://wdzone-terabox-api.vercel.app/api?url={url}"
        
        print(f"🌐 API URL: {api_url}")
        
        # Make request with timeout
        response = requests.get(api_url, headers=headers, timeout=60)
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📄 Response: {response.text[:200]}")  # Log first 200 chars
        
        # Parse JSON
        data = response.json()
        
        # Check if successful
        if not data.get("success"):
            error_msg = data.get("message", "Unknown error")
            raise Exception(f"API returned error: {error_msg}")
        
        # Extract file data
        file_data = data.get('data', {})
        
        if not file_data:
            raise Exception("No file data in response")
        
        filename = file_data.get('filename', 'unknown_file')
        filesize_str = file_data.get('filesize', '0')
        download_url = file_data.get('directLink', '')
        
        if not download_url:
            raise Exception("No download URL found in response")
        
        file_size = speed_string_to_bytes(filesize_str)
        
        print(f"✅ File: {filename}, Size: {format_size(file_size)}")
        print(f"🔗 Download URL: {download_url[:80]}...")
        
        return {
            'filename': filename,
            'size': file_size,
            'download_url': download_url
        }
            
    except requests.Timeout:
        raise Exception("API request timed out. Please try again.")
    except requests.RequestException as e:
        raise Exception(f"Network error: {str(e)}")
    except ValueError as e:
        raise Exception(f"Failed to parse API response: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to get file info: {str(e)}")

async def download_with_micro_chunks_only(download_url, file_path, filename, status_msg, file_size):
    """
    Download with 8KB micro-chunks (anasty17 method)
    """
    try:
        print(f"⬇️ Starting download: {filename}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Connection': 'keep-alive',
            'Accept-Encoding': 'gzip, deflate',
        }
        
        response = requests.get(download_url, headers=headers, stream=True, timeout=900)
        response.raise_for_status()
        
        # Get actual file size if not provided
        if not file_size or file_size == 0:
            file_size = int(response.headers.get('content-length', 0))
        
        downloaded = 0
        start_time = time.time()
        last_update = 0
        last_update_time = start_time
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=MICRO_CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Update progress every 100KB
                    if downloaded - last_update >= UPDATE_INTERVAL:
                        current_time = time.time()
                        elapsed = current_time - last_update_time
                        speed = (downloaded - last_update) / elapsed if elapsed > 0 else 0
                        percentage = (downloaded / file_size * 100) if file_size > 0 else 0
                        
                        try:
                            progress_bar = '█' * int(percentage / 10) + '░' * (10 - int(percentage / 10))
                            await status_msg.edit_text(
                                f"⬇️ **Downloading...**\n\n"
                                f"`{progress_bar}` {percentage:.1f}%\n\n"
                                f"📥 {format_size(downloaded)} / {format_size(file_size)}\n"
                                f"⚡ {format_size(speed)}/s",
                                parse_mode='Markdown'
                            )
                        except:
                            pass
                        
                        last_update = downloaded
                        last_update_time = current_time
                        
                        print(f"📥 {percentage:.1f}% - {format_size(speed)}/s")
        
        total_time = time.time() - start_time
        avg_speed = downloaded / total_time if total_time > 0 else 0
        print(f"✅ Download complete: {format_size(downloaded)} in {int(total_time)}s - {format_size(avg_speed)}/s")
        
        return True
        
    except Exception as e:
        raise Exception(f"Download failed: {str(e)}")
        
