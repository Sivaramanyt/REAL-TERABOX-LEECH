"""
Terabox File Downloader - WORKING VERSION
Handles redirects and chunked encoding properly
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
from telegram.error import BadRequest, RetryAfter
from terabox_api import format_size

logger = logging.getLogger(__name__)

# Configuration
DOWNLOAD_DIR = "downloads"
THUMBNAIL_DIR = "thumbnails"
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
CHUNK_SIZE = 8192  # 8KB chunks
MAX_RETRIES = 3
PROGRESS_UPDATE_INTERVAL = 3

# Video file extensions
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v', '.3gp']

# Thread pool
executor = ThreadPoolExecutor(max_workers=3)

def create_progress_bar(percentage):
    """Create a visual progress bar"""
    filled = int(percentage / 10)
    empty = 10 - filled
    return '█' * filled + '░' * empty

async def update_progress_message(message, downloaded, total_size, speed, start_time):
    """Update Telegram message with download progress"""
    try:
        percentage = (downloaded / total_size * 100) if total_size > 0 else 0
        elapsed = time.time() - start_time
        remaining_bytes = total_size - downloaded
        eta = remaining_bytes / speed if speed > 0 else 0
        
        progress_bar = create_progress_bar(percentage)
        
        progress_text = (
            f"⬇️ **Downloading...**\n\n"
            f"`{progress_bar}` {percentage:.1f}%\n\n"
            f"📦 **Downloaded:** {format_size(downloaded)} / {format_size(total_size)}\n"
            f"⚡ **Speed:** {format_size(speed)}/s\n"
            f"⏱️ **Time Elapsed:** {int(elapsed)}s\n"
            f"⏳ **ETA:** {int(eta)}s remaining"
        )
        
        await message.edit_text(progress_text, parse_mode='Markdown')
    except (BadRequest, RetryAfter):
        pass
    except Exception as e:
        logger.debug(f"Progress update error: {e}")

def download_file_sync_with_progress(url, file_path, total_size, update_func, message_id):
    """
    Synchronous download with proper chunked encoding handling
    """
    logger.info(f"⬇️ Starting download: {file_path}")
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"🔄 Download attempt {attempt}/{MAX_RETRIES}")
            
            start_byte = 0
            if os.path.exists(file_path) and attempt > 1:
                start_byte = os.path.getsize(file_path)
                logger.info(f"📍 Resuming from byte {start_byte}")
            
            # Create session with retry adapter
            session = requests.Session()
            
            # CRITICAL: Disable automatic decompression to handle chunked encoding properly
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=5,
                pool_maxsize=10,
                max_retries=0
            )
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'identity',  # CRITICAL: Disable gzip/deflate
                'Connection': 'keep-alive'
            }
            
            if start_byte > 0:
                headers['Range'] = f'bytes={start_byte}-'
            
            # Warm-up on first attempt
            if attempt == 1:
                try:
                    logger.info("🔥 Warming up connection...")
                    session.head(url, timeout=15, allow_redirects=True)
                    time.sleep(0.5)
                except:
                    pass
            
            # Download with streaming
            response = session.get(
                url,
                headers=headers,
                stream=True,  # CRITICAL: Enable streaming
                timeout=(45, 900),
                allow_redirects=True  # CRITICAL: Follow redirects
            )
            
            response.raise_for_status()
            
            # Get total size
            if not total_size:
                content_length = response.headers.get('content-length')
                if content_length:
                    total_size = int(content_length) + start_byte
                else:
                    total_size = 0
            
            logger.info(f"📦 Total size: {format_size(total_size)}")
            
            # Download
            mode = 'ab' if start_byte > 0 else 'wb'
            downloaded = start_byte
            start_time = time.time()
            last_update_time = start_time
            last_update_bytes = downloaded
            
            progress_state = {
                'downloaded': downloaded,
                'total_size': total_size,
                'speed': 0,
                'start_time': start_time
            }
            
            with open(file_path, mode) as f:
                # CRITICAL: Use iter_content with decode_unicode=False
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE, decode_unicode=False):
                    if chunk:  # Filter out keep-alive new chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        current_time = time.time()
                        
                        # Update progress
                        if current_time - last_update_time >= PROGRESS_UPDATE_INTERVAL:
                            bytes_since_update = downloaded - last_update_bytes
                            time_since_update = current_time - last_update_time
                            current_speed = bytes_since_update / time_since_update if time_since_update > 0 else 0
                            
                            progress_state['downloaded'] = downloaded
                            progress_state['speed'] = current_speed
                            
                            if update_func:
                                update_func(progress_state)
                            
                            logger.info(f"📥 Downloaded: {format_size(downloaded)} - Speed: {format_size(current_speed)}/s")
                            
                            last_update_time = current_time
                            last_update_bytes = downloaded
            
            session.close()
            
            final_size = os.path.getsize(file_path)
            total_time = time.time() - start_time
            avg_speed = (final_size - start_byte) / total_time if total_time > 0 else 0
            
            logger.info(
                f"✅ Download completed: {format_size(final_size)} | "
                f"Time: {int(total_time)}s | "
                f"Speed: {format_size(avg_speed)}/s"
            )
            
            return True
            
        except Exception as e:
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
                logger.error(f"❌ All attempts failed")
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise Exception(f"Download failed: {e}")

async def download_file(url, file_path, total_size=0, status_message=None):
    """Async wrapper with live Telegram progress updates"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    progress_data = {'downloaded': 0, 'total_size': total_size, 'speed': 0, 'start_time': time.time()}
    last_message_update = time.time()
    
    def progress_callback(state):
        nonlocal progress_data, last_message_update
        progress_data.update(state)
        
        current_time = time.time()
        if status_message and current_time - last_message_update >= PROGRESS_UPDATE_INTERVAL:
            asyncio.create_task(
                update_progress_message(
                    status_message,
                    state['downloaded'],
                    state['total_size'],
                    state['speed'],
                    state['start_time']
                )
            )
            last_message_update = current_time
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        executor,
        download_file_sync_with_progress,
        url,
        file_path,
        total_size,
        progress_callback,
        None
    )
    
    return True

async def generate_video_thumbnail(video_path, thumbnail_path=None):
    """Generate thumbnail from video"""
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
        
        await process.communicate()
        
        if process.returncode == 0 and os.path.exists(thumbnail_path):
            logger.info(f"✅ Thumbnail generated")
            return thumbnail_path
        return None
            
    except Exception as e:
        logger.error(f"❌ Thumbnail error: {e}")
        return None

async def get_video_metadata(video_path):
    """Get video metadata"""
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
        
        stdout, _ = await process.communicate()
        
        if process.returncode == 0:
            import json
            data = json.loads(stdout.decode())
            
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    return {
                        'width': int(stream.get('width', 0)),
                        'height': int(stream.get('height', 0)),
                        'duration': int(float(data.get('format', {}).get('duration', 0)))
                    }
        return None
    except:
        return None

async def upload_to_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                             file_path, caption, file_info=None):
    """Upload file to Telegram"""
    try:
        if not os.path.exists(file_path):
            raise Exception("File not found")
        
        file_size = os.path.getsize(file_path)
        logger.info(f"⬆️ Uploading: {format_size(file_size)}")
        
        if file_size > MAX_FILE_SIZE:
            raise Exception(f"File too large: {format_size(file_size)}")
        
        is_video = any(file_path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)
        
        if is_video:
            thumbnail_path = await generate_video_thumbnail(file_path)
            metadata = await get_video_metadata(file_path)
            
            with open(file_path, 'rb') as video_file:
                kwargs = {
                    'video': video_file,
                    'caption': caption,
                    'supports_streaming': True
                }
                
                if thumbnail_path:
                    kwargs['thumbnail'] = open(thumbnail_path, 'rb')
                
                if metadata:
                    kwargs.update(metadata)
                
                sent_message = await update.message.reply_video(**kwargs)
                
                if thumbnail_path and 'thumbnail' in kwargs:
                    kwargs['thumbnail'].close()
                    os.remove(thumbnail_path)
        else:
            sent_message = await update.message.reply_document(
                document=open(file_path, 'rb'),
                caption=caption
            )
        
        logger.info("✅ Upload completed")
        return sent_message
        
    except Exception as e:
        logger.error(f"❌ Upload error: {e}")
        raise

def cleanup_file(file_path):
    """Remove file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"🗑️ Cleaned up: {file_path}")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

def get_safe_filename(filename):
    """Safe filename"""
    import re
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    return filename
    
