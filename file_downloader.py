"""
File Downloader - Downloads files with progress tracking
"""
import aiohttp
import asyncio
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class DownloadProgress:
    def __init__(self, total_size, callback=None):
        self.total_size = total_size
        self.downloaded = 0
        self.callback = callback
        
    async def update(self, chunk_size):
        self.downloaded += chunk_size
        if self.callback:
            percentage = (self.downloaded / self.total_size * 100) if self.total_size > 0 else 0
            await self.callback(self.downloaded, self.total_size, percentage)

async def download_file(url, filename, progress_callback=None):
    """Download file with progress tracking"""
    try:
        # Create downloads directory
        download_dir = Path("/tmp/terabox_downloads")
        download_dir.mkdir(exist_ok=True)
        
        file_path = download_dir / filename
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Download failed: HTTP {response.status}")
                
                total_size = int(response.headers.get('Content-Length', 0))
                progress = DownloadProgress(total_size, progress_callback)
                
                with open(file_path, 'wb') as file:
                    async for chunk in response.content.iter_chunked(1024 * 1024):  # 1MB chunks
                        file.write(chunk)
                        await progress.update(len(chunk))
                
                logger.info(f"Downloaded: {filename} ({total_size} bytes)")
                return str(file_path)
                
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise

async def cleanup_file(file_path):
    """Clean up downloaded file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up: {file_path}")
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")
