"""
Terabox File Downloader - WITH RETRY & RESUME
Handles network interruptions and slow connections
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
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB chunks
MAX_RETRIES = 3  # Retry failed downloads 3 times
CONNECT_TIMEOUT = 60  # Seconds to wait for connection
DOWNLOAD_TIMEOUT = 7200  # 2 hours total download time

# Video file extensions
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v', '.3gp']

async def download_file(url, file_path, progress_callback=None):
    """
    Download file with retry and resume capability
    FIXED: Handles "Response payload is not completed" errors
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    logger.info(f"⬇️ Starting download: {file_path}")
    
    # Try multiple times if download fails
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"🔄 Download attempt {attempt}/{MAX_RETRIES}")
            
            # Check if partial file exists (for resume)
            start_byte = 0
            if os.path.exists(file_path) and attempt > 1:
                start_byte = os.path.getsize(file_path)
                logger.info(f"📍 Resuming from byte {start_byte}")
            
            # Create session with longer timeouts
            timeout = aiohttp.ClientTimeout(
                total=DOWNLOAD_TIMEOUT,
                connect=CONNECT_TIMEOUT,
                sock_read=300  # 5 minutes per chunk read
            )
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Set range header for resume
                headers = {}
                if start_byte > 0:
                    headers['Range'] = f'bytes={start_byte}-'
                
                async with session.get(url, headers=headers) as response:
                    if response.status not in [200, 206]:  # 206 = Partial Content
                        raise Exception(f"Download failed with status {response.status}")
                    
                    # Get total size
                    content_length = response.headers.get('content-length')
                    if content_length:
                        total_size = int(content_length) + start_byte
                        logger.info(f"📦 Total file size: {format_size(total_size)}")
                    else:
                        total_size = 0
                        logger.info("📦 File size: Unknown")
                    
                    # Open file in append mode if resuming
                    mode = 'ab' if start_byte > 0 else 'wb'
                    downloaded = start_byte
                    
                    with open(file_path, mode) as f:
                        # Download in chunks with progress
                        async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if progress_callback:
                                await progress_callback(downloaded, total_size if total_size else downloaded)
                            
                            # Log progress every 10MB
                            if downloaded % (10 * 1024 * 1024) < CHUNK_SIZE:
                                logger.info(f"📥 Downloaded: {format_size(downloaded)}")
                    
                    final_size = os.path.getsize(file_path)
                    logger.info(f"✅ Download completed: {format_size(final_size)}")
                    return True
                    
        except (asyncio.TimeoutError, aiohttp.ClientError, aiohttp.ServerDisconnectedError) as e:
            logger.warning(f"⚠️ Attempt {attempt} failed: {e.__class__.__name__}")
            
            if attempt < MAX_RETRIES:
                wait_time = attempt * 5  # Wait 5, 10, 15 seconds
                logger.info(f"⏳ Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ All {MAX_RETRIES} download attempts failed")
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise Exception(f"Download failed after {MAX_RETRIES} attempts: {e}")
                
        except Exception as e:
            logger.error(f"❌ Download error: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)
            raise

async def generate_video_thumbnail(video_path, thumbnail_path=None):
    """Generate thumbnail from video using ffmpeg"""
    try:
        os.makedirs(THUMBNAIL_DIR, exist_ok=True)
        
        if not thumbnail_path:
            thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{os.path.basename(video_path)}_thumb.jpg")
        
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
            logger.warning(f"⚠️ Thumbnail generation failed")
            return None
            
    except Exception as e:
        logger.error(f"❌ Thumbnail generation error: {e}")
        return None

async def get_video_metadata(video_path):
    """Get video metadata using ffprobe"""
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
    """Upload file to Telegram with thumbnails and original quality"""
    try:
        if not os.path.exists(file_path):
            raise Exception("File not found")
        
        file_size = os.path.getsize(file_path)
        logger.info(f"⬆️ Uploading to Telegram: {file_path} ({format_size(file_size)})")
        
        if file_size > MAX_FILE_SIZE:
            raise Exception(f"File too large: {format_size(file_size)}")
        
        is_video = any(file_path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)
        
        sent_message = None
        
        if is_video:
            thumbnail_path = await generate_video_thumbnail(file_path)
            metadata = await get_video_metadata(file_path)
            
            with open(file_path, 'rb') as video_file:
                upload_kwargs = {
                    'video': video_file,
                    'caption': caption,
                    'supports_streaming': True
                }
                
                if thumbnail_path and os.path.exists(thumbnail_path):
                    upload_kwargs['thumbnail'] = open(thumbnail_path, 'rb')
                
                if metadata:
                    upload_kwargs['width'] = metadata.get('width')
                    upload_kwargs['height'] = metadata.get('height')
                    upload_kwargs['duration'] = metadata.get('duration')
                
                sent_message = await update.message.reply_video(**upload_kwargs)
                
                if thumbnail_path and 'thumbnail' in upload_kwargs:
                    upload_kwargs['thumbnail'].close()
            
            if thumbnail_path and os.path.exists(thumbnail_path):
                try:
                    os.remove(thumbnail_path)
                except:
                    pass
        else:
            sent_message = await update.message.reply_document(
                document=open(file_path, 'rb'),
                caption=caption
            )
        
        logger.info("✅ Upload completed successfully")
        return sent_message
        
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
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    return filename
    
