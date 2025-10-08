"""
Terabox API Handler - Gets file metadata and download links
"""
import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)

TERABOX_API_URL = "https://wdzone-terabox-api.vercel.app/api?url="

class TeraboxAPIError(Exception):
    pass

async def get_terabox_info(link):
    """Get file information from Terabox link"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(TERABOX_API_URL + link, timeout=30) as response:
                if response.status != 200:
                    raise TeraboxAPIError(f"API returned status {response.status}")
                
                data = await response.json()
                
                if not data or 'error' in data:
                    raise TeraboxAPIError(f"API error: {data.get('error', 'Unknown error')}")
                
                return {
                    'filename': data.get('filename', 'Unknown'),
                    'size': data.get('size', 0),
                    'download_url': data.get('download_url', ''),
                    'direct_link': data.get('direct_link', ''),
                    'thumbnail': data.get('thumbnail', ''),
                    'type': data.get('type', 'file')
                }
                
    except asyncio.TimeoutError:
        raise TeraboxAPIError("API request timed out")
    except aiohttp.ClientError as e:
        raise TeraboxAPIError(f"Network error: {str(e)}")
    except Exception as e:
        raise TeraboxAPIError(f"Unexpected error: {str(e)}")

def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    if not size_bytes:
        return "Unknown size"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"
