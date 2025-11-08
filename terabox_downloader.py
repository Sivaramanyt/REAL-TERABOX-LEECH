"""
Terabox Downloader - video-first uploads + size-aware segmentation + turbo 2-lane downloader,
robust headers, cancel support, and throughput tuning.
"""

import os
import glob
import math
import logging
import time
import subprocess
import requests
import threading
from typing import Optional, List

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest, TimedOut, NetworkError

from terabox_api import format_size

logger = logging.getLogger(__name__)

# ===== Tunables (env overrides) =====
DOWNLOAD_DIR = "downloads"
CHUNK_SIZE = int(os.getenv("DOWNLOAD_CHUNK_KB", "768")) * 1024          # default 768 KB
PROGRESS_INTERVAL_SEC = int(os.getenv("PROGRESS_INTERVAL_SEC", "8"))    # progress every 8s
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024                                  # 2GB
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v', '.3gp']

# Video-only policy
FORCE_VIDEO_UPLOAD = True
DISABLE_THUMBNAIL = True

# Size-aware segmentation targets for Bot API
BOT_API_MAX_MB = int(os.getenv("BOT_API_MAX_MB", "49"))
SEGMENT_SAFETY_MB = int(os.getenv("SEGMENT_SAFETY_MB", "2"))
MIN_SEG_TIME_SEC = int(os.getenv("MIN_SEG_TIME_SEC", "60"))
MAX_SEG_TIME_SEC = int(os.getenv("MAX_SEG_TIME_SEC", "900"))
VIDEO_SEGMENT_THRESHOLD_MB = int(os.getenv("VIDEO_SEGMENT_THRESHOLD_MB", "50"))

# Turbo parallel ranges
TURBO_SEGMENTS = int(os.getenv("TURBO_SEGMENTS", "2"))           # 1=off, 2=two lanes
TURBO_MIN_SIZE_MB = int(os.getenv("TURBO_MIN_SIZE_MB", "60"))    # enable turbo on ≥60 MB

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

def create_progress_bar(percentage: float) -> str:
    filled = int(percentage / 10)
    empty = 10 - filled
    return '█' * filled + '░' * empty

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
            f"⏱️ ETA: {int(eta)}s\n\n"
            "🛑 Send /cancel to stop"
        )
        await message.edit_text(text, parse_mode='Markdown')
    except (BadRequest, TimedOut):
        pass
    except Exception as e:
        logger.debug(f"Progress update error: {e}")

def _open_part(base_path: str, idx: int):
    part_path = f"{base_path}.part{idx:02d}"
    return part_path, open(part_path, "wb")

def ffprobe_duration_seconds(path: str) -> Optional[float]:
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20
        )
        if res.returncode != 0:
            return None
        return float(res.stdout.decode().strip())
    except Exception:
        return None

def calc_segment_time_for_size(file_path: str, target_mb: int, safety_mb: int) -> int:
    file_size = os.path.getsize(file_path)
    duration = ffprobe_duration_seconds(file_path) or 0
    if duration <= 0:
        return max(MIN_SEG_TIME_SEC, min(MAX_SEG_TIME_SEC, 240))
    bytes_per_sec = file_size / duration
    target_bytes = (target_mb - safety_mb) * 1024 * 1024
    seg_time = int(max(1, target_bytes / max(1, bytes_per_sec)))
    return max(MIN_SEG_TIME_SEC, min(MAX_SEG_TIME_SEC, seg_time))

def segment_video_by_time(input_path: str, segment_time_sec: int) -> List[str]:
    root = os.path.splitext(os.path.basename(input_path))[0]
    out_pattern = os.path.join(DOWNLOAD_DIR, f"{root}_seg%03d.mp4")
    glob_pattern = os.path.join(DOWNLOAD_DIR, f"{root}_seg*.mp4")
    for old in glob.glob(glob_pattern):
        try: os.remove(old)
        except: pass
    cmd = [
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-i', input_path, '-c', 'copy', '-map', '0',
        '-f', 'segment', '-segment_time', str(segment_time_sec),
        '-reset_timestamps', '1', out_pattern
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

def _range_fetch(url, headers, start, end, out_path, cancel_event):
    rng = f"bytes={start}-{end}" if end is not None else f"bytes={start}-"
    h = dict(headers); h["Range"] = rng
    with requests.get(url, headers=h, stream=True, timeout=(30, 300), allow_redirects=True) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if cancel_event and cancel_event.is_set():
                    raise Exception("Cancelled by user")
                if chunk:
                    f.write(chunk)

async def _download_turbo(url, headers, total_size, base_path, cancel_event):
    # Two halves
    mid = (total_size - 1) // 2
    p1 = base_path + ".seg0"
    p2 = base_path + ".seg1"
    t1 = threading.Thread(target=_range_fetch, args=(url, headers, 0, mid, p1, cancel_event), daemon=True)
    t2 = threading.Thread(target=_range_fetch, args=(url, headers, mid+1, total_size-1, p2, cancel_event), daemon=True)
    t1.start(); t2.start(); t1.join(); t2.join()
    # Concatenate
    with open(base_path, "wb") as out:
        for p in (p1, p2):
            with open(p, "rb") as src:
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    out.write(chunk)
    try: os.remove(p1); os.remove(p2)
    except: pass
    return base_path

async def download_file(
    url: str,
    filename: str,
    status_message=None,
    referer: Optional[str] = None,
    cancel_event=None,
    split_enabled: bool = False,  # keep off for video so we can segment by time after full download
    split_part_mb: int = 200
) -> str | list[str]:
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
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
            "Referer": r,
            "Range": "bytes=0-",
        }
        try:
            resp = try_request(headers)
            if resp.status_code == 403:
                last_err = f"403 with Referer={r}"; logger.warning(last_err); continue
            resp.raise_for_status()

            headers_no_range = dict(headers); headers_no_range.pop("Range", None)
            try:
                resp2 = try_request(headers_no_range)
                if resp2.status_code in (200, 206):
                    resp.close(); resp = resp2
            except Exception:
                pass

            total_size = int(resp.headers.get("content-length", "0"))
            if total_size and total_size > MAX_FILE_SIZE:
                resp.close(); raise Exception(f"File too large: {format_size(total_size)} (Max: 2GB)")

            # Turbo path for large files
            if total_size and total_size >= TURBO_MIN_SIZE_MB * 1024 * 1024 and TURBO_SEGMENTS >= 2:
                resp.close()
                return await _download_turbo(url, headers_no_range, total_size, base_path, cancel_event)

            # Single-lane streaming path
            parts: List[str] = []
            part_idx = 1
            written_in_part = 0
            downloaded = 0
            start_time = time.time()
            last_update = 0

            if split_enabled:
                part_path, f = _open_part(base_path, part_idx); parts.append(part_path)
            else:
                f = open(base_path, "wb")

            with f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if cancel_event and cancel_event.is_set():
                        resp.close(); raise Exception("Cancelled by user")
                    if not chunk:
                        continue

                    if split_enabled and written_in_part + len(chunk) > part_limit:
                        remain = part_limit - written_in_part
                        if remain > 0:
                            f.write(chunk[:remain]); downloaded += remain; written_in_part += remain
                            chunk = chunk[remain:]
                        f.close()
                        part_idx += 1; written_in_part = 0
                        part_path, f = _open_part(base_path, part_idx); parts.append(part_path)

                    f.write(chunk); downloaded += len(chunk)
                    if split_enabled: written_in_part += len(chunk)

                    current_time = time.time()
                    if status_message and (current_time - last_update >= PROGRESS_INTERVAL_SEC):
                        try: await update_progress(status_message, downloaded, total_size, start_time)
                        except: pass
                        last_update = current_time

            resp.close()
            if split_enabled: return parts
            return base_path

        except requests.Timeout as e:
            last_err = f"timeout with Referer={r}: {e}"; logger.warning(last_err)
        except requests.ConnectionError as e:
            last_err = f"connection error with Referer={r}: {e}"; logger.warning(last_err)
        except Exception as e:
            last_err = str(e); logger.warning(f"attempt with Referer={r} failed: {e}")

        # Cleanup partials
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
    Video-only:
    - If file ≥ ~50 MB, segment by time to keep each part ≤ ~49 MB and send each via sendVideo.
    - Else sendVideo directly (no thumbnail).
    """
    try:
        if not os.path.exists(file_path):
            raise Exception("File not found after download")

        file_size = os.path.getsize(file_path)
        logger.info(f"⬆️ Uploading to Telegram: {format_size(file_size)}")

        is_video = any(file_path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)
        if not is_video:
            with open(file_path, 'rb') as f:
                return await update.message.reply_document(
                    document=f, caption=caption, read_timeout=300, write_timeout=300
                )

        threshold_bytes = VIDEO_SEGMENT_THRESHOLD_MB * 1024 * 1024
        if file_size >= threshold_bytes:
            seg_time = calc_segment_time_for_size(file_path, BOT_API_MAX_MB, SEGMENT_SAFETY_MB)
            seg_paths = segment_video_by_time(file_path, seg_time)
            last_sent = None
            total = len(seg_paths); idx = 1
            for p in seg_paths:
                # guard: if any part too big, resegment finer
                if os.path.getsize(p) >= (BOT_API_MAX_MB * 1024 * 1024):
                    finer = max(MIN_SEG_TIME_SEC, seg_time // 2)
                    seg_paths = segment_video_by_time(file_path, finer)
                    total = len(seg_paths); idx = 1
                with open(p, 'rb') as f:
                    part_caption = f"{caption}\n🧩 Part {idx}/{total}"
                    last_sent = await update.message.reply_video(
                        video=f, caption=part_caption, supports_streaming=True,
                        read_timeout=300, write_timeout=300
                    )
                try: os.remove(p)
                except: pass
                idx += 1
            return last_sent

        with open(file_path, 'rb') as f:
            return await update.message.reply_video(
                video=f, caption=caption, supports_streaming=True,
                read_timeout=300, write_timeout=300
            )

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
        
