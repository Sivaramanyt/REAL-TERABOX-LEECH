"""
Terabox File Downloader
Handles downloading and uploading Terabox files to Telegram
"""

import os
import asyncio
import aiohttp
import logging
from telegram import Update
from telegram.ext import ContextTypes
from terabox_api import format_size

logger = logging.getLogger(__name__)

# Configuration
DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB for Koyeb free tier
CHUNK_SIZE = 1024 * 1024  # 1MB chunks

# Video file extensions
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v', '.3gp']

async def download_file(url, file_path, progress_callback=None):
    """
    Download file from direct URL with progress tracking
    """
    try:
        # Create downloads directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        logger.info(f"⬇️ Starting download: {file_path}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3600)) as response:
                if response.status != 200:
                    raise Exception(f"Download failed with status {response.status}")
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback:
                            await progress_callback(downloaded, total_size)
                
                logger.info(f"✅ Download completed: {format_size(downloaded)}")
                return True
                
    except asyncio.TimeoutError:
        logger.error("❌ Download timeout")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise Exception("Download timed out")
    except Exception as e:
        logger.error(f"❌ Download error: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

async def upload_to_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                             file_path, caption, file_info=None):
    """
    Upload file to Telegram with appropriate type detection
    """
    try:
        if not os.path.exists(file_path):
            raise Exception("File not found")
        
        file_size = os.path.getsize(file_path)
        logger.info(f"⬆️ Uploading to Telegram: {file_path} ({format_size(file_size)})")
        
        # Check file size limit
        if file_size > MAX_FILE_SIZE:
            raise Exception(f"File too large: {format_size(file_size)}")
        
        # Determine if it's a video
        is_video = any(file_path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)
        
        # Upload based on type
        if is_video:
            await update.message.reply_video(
                video=open(file_path, 'rb'),
                caption=caption,
                supports_streaming=True
            )
        else:
            await update.message.reply_document(
                document=open(file_path, 'rb'),
                caption=caption
            )
        
        logger.info("✅ Upload completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Upload error: {e}")
        raise

def cleanup_file(file_path):
    """Remove downloaded file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"🗑️ Cleaned up: {file_path}")
    except Exception as e:
        logger.error(f"❌ Cleanup error: {e}")

def get_safe_filename(filename):
    """Generate safe filename"""
    import re
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Limit length
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    return filename
