"""
Terabox File Downloader - OPTIMIZED FOR 200-300 KB/s
Professional production-ready code
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
from telegram.error import BadRequest, RetryAfter, TimedOut, NetworkError
from terabox_api import format_size

logger = logging.getLogger(__name__)

# Configuration
DOWNLOAD_DIR = "downloads"
THUMBNAIL_DIR = "thumbnails"
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
CHUNK_SIZE = 16384  # 16KB chunks for optimal speed
MAX_RETRIES = 2  # Reduce retries since first attempt should work
PROGRESS_UPDATE_INTERVAL = 4
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
            f"⏱️ **Elapsed:** {int(elapsed)}s | **ETA:** {int(eta)}s"
        )
        
        await message.edit_text(progress_text, parse_mode='Markdown')
    except (BadRequest, RetryAfter):
        pass
    except Exception as e:
        logger.debug(f"Progress update skipped: {e}")

def download_file_sync_optimized(url, file_path, total_size, update_func):
    """
    OPTIMIZED download for 200-300 KB/s speeds
    """
    logger.info(f"⬇️ Starting optimized download: {file_path}")
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"🔄 Attempt {attempt}/{MAX_RETRIES}")
            
            # Remove partial file
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Create session with optimizations
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'identity',  # Disable compression
                'Connection': 'keep-alive',
                'DNT': '1'
            })
            
            # Get file info first
            logger.info("🔍 Getting file info...")
            head_response = session.head(url, timeout=20, allow_redirects=True)
            final_url = head_response.url
            logger.info(f"✅ Final URL obtained")
            
            # Download with streaming
            response = session.get(
                final_url,
                stream=True,
                timeout=(30, 1200),  # Longer read timeout
                allow_redirects=False  # Already redirected
            )
            response.raise_for_status()
            
            # Get total size
            if not total_size:
                total_size = int(response.headers.get('content-length', 0))
            
            logger.info(f"📦 Total size: {format_size(total_size)}")
            
            # Download with progress
            downloaded = 0
            start_time = time.time()
            last_update_time = start_time
            last_update_bytes = 0
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE, decode_unicode=False):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        current_time = time.time()
                        
                        # Update progress
                        if current_time - last_update_time >= PROGRESS_UPDATE_INTERVAL:
                            bytes_since_update = downloaded - last_update_bytes
                            time_since_update = current_time - last_update_time
                            speed = bytes_since_update / time_since_update if time_since_update > 0 else 0
                            
                            if update_func:
                                update_func({
                                    'downloaded': downloaded,
                                    'total_size': total_size,
                                    'speed': speed,
                                    'start_time': start_time
                                })
                            
                            logger.info(f"📥 {int((downloaded/total_size)*100)}% - {format_size(speed)}/s")
                            last_update_time = current_time
                            last_update_bytes = downloaded
            
            session.close()
            
            final_size = os.path.getsize(file_path)
            total_time = time.time() - start_time
            avg_speed = final_size / total_time if total_time > 0 else 0
            
            logger.info(f"✅ Completed: {format_size(final_size)} in {int(total_time)}s - {format_size(avg_speed)}/s")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Attempt {attempt} failed: {str(e)}")
            
            try:
                session.close()
            except:
                pass
            
            if attempt < MAX_RETRIES:
                time.sleep(2)
            else:
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise

async def download_file(url, file_path, total_size=0, status_message=None):
    """Async wrapper with live progress"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    last_message_update = time.time()
    
    def progress_callback(state):
        nonlocal last_message_update
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
    await loop.run_in_executor(executor, download_file_sync_optimized, url, file_path, total_size, progress_callback)
    return True

async def generate_video_thumbnail(video_path):
    """Generate thumbnail"""
    try:
        os.makedirs(THUMBNAIL_DIR, exist_ok=True)
        thumb_path = os.path.join(THUMBNAIL_DIR, f"{os.path.basename(video_path)}_thumb.jpg")
        
        proc = await asyncio.create_subprocess_exec(
            'ffmpeg', '-i', video_path, '-ss', '00:00:01', '-vframes', '1',
            '-vf', 'scale=320:-1', '-y', thumb_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        
        return thumb_path if proc.returncode == 0 and os.path.exists(thumb_path) else None
    except:
        return None

async def get_video_metadata(video_path):
    """Get video metadata"""
    try:
        proc = await asyncio.create_subprocess_exec(
            'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', '-show_format', video_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        
        if proc.returncode == 0:
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

async def upload_to_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE, file_path, caption, file_info=None):
    """Upload with increased timeout"""
    try:
        if not os.path.exists(file_path):
            raise Exception("File not found")
        
        file_size = os.path.getsize(file_path)
        logger.info(f"⬆️ Uploading: {format_size(file_size)}")
        
        if file_size > MAX_FILE_SIZE:
            raise Exception(f"File too large")
        
        is_video = any(file_path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)
        
        # INCREASED TIMEOUT for upload
        upload_timeout = 300  # 5 minutes
        
        if is_video:
            thumb = await generate_video_thumbnail(file_path)
            meta = await get_video_metadata(file_path)
            
            with open(file_path, 'rb') as f:
                kwargs = {'video': f, 'caption': caption, 'supports_streaming': True, 'read_timeout': upload_timeout, 'write_timeout': upload_timeout}
                if thumb:
                    kwargs['thumbnail'] = open(thumb, 'rb')
                if meta:
                    kwargs.update(meta)
                
                msg = await update.message.reply_video(**kwargs)
                
                if thumb and 'thumbnail' in kwargs:
                    kwargs['thumbnail'].close()
                    try:
                        os.remove(thumb)
                    except:
                        pass
        else:
            with open(file_path, 'rb') as f:
                msg = await update.message.reply_document(
                    document=f, caption=caption,
                    read_timeout=upload_timeout, write_timeout=upload_timeout
                )
        
        logger.info("✅ Upload completed")
        return msg
        
    except (TimedOut, NetworkError) as e:
        logger.error(f"❌ Upload timeout/network error: {e}")
        raise Exception(f"Upload failed: Network issue")
    except Exception as e:
        logger.error(f"❌ Upload error: {e}")
        raise

def cleanup_file(file_path):
    """Remove file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"🗑️ Cleaned: {file_path}")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

def get_safe_filename(filename):
    """Safe filename"""
    import re
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:190] + ext
    return filename
    
