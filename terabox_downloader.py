"""
Terabox Downloader - video-first uploads with safe segmentation, robust headers,
cancel support, and throughput tuning.
"""

import os
import glob
import logging
import time
import subprocess
import requests
from typing import Optional, List

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest, TimedOut, NetworkError

from terabox_api import format_size

logger = logging.getLogger(__name__)

# ===== Tunables (use env to tweak without code edits) =====
DOWNLOAD_DIR = "downloads"
CHUNK_SIZE = int(os.getenv("DOWNLOAD_CHUNK_KB", "768")) * 1024      # 768 KB default (good throughput) [env]
PROGRESS_INTERVAL_SEC = int(os.getenv("PROGRESS_INTERVAL_SEC", "8")) # edit progress every 8s [env]
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024                               # 2GB cap
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v', '.3gp']

# Video-first policy (no document fallback)
FORCE_VIDEO_UPLOAD = os.getenv("FORCE_VIDEO_UPLOAD", "true").lower() == "true"       # keep video always [env]
DISABLE_THUMBNAIL = os.getenv("DISABLE_THUMBNAIL", "true").lower() == "true"         # avoid ffmpeg spikes [env]
VIDEO_SEGMENT_THRESHOLD_MB = int(os.getenv("VIDEO_SEGMENT_THRESHOLD_MB", "300"))     # segment when >= 300MB [env]
VIDEO_SEGMENT_TIME_SEC = int(os.getenv("VIDEO_SEGMENT_TIME_SEC", "360"))             # ~6 min per segment [env]

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

def create_progress_bar(percentage: float) -> str:
    filled = int(percentage / 10)
    empty = 10 - filled
    return '█' * filled + '░' * empty

async def update_progress(message, downloaded, total_size, start_time):
    """Edit a progress message at a controlled interval to reduce backpressure."""
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

def _segment_output_paths(base_name: str) -> List[str]:
    # e.g., movie.mp4 -> movie_seg000.mp4, movie_seg001.mp4, ...
    root, ext = os.path.splitext(base_name)
    pattern = os.path.join(DOWNLOAD_DIR, f"{root}_seg%03d.mp4")
    glob_pattern = os.path.join(DOWNLOAD_DIR, f"{root}_seg*.mp4")
    return pattern, glob_pattern

def segment_video(input_path: str, segment_time_sec: int) -> List[str]:
    """
    Split video into valid MP4 chunks without re-encoding using ffmpeg segmenter.
    Returns list of segment file paths.
    """
    try:
        base_name = os.path.basename(input_path)
        out_pattern, glob_pattern = _segment_output_paths(base_name)

        # Cleanup any old segments
        for old in glob.glob(glob_pattern):
            try: os.remove(old)
            except: pass

        cmd = [
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-i', input_path,
            '-c', 'copy',              # no re-encode = low CPU/RAM
            '-map', '0',
            '-f', 'segment',
            '-segment_time', str(segment_time_sec),
            '-reset_timestamps', '1',
            out_pattern
        ]
        logger.info(f"🎬 Segmenting video: {' '.join(cmd)}")
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=None)
        if res.returncode != 0:
            raise Exception(f"ffmpeg segment failed: {res.stderr.decode(errors='ignore')[:400]}")

        paths = sorted(glob.glob(glob_pattern))
        if not paths:
            raise Exception("ffmpeg produced no segments")
        logger.info(f"✅ Segments ready: {len(paths)} parts")
        return paths
    except Exception as e:
        raise Exception(f"Segment error: {str(e)}")

async def download_file(
    url: str,
    filename: str,
    status_message=None,
    referer: Optional[str] = None,
    cancel_event=None,
    split_enabled: bool = False,   # byte-split kept for non-video paths; video uses segmentation after download
    split_part_mb: int = 200
) -> str | list[str]:
    """
    Stream download with browser-like headers, Referer, cancel support, optional on-disk byte splitting.
    For video-first uploads, keep split_enabled=False so the full file exists for ffmpeg segmentation.
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    base_path = os.path.join(DOWNLOAD_DIR, filename)

    referer_chain = [r for r in [referer, "https://teraboxapp.com/", "https://www.terabox.com/", "https://1024tera.com/"] if r]
    part_limit = split_part_mb * 1024 * 1024
    last_err = None

    def try_request(headers):
        return requests.get(
            url, headers=headers, stream=True,
            timeout=(30, 300), allow_redirects=True
        )

    for r in referer_chain:
        headers = {
            "User-Agent": DEFAULT_UA,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",   # prefer raw stream for big files
            "Connection": "keep-alive",
            "Referer": r,
            "Range": "bytes=0-",             # probe to satisfy hotlink checks
        }
        try:
            resp = try_request(headers)
            if resp.status_code == 403:
                last_err = f"403 with Referer={r}"
                logger.warning(last_err)
                continue
            resp.raise_for_status()

            # Reopen without Range to improve throughput after validation
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

            parts: List[str] = []
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
                    if status_message and (current_time - last_update >= PROGRESS_INTERVAL_SEC):
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

        # Cleanup partials before next referer attempt
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
    """
    Pure video path: sendVideo for small/medium files; for large files, first segment into valid MP4s
    and send each segment via sendVideo. No document fallback to honor video-only requirement.
    """
    try:
        if not os.path.exists(file_path):
            raise Exception("File not found after download")

        file_size = os.path.getsize(file_path)
        logger.info(f"⬆️ Uploading to Telegram: {format_size(file_size)}")

        is_video = any(file_path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)
        if not is_video:
            # If non-video, still send as document (can’t be video)
            with open(file_path, 'rb') as f:
                sent = await update.message.reply_document(
                    document=f, caption=caption, read_timeout=300, write_timeout=300
                )
            return sent

        # 1) Large video -> segment to valid MP4 chunks, then sendVideo for each
        if file_size >= VIDEO_SEGMENT_THRESHOLD_MB * 1024 * 1024:
            seg_paths = segment_video(file_path, VIDEO_SEGMENT_TIME_SEC)
            last_sent = None
            total_parts = len(seg_paths)
            idx = 1
            for p in seg_paths:
                with open(p, 'rb') as f:
                    part_caption = f"{caption}\n🧩 Part {idx}/{total_parts}"
                    last_sent = await update.message.reply_video(
                        video=f, caption=part_caption, supports_streaming=True,
                        read_timeout=300, write_timeout=300
                    )
                # cleanup segment immediately
                try: os.remove(p)
                except: pass
                idx += 1
            return last_sent

        # 2) Small/medium video -> sendVideo directly (no thumbnail to avoid OOM)
        thumb_path = None
        try:
            with open(file_path, 'rb') as f:
                sent = await update.message.reply_video(
                    video=f, caption=caption, supports_streaming=True,
                    read_timeout=300, write_timeout=300
                )
            return sent
        finally:
            if thumb_path and os.path.exists(thumb_path):
                try: os.remove(thumb_path)
                except: pass

    except (TimedOut, NetworkError) as e:
        raise Exception(f"Upload failed: Network issue - {str(e)}")
    except Exception as e:
        raise Exception(f"Upload error: {str(e)}")

def cleanup_file(file_path):
    """Delete downloaded file or part to save disk."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"🗑️ Cleaned up: {file_path}")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        
