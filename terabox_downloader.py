"""
Terabox Downloader - FIXED with reliable requests library
"""

import os
import logging
import time
import subprocess
import requests
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest, TimedOut, NetworkError

from terabox_api import format_size

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = "downloads"
CHUNK_SIZE = 8192  # 8KB chunks
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v', '.3gp']

def create_progress_bar(percentage):
    """Create visual progress bar"""
    filled = int(percentage / 10)
    empty = 10 - filled
    return '█' * filled + '░' * empty

def generate_thumbnail(video_path):
    """
    Generate thumbnail from video using ffmpeg
    Returns thumbnail path or None
    """
    try:
        thumb_path = video_path + "_thumb.jpg"
        
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-ss', '00:00:01.000',
            '-vframes', '1',
            '-vf', 'scale=320:320:force_original_aspect_ratio=decrease',
            '-y',
            thumb_path
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )
        
        if result.returncode == 0 and os.path.exists(thumb_path):
            logger.info(f"✅ Thumbnail generated: {thumb_path}")
            return thumb_path
        else:
            logger.warning(f"⚠️ Thumbnail generation failed")
            return None
            
    except Exception as e:
        logger.error(f"❌ Thumbnail error: {e}")
        return None

async def update_progress(message, downloaded, total_size, start_time):
    """Update download progress message"""
    try:
        if total_size == 0:
            return
        
        percentage = (downloaded / total_size) * 100
        elapsed = time.time() - start_time
        speed = downloaded / elapsed if elapsed > 0 else 0
        remaining_bytes = total_size - downloaded
        eta = remaining_bytes / speed if speed > 0 else 0
        
        progress_bar = create_progress_bar(percentage)
        
        text = (
            f"⬇️ **Downloading...**\n\n"
            f"`{progress_bar}` {percentage:.1f}%\n\n"
            f"📦 {format_size(downloaded)} / {format_size(total_size)}\n"
            f"⚡ {format_size(speed)}/s\n"
            f"⏱️ ETA: {int(eta)}s"
        )
        
        await message.edit_text(text, parse_mode='Markdown')
        
    except (BadRequest, TimedOut):
        pass
    except Exception as e:
        logger.debug(f"Progress update error: {e}")

async def download_file(url, filename, status_message=None):
    """
    Download file using requests (FIXED - More reliable than aiohttp)
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    
    try:
        logger.info(f"⬇️ Starting download: {filename}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Connection': 'keep-alive',
        }
        
        # Use requests with stream=True
        response = requests.get(url, headers=headers, stream=True, timeout=(30, 300))
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        if total_size > MAX_FILE_SIZE:
            raise Exception(f"File too large: {format_size(total_size)} (Max: 2GB)")
        
        downloaded = 0
        start_time = time.time()
        last_update = 0
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Update progress every 3 seconds
                    current_time = time.time()
                    if status_message and (current_time - last_update >= 3):
                        import asyncio
                        try:
                            await update_progress(status_message, downloaded, total_size, start_time)
                        except:
                            pass
                        last_update = current_time
        
        total_time = time.time() - start_time
        avg_speed = downloaded / total_time if total_time > 0 else 0
        
        logger.info(f"✅ Download complete: {format_size(downloaded)} in {int(total_time)}s - {format_size(avg_speed)}/s")
        
        return file_path
        
    except requests.Timeout:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise Exception("Download timeout - server took too long")
    except requests.ConnectionError:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise Exception("Connection error - check internet connection")
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise Exception(f"Download failed: {str(e)}")

async def upload_to_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE, file_path, caption):
    """Upload file to Telegram with thumbnail support"""
    try:
        if not os.path.exists(file_path):
            raise Exception("File not found after download")
        
        file_size = os.path.getsize(file_path)
        logger.info(f"⬆️ Uploading to Telegram: {format_size(file_size)}")
        
        is_video = any(file_path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)
        
        thumb_path = None
        sent_msg = None
        
        try:
            with open(file_path, 'rb') as f:
                if is_video:
                    # Generate thumbnail for video
                    logger.info("📸 Generating thumbnail...")
                    thumb_path = generate_thumbnail(file_path)
                    
                    # Upload video with thumbnail
                    if thumb_path and os.path.exists(thumb_path):
                        with open(thumb_path, 'rb') as thumb:
                            sent_msg = await update.message.reply_video(
                                video=f,
                                caption=caption,
                                thumbnail=thumb,
                                supports_streaming=True,
                                read_timeout=300,
                                write_timeout=300
                            )
                    else:
                        # Upload without thumbnail if generation failed
                        sent_msg = await update.message.reply_video(
                            video=f,
                            caption=caption,
                            supports_streaming=True,
                            read_timeout=300,
                            write_timeout=300
                        )
                else:
                    # Upload as document
                    sent_msg = await update.message.reply_document(
                        document=f,
                        caption=caption,
                        read_timeout=300,
                        write_timeout=300
                    )
        
        finally:
            # Cleanup thumbnail
            if thumb_path and os.path.exists(thumb_path):
                try:
                    os.remove(thumb_path)
                    logger.info("🗑️ Thumbnail cleaned up")
                except:
                    pass
        
        logger.info("✅ Upload complete")
        return sent_msg
        
    except (TimedOut, NetworkError) as e:
        raise Exception(f"Upload failed: Network issue - {str(e)}")
    except Exception as e:
        raise Exception(f"Upload error: {str(e)}")

def cleanup_file(file_path):
    """Delete downloaded file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"🗑️ Cleaned up: {file_path}")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        
