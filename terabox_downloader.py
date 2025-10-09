"""
Terabox File Downloader
Handles downloading and uploading Terabox files to Telegram
WITH VIDEO THUMBNAILS AND ORIGINAL QUALITY
"""

import os
import asyncio
import aiohttp
import logging
import subprocess
from telegram import Update
from telegram.ext import ContextTypes
from terabox_api import format_size

logger = logging.getLogger(__name__)

# Configuration
DOWNLOAD_DIR = "downloads"
THUMBNAIL_DIR = "thumbnails"
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

async def generate_video_thumbnail(video_path, thumbnail_path=None):
    """
    Generate thumbnail from video using ffmpeg
    Returns thumbnail path or None if failed
    """
    try:
        # Create thumbnails directory
        os.makedirs(THUMBNAIL_DIR, exist_ok=True)
        
        if not thumbnail_path:
            thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{os.path.basename(video_path)}_thumb.jpg")
        
        # Use ffmpeg to extract thumbnail at 1 second
        command = [
            'ffmpeg',
            '-i', video_path,
            '-ss', '00:00:01.000',
            '-vframes', '1',
            '-vf', 'scale=320:320:force_original_aspect_ratio=decrease',
            '-y',
            thumbnail_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0 and os.path.exists(thumbnail_path):
            logger.info(f"✅ Thumbnail generated: {thumbnail_path}")
            return thumbnail_path
        else:
            logger.warning(f"⚠️ Thumbnail generation failed: {stderr.decode()}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Thumbnail generation error: {e}")
        return None

async def get_video_metadata(video_path):
    """
    Get video metadata using ffprobe
    Returns dict with width, height, duration
    """
    try:
        command = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            '-show_format',
            video_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            import json
            data = json.loads(stdout.decode())
            
            # Find video stream
            video_stream = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if video_stream:
                width = int(video_stream.get('width', 0))
                height = int(video_stream.get('height', 0))
                duration = int(float(data.get('format', {}).get('duration', 0)))
                
                logger.info(f"📹 Video metadata: {width}x{height}, {duration}s")
                return {
                    'width': width,
                    'height': height,
                    'duration': duration
                }
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Metadata extraction error: {e}")
        return None

async def upload_to_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                             file_path, caption, file_info=None):
    """
    Upload file to Telegram with thumbnails and original quality
    RETURNS the sent message object for forwarding
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
        
        sent_message = None
        
        if is_video:
            # Generate thumbnail
            thumbnail_path = await generate_video_thumbnail(file_path)
            
            # Get video metadata for original quality
            metadata = await get_video_metadata(file_path)
            
            # Upload with thumbnail and metadata
            with open(file_path, 'rb') as video_file:
                upload_kwargs = {
                    'video': video_file,
                    'caption': caption,
                    'supports_streaming': True
                }
                
                # Add thumbnail if generated
                if thumbnail_path and os.path.exists(thumbnail_path):
                    upload_kwargs['thumbnail'] = open(thumbnail_path, 'rb')
                
                # Add original dimensions to preserve quality
                if metadata:
                    upload_kwargs['width'] = metadata.get('width')
                    upload_kwargs['height'] = metadata.get('height')
                    upload_kwargs['duration'] = metadata.get('duration')
                
                sent_message = await update.message.reply_video(**upload_kwargs)
                
                # Close thumbnail file if opened
                if thumbnail_path and 'thumbnail' in upload_kwargs:
                    upload_kwargs['thumbnail'].close()
            
            # Cleanup thumbnail
            if thumbnail_path and os.path.exists(thumbnail_path):
                try:
                    os.remove(thumbnail_path)
                    logger.info(f"🗑️ Thumbnail cleaned: {thumbnail_path}")
                except:
                    pass
        else:
            # Non-video file
            sent_message = await update.message.reply_document(
                document=open(file_path, 'rb'),
                caption=caption
            )
        
        logger.info("✅ Upload completed successfully")
        return sent_message  # Return the message object, not True
        
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
                
