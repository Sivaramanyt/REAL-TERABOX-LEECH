"""
Terabox File Downloader - FIRST ATTEMPT OPTIMIZED
Pre-warms connection to avoid ClientPayloadError
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
MAX_RETRIES = 3
CONNECT_TIMEOUT = 90  # Increased from 60
DOWNLOAD_TIMEOUT = 7200

# Video file extensions
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v', '.3gp']

async def warm_up_connection(session, url):
    """
    Pre-warm connection with HEAD request
    This prevents ClientPayloadError on first download attempt
    """
    try:
        logger.info("🔥 Warming up connection...")
        async with session.head(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            logger.info(f"✅ Connection warmed up - Status: {response.status}")
            await asyncio.sleep(1)  # Small delay to stabilize
            return True
    except Exception as e:
        logger.warning(f"⚠️ Warm-up failed (non-critical): {e}")
        return False

async def download_file(url, file_path, progress_callback=None):
    """
    Download file with connection warm-up for first attempt success
    OPTIMIZED: Reduces ClientPayloadError significantly
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    logger.info(f"⬇️ Starting download: {file_path}")
    
    # Configure session with optimized settings
    connector = aiohttp.TCPConnector(
        limit=10,
        limit_per_host=5,
        ttl_dns_cache=300,
        force_close=False,  # Keep connection alive
        enable_cleanup_closed=True
    )
    
    timeout = aiohttp.ClientTimeout(
        total=DOWNLOAD_TIMEOUT,
        connect=CONNECT_TIMEOUT,
        sock_read=600  # 10 minutes per chunk
    )
    
    # Enhanced headers for better connection
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive'
    }
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"🔄 Download attempt {attempt}/{MAX_RETRIES}")
            
            # Check if partial file exists (for resume)
            start_byte = 0
            if os.path.exists(file_path) and attempt > 1:
                start_byte = os.path.getsize(file_path)
                logger.info(f"📍 Resuming from byte {start_byte}")
            
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=headers
            ) as session:
                
                # CRITICAL: Warm up connection on first attempt
                if attempt == 1:
                    await warm_up_connection(session, url)
                
                # Set range header for resume
                request_headers = {}
                if start_byte > 0:
                    request_headers['Range'] = f'bytes={start_byte}-'
                
                async with session.get(url, headers=request_headers) as response:
                    if response.status not in [200, 206]:
                        raise Exception(f"Download failed with status {response.status}")
                    
                    # Get total size
                    content_length = response.headers.get('content-length')
                    if content_length:
                        total_size = int(content_length) + start_byte
                        logger.info(f"📦 Total file size: {format_size(total_size)}")
                    else:
                        total_size = 0
                        logger.info("📦 File size: Unknown")
                    
                    # Open file
                    mode = 'ab' if start_byte > 0 else 'wb'
                    downloaded = start_byte
                    last_log = 0
                    
                    with open(file_path, mode) as f:
                        # Download in chunks
                        async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if progress_callback:
                                await progress_callback(downloaded, total_size if total_size else downloaded)
                            
                            # Log progress every 1MB (less spam)
                            if downloaded - last_log >= 1024 * 1024:
                                logger.info(f"📥 Downloaded: {format_size(downloaded)}")
                                last_log = downloaded
                    
                    final_size = os.path.getsize(file_path)
                    logger.info(f"✅ Download completed: {format_size(final_size)}")
                    return True
                    
        except (asyncio.TimeoutError, aiohttp.ClientError, aiohttp.ServerDisconnectedError) as e:
            logger.warning(f"⚠️ Attempt {attempt} failed: {e.__class__.__name__}")
            
            if attempt < MAX_RETRIES:
                wait_time = attempt * 3  # Wait 3, 6, 9 seconds (reduced from 5, 10, 15)
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
        finally:
            # Cleanup connector
            if 'connector' in locals():
                await connector.close()

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
        
