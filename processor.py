"""
Terabox Processor - WITH BACKUP API SUPPORT
"""

import os
import requests
import asyncio
import time
from pathlib import Path

MICRO_CHUNK_SIZE = 1024  # 1KB
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
    size_str = size_str.replace(" ", "").upper()
    if "KB" in size_str:
        return float(size_str.replace("KB", "")) * 1024
    elif "MB" in size_str:
        return float(size_str.replace("MB", "")) * 1024 * 1024
    elif "GB" in size_str:
        return float(size_str.replace("GB", "")) * 1024 * 1024 * 1024
    elif "TB" in size_str:
        return float(size_str.replace("TB", "")) * 1024 * 1024 * 1024 * 1024
    else:
        try:
            return float(size_str.replace("B", ""))
        except:
            return 0

def extract_terabox_info(url):
    """
    Extract file info using multiple APIs with fallback
    """
    # List of APIs to try
    apis = [
        f"https://wdzone-terabox-api.vercel.app/api?url={url}",
        f"https://terabox-dl.qtcloud.workers.dev/api/get-info?shorturl={url}",
        f"https://teradl-api.deno.dev/download?url={url}"
    ]
    
    for api_url in apis:
        try:
            print(f"🔍 Trying API: {api_url[:50]}...")
            
            response = requests.get(api_url, timeout=30)
            data = response.json()
            
            # wdzone-terabox-api format
            if data.get("success") and data.get("data"):
                file_data = data['data']
                return {
                    'filename': file_data.get('filename', 'unknown_file'),
                    'size': speed_string_to_bytes(file_data.get('filesize', '0')),
                    'download_url': file_data.get('directLink', '')
                }
            
            # Alternative API format
            elif data.get('ok') and data.get('file_name'):
                return {
                    'filename': data.get('file_name', 'unknown_file'),
                    'size': int(data.get('file_size', 0)),
                    'download_url': data.get('download_link', '')
                }
            
            # Another format
            elif data.get('downloadLink'):
                return {
                    'filename': data.get('fileName', 'unknown_file'),
                    'size': int(data.get('fileSize', 0)),
                    'download_url': data.get('downloadLink', '')
                }
                
        except Exception as e:
            print(f"⚠️ API failed: {str(e)}")
            continue
    
    # If all APIs fail
    raise Exception("All APIs failed. Please try again later or check if the link is valid.")

async def download_with_micro_chunks_only(download_url, file_path, filename, status_msg, file_size):
    """
    Download with 1KB micro-chunks - PREVENTS IncompleteRead errors
    """
    try:
        headers = {
            'User-Agent': 'curl/7.68.0',
            'Accept': '*/*',
            'Connection': 'keep-alive'
        }
        
        response = requests.get(download_url, headers=headers, stream=True, timeout=900)
        response.raise_for_status()
        
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
            
