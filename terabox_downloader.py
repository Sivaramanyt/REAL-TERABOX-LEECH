"""
Terabox File Downloader - SPEED OPTIMIZED FOR 200-300 KB/s
Multiple techniques to maximize download speed
"""

import os
import asyncio
import requests
import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ContextTypes
from terabox_api import format_size

logger = logging.getLogger(__name__)

# Configuration
DOWNLOAD_DIR = "downloads"
THUMBNAIL_DIR = "thumbnails"
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
CHUNK_SIZE = 4096  # 4KB chunks (optimal for 200-300 KB/s)
MAX_RETRIES = 3

# Video file extensions
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v', '.3gp']

# Thread pool
executor = ThreadPoolExecutor(max_workers=3)

def download_file_sync(url, file_path, total_size=0):
    """
    SPEED OPTIMIZED synchronous download
    Targets 200-300 KB/s speeds
    """
    logger.info(f"⬇️ Starting SPEED OPTIMIZED download: {file_path}")
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"🔄 Download attempt {attempt}/{MAX_RETRIES}")
            
            # Check if partial file exists
            start_byte = 0
            if os.path.exists(file_path) and attempt > 1:
                start_byte = os.path.getsize(file_path)
                logger.info(f"📍 Resuming from byte {start_byte}")
            
            # SPEED OPTIMIZATION 1: Persistent session with connection pooling
            session = requests.Session()
            
            # SPEED OPTIMIZATION 2: Multiple adapters for better connection management
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=10,
                pool_maxsize=20,
                max_retries=0,
                pool_block=False
            )
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            
            # SPEED OPTIMIZATION 3: Optimized headers
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            })
            
            # SPEED OPTIMIZATION 4: Connection warm-up
            if attempt == 1:
                try:
                    logger.info("🔥 Warming up connection for max speed...")
                    warmup = session.head(url, timeout=15)
                    logger.info(f"🔥 Connection ready - Server: {warmup.headers.get('Server', 'Unknown')}")
                    time.sleep(0.5)
                except Exception as e:
                    logger.warning(f"⚠️ Warm-up failed: {e}")
            
            # Set range header for resume
            headers = {}
            if start_byte > 0:
                headers['Range'] = f'bytes={start_byte}-'
            
            # SPEED OPTIMIZATION 5: Longer connect timeout, streaming enabled
            response = session.get(
                url,
                headers=headers,
                stream=True,
                timeout=(45, 900),  # (connect, read) - longer timeouts
                allow_redirects=True
            )
            response.raise_for_status()
            
            # SPEED OPTIMIZATION 6: Check if we got a good server
            server_name = response.headers.get('Server', 'Unknown')
            logger.info(f"📡 Connected to server: {server_name}")
            
            # Open file
            mode = 'ab' if start_byte > 0 else 'wb'
            downloaded = start_byte
            start_time = time.time()
            last_log_time = start_time
            last_log_bytes = downloaded
            
            with open(file_path, mode, buffering=8192) as f:  # Buffered writes
                # SPEED OPTIMIZATION 7: 4KB chunks (sweet spot for 200-300 KB/s)
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Calculate speed every 2 seconds
                        current_time = time.time()
                        if current_time - last_log_time >= 2.0:
                            elapsed = current_time - start_time
                            bytes_since_log = downloaded - last_log_bytes
                            current_speed = bytes_since_log / (current_time - last_log_time)
                            avg_speed = (downloaded - start_byte) / elapsed if elapsed > 0 else 0
                            
                            logger.info(
                                f"📥 Downloaded: {format_size(downloaded)} | "
                                f"Speed: {format_size(current_speed)}/s | "
                                f"Avg: {format_size(avg_speed)}/s"
                            )
                            
                            last_log_time = current_time
                            last_log_bytes = downloaded
            
            session.close()
            
            # Final stats
            final_size = os.path.getsize(file_path)
            total_time = time.time() - start_time
            avg_speed = (final_size - start_byte) / total_time if total_time > 0 else 0
            
            logger.info(
                f"✅ Download completed: {format_size(final_size)} | "
                f"Time: {int(total_time)}s | "
                f"Average speed: {format_size(avg_speed)}/s"
            )
            
            return True
            
        except (requests.exceptions.RequestException, IOError) as e:
            logger.warning(f"⚠️ Attempt {attempt} failed: {e.__class__.__name__}: {str(e)}")
            
            try:
                session.close()
            except:
                pass
            
            if attempt < MAX_RETRIES:
                wait_time = attempt * 2
                logger.info(f"⏳ Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
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

async def download_file(url, file_path, progress_callback=None):
    """Async wrapper for synchronous download"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, download_file_sync, url, file_path, 0)
    
    return True

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
            thumbnail_path = await generate_video_thumbnail(video_path)
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
                
