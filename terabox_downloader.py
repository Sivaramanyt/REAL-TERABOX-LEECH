"""
Terabox File Downloader - SPEED OPTIMIZED
Multi-threaded download + Larger chunks + Thumbnails
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
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB chunks (increased from 1MB)
CONCURRENT_DOWNLOADS = 4  # Number of parallel download threads

# Video file extensions
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v', '.3gp']

async def download_file_chunk(session, url, start, end, file_path, chunk_num):
    """Download a specific chunk of the file"""
    try:
        headers = {'Range': f'bytes={start}-{end}'}
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=600)) as response:
            if response.status in [200, 206]:  # 206 = Partial Content
                chunk_data = await response.read()
                
                # Write chunk to temporary file
                chunk_file = f"{file_path}.part{chunk_num}"
                with open(chunk_file, 'wb') as f:
                    f.write(chunk_data)
                
                logger.info(f"✅ Chunk {chunk_num} downloaded: {format_size(len(chunk_data))}")
                return chunk_num, len(chunk_data)
            else:
                raise Exception(f"Chunk {chunk_num} failed with status {response.status}")
    except Exception as e:
        logger.error(f"❌ Chunk {chunk_num} error: {e}")
        raise

async def download_file(url, file_path, progress_callback=None):
    """
    Multi-threaded file download with progress tracking
    SPEED OPTIMIZED: 4x parallel downloads
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        logger.info(f"⬇️ Starting SPEED download: {file_path}")
        
        async with aiohttp.ClientSession() as session:
            # Get file size first
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                total_size = int(response.headers.get('content-length', 0))
                supports_range = 'bytes' in response.headers.get('accept-ranges', '')
            
            logger.info(f"📦 File size: {format_size(total_size)}, Range support: {supports_range}")
            
            # If server doesn't support range requests, fall back to single download
            if not supports_range or total_size < 5 * 1024 * 1024:  # Less than 5MB
                logger.info("📥 Using single-threaded download")
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=3600)) as response:
                    if response.status != 200:
                        raise Exception(f"Download failed with status {response.status}")
                    
                    downloaded = 0
                    with open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback:
                                await progress_callback(downloaded, total_size)
                    
                    logger.info(f"✅ Download completed: {format_size(downloaded)}")
                    return True
            
            # Multi-threaded download for large files
            logger.info(f"🚀 Using {CONCURRENT_DOWNLOADS}-thread download")
            
            # Calculate chunk ranges
            chunk_size = total_size // CONCURRENT_DOWNLOADS
            download_tasks = []
            
            for i in range(CONCURRENT_DOWNLOADS):
                start = i * chunk_size
                end = start + chunk_size - 1 if i < CONCURRENT_DOWNLOADS - 1 else total_size - 1
                
                task = download_file_chunk(session, url, start, end, file_path, i)
                download_tasks.append(task)
            
            # Download all chunks in parallel
            chunk_results = await asyncio.gather(*download_tasks, return_exceptions=True)
            
            # Check for errors
            for result in chunk_results:
                if isinstance(result, Exception):
                    raise result
            
            # Merge chunks into final file
            logger.info("🔗 Merging chunks...")
            with open(file_path, 'wb') as final_file:
                for i in range(CONCURRENT_DOWNLOADS):
                    chunk_file = f"{file_path}.part{i}"
                    if os.path.exists(chunk_file):
                        with open(chunk_file, 'rb') as cf:
                            final_file.write(cf.read())
                        os.remove(chunk_file)  # Cleanup chunk
            
            downloaded_size = os.path.getsize(file_path)
            logger.info(f"✅ SPEED download completed: {format_size(downloaded_size)}")
            return True
                
    except asyncio.TimeoutError:
        logger.error("❌ Download timeout")
        cleanup_chunks(file_path)
        raise Exception("Download timed out")
    except Exception as e:
        logger.error(f"❌ Download error: {e}")
        cleanup_chunks(file_path)
        raise

def cleanup_chunks(file_path):
    """Remove partial chunk files"""
    try:
        for i in range(CONCURRENT_DOWNLOADS):
            chunk_file = f"{file_path}.part{i}"
            if os.path.exists(chunk_file):
                os.remove(chunk_file)
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

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
    
