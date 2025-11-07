"""
Terabox Downloader - robust headers + cancel + split-while-downloading + throughput tuning
"""
import os
import logging
import time
import subprocess
import requests
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest, TimedOut, NetworkError

from terabox_api import format_size

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = "downloads"
CHUNK_SIZE = int(os.getenv("DOWNLOAD_CHUNK_KB", "512")) * 1024  # default 512 KB
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v', '.3gp']
THUMBNAIL_MAX_MB = int(os.getenv("THUMBNAIL_MAX_MB", "300"))

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

def create_progress_bar(percentage: float) -> str:
    filled = int(percentage / 10)
    empty = 10 - filled
    return '█' * filled + '░' * empty

def generate_thumbnail(video_path):
    try:
        thumb_path = video_path + "_thumb.jpg"
        cmd = [
            'ffmpeg', '-i', video_path, '-ss', '00:00:01.000', '-vframes', '1',
            '-vf', 'scale=320:320:force_original_aspect_ratio=decrease', '-y', thumb_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        if result.returncode == 0 and os.path.exists(thumb_path):
            logger.info(f"✅ Thumbnail generated: {thumb_path}")
            return thumb_path
        logger.warning("⚠️ Thumbnail generation failed")
        return None
    except Exception as e:
        logger.error(f"❌ Thumbnail error: {e}")
        return None

async def update_progress(message, downloaded, total_size, start_time):
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

def _open_part(base_path: str, idx: int):
    part_path = f"{base_path}.part{idx:02d}"
    return part_path, open(part_path, "wb")

async def download_file(
    url: str,
    filename: str,
    status_message=None,
    referer: Optional[str] = None,
    cancel_event=None,
    split_enabled: bool = False,
    split_part_mb: int = 200
) -> str | list[str]:
    """
    Stream download with browser-like headers, Referer, cancel support, and optional on-disk splitting.
    Returns a single path (no split) or list of part paths (split).
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    base_path = os.path.join(DOWNLOAD_DIR, filename)

    referer_chain = [r for r in [referer, "https://teraboxapp.com/", "https://www.terabox.com/", "https://1024tera.com/"] if r]
    part_limit = split_part_mb * 1024 * 1024
    last_err = None

    def try_request(headers):
        return requests.get(url, headers=headers, stream=True, timeout=(30, 300), allow_redirects=True)

    for r in referer_chain:
        headers = {
            "User-Agent": DEFAULT_UA,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Referer": r,
            "Range": "bytes=0-",
        }
        try:
            resp = try_request(headers)
            if resp.status_code == 403:
                last_err = f"403 with Referer={r}"
                logger.warning(last_err)
                continue
            resp.raise_for_status()

            # reopen without Range for better throughput
            headers_no_range = dict(headers); headers_no_range.pop("Range", None)
            try:
                resp2 = try_request(headers_no_range)
                if resp2.status_code in (200, 206):
                    resp.close()
                    resp = resp2
            except Exception:
                pass

            total_size = int(resp.headers.get("content-length", "0"))
            if total_size and total_size > MAX_FILE_SIZE:
                resp.close()
                raise Exception(f"File too large: {format_size(total_size)} (Max: 2GB)")

            parts: list[str] = []
            part_idx = 1
            written_in_part = 0
            downloaded = 0
            start_time = time.time()
            last_update = 0

            if split_enabled:
                part_path, f = _open_part(base_path, part_idx)
                parts.append(part_path)
            else:
                f = open(base_path, "wb")

            with f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if cancel_event and cancel_event.is_set():
                        resp.close()
                        raise Exception("Cancelled by user")
                    if not chunk:
                        continue

                    if split_enabled and written_in_part + len(chunk) > part_limit:
                        remain = part_limit - written_in_part
                        if remain > 0:
                            f.write(chunk[:remain])
                            downloaded += remain
                            written_in_part += remain
                            chunk = chunk[remain:]
                        f.close()
                        part_idx += 1
                        written_in_part = 0
                        part_path, f = _open_part(base_path, part_idx)
                        parts.append(part_path)

                    f.write(chunk)
                    downloaded += len(chunk)
                    if split_enabled:
                        written_in_part += len(chunk)

                    current_time = time.time()
                    if status_message and (current_time - last_update >= 6):
                        try:
                            await update_progress(status_message, downloaded, total_size, start_time)
                        except:
                            pass
                        last_update = current_time

            resp.close()
            if split_enabled:
                return parts
            return base_path

        except requests.Timeout as e:
            last_err = f"timeout with Referer={r}: {e}"
            logger.warning(last_err)
        except requests.ConnectionError as e:
            last_err = f"connection error with Referer={r}: {e}"
            logger.warning(last_err)
        except Exception as e:
            last_err = str(e)
            logger.warning(f"attempt with Referer={r} failed: {e}")

        # cleanup partials
        try:
            if split_enabled:
                base_dir = os.path.dirname(base_path)
                for fn in os.listdir(base_dir):
                    if fn.startswith(os.path.basename(base_path) + ".part"):
                        try: os.remove(os.path.join(base_dir, fn))
                        except: pass
            else:
                if os.path.exists(base_path):
                    try: os.remove(base_path)
                    except: pass
        except:
            pass

    raise Exception(f"Download failed: {last_err or 'unknown error'}")

async def upload_to_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE, file_path, caption):
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
                if is_video and file_size <= THUMBNAIL_MAX_MB * 1024 * 1024:
                    logger.info("📸 Generating thumbnail...")
                    thumb_path = generate_thumbnail(file_path)
                    if thumb_path and os.path.exists(thumb_path):
                        with open(thumb_path, 'rb') as thumb:
                            sent_msg = await update.message.reply_video(
                                video=f, caption=caption, thumbnail=thumb,
                                supports_streaming=True, read_timeout=300, write_timeout=300
                            )
                    else:
                        sent_msg = await update.message.reply_video(
                            video=f, caption=caption, supports_streaming=True,
                            read_timeout=300, write_timeout=300
                        )
                else:
                    if is_video:
                        sent_msg = await update.message.reply_video(
                            video=f, caption=caption, supports_streaming=True,
                            read_timeout=300, write_timeout=300
                        )
                    else:
                        sent_msg = await update.message.reply_document(
                            document=f, caption=caption, read_timeout=300, write_timeout=300
                        )
        finally:
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
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"🗑️ Cleaned up: {file_path}")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
    
