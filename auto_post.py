import logging
import asyncio
import os
import tempfile

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import AUTO_POST_ENABLED, POST_CHANNEL_ID, BOT_USERNAME
from deep_link_gate import build_deep_link_for_message

logger = logging.getLogger(__name__)

def _mk_caption(meta: dict, deep_link: str) -> str:
    title = meta.get("file_name") or (meta.get("caption") or "").strip() or "Video"
    size = meta.get("file_size")
    dur = meta.get("duration")
    size_txt = f"{(size or 0) / (1024*1024):.1f} MB" if size else "—"
    dur_txt = f"{int((dur or 0)//60)} min" if dur else "—"
    return "\n".join([
        f"🎬 {title}",
        f"⏱ {dur_txt}   •   📦 {size_txt}",
        "",
        f"👉 Get it on bot: {deep_link}",
    ])

def _pick_inline_thumb(forwarded_msg) -> str | None:
    if getattr(forwarded_msg, "video", None) and getattr(forwarded_msg.video, "thumbnail", None):
        return forwarded_msg.video.thumbnail.file_id
    if getattr(forwarded_msg, "document", None) and getattr(forwarded_msg.document, "thumbnail", None):
        return forwarded_msg.document.thumbnail.file_id
    if getattr(forwarded_msg, "photo", None) and len(forwarded_msg.photo) > 0:
        return forwarded_msg.photo[-1].file_id
    return None

async def _run_ffmpeg_frame(input_path: str) -> str | None:
    out = os.path.join(tempfile.gettempdir(), f"thumb_{os.getpid()}.jpg")
    try:
        cmd = ["ffmpeg", "-y", "-ss", "1", "-i", input_path, "-frames:v", "1", "-q:v", "5", out]
        proc = await asyncio.create_subprocess_exec(*cmd,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.communicate()
        return out if os.path.exists(out) else None
    except Exception:
        return None

async def _download_small(context, file_id: str, max_bytes: int = 12_000_000) -> str | None:
    try:
        tg_file = await context.bot.get_file(file_id)
        import aiohttp, aiofiles
        tmp_path = os.path.join(tempfile.gettempdir(), f"dl_{os.getpid()}.mp4")
        async with aiohttp.ClientSession() as session:
            async with session.get(tg_file.file_path, timeout=45) as resp:
                if resp.status != 200:
                    return None
                read = 0
                async with aiofiles.open(tmp_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(256*1024):
                        if not chunk:
                            break
                        await f.write(chunk)
                        read += len(chunk)
                        if read >= max_bytes:
                            break
        return tmp_path
    except Exception as e:
        logger.warning(f"Download small error: {e}")
        return None

async def post_preview_to_channel(context, forwarded_msg, meta: dict):
    if not AUTO_POST_ENABLED or not POST_CHANNEL_ID:
        logger.info("Auto-post disabled or POST_CHANNEL_ID missing")
        return False

    try:
        deep = build_deep_link_for_message(forwarded_msg.message_id)
        caption = _mk_caption(meta, deep)
        rm = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Get on bot", url=deep)]])

        # Step 1: Inline thumbnail from Telegram
        thumb_file_id = _pick_inline_thumb(forwarded_msg)
        logger.info(
            f"Poster inline thumb: {bool(thumb_file_id)} | "
            f"has_video={bool(getattr(forwarded_msg,'video',None))} | "
            f"has_doc={bool(getattr(forwarded_msg,'document',None))} | "
            f"has_photo={bool(getattr(forwarded_msg,'photo',None))}"
        )

        if thumb_file_id:
            await context.bot.send_photo(POST_CHANNEL_ID, photo=thumb_file_id, caption=caption, reply_markup=rm)
            logger.info("✅ Auto-post with inline thumbnail")
            return True

        # Step 2: ffmpeg fallback on small chunk
        file_id = None
        if getattr(forwarded_msg, "video", None):
            file_id = forwarded_msg.video.file_id
        elif getattr(forwarded_msg, "document", None):
            try:
                size_ok = (getattr(forwarded_msg.document, "file_size", 0) or 0) <= 15_000_000
            except Exception:
                size_ok = False
            if size_ok:
                file_id = forwarded_msg.document.file_id

        # Use original upload's id if provided in meta
        if not file_id:
            file_id = meta.get("fallback_file_id")

        logger.info(f"FFMPEG path -> file_id present: {bool(file_id)}")

        if file_id:
            tmp_path = await _download_small(context, file_id, max_bytes=12_000_000)
            if tmp_path:
                jpg = await _run_ffmpeg_frame(tmp_path)
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                if jpg and os.path.exists(jpg):
                    try:
                        with open(jpg, "rb") as fh:
                            await context.bot.send_photo(POST_CHANNEL_ID, photo=fh, caption=caption, reply_markup=rm)
                        logger.info("✅ Auto-post with ffmpeg thumbnail")
                        return True
                    finally:
                        try:
                            os.remove(jpg)
                        except Exception:
                            pass

        # Step 3: Text-only fallback
        await context.bot.send_message(POST_CHANNEL_ID, text=caption, reply_markup=rm)
        logger.info("ℹ️ Auto-post text-only (no thumbnail available)")
        return True

    except Exception as e:
        logger.error(f"❌ Auto-post error: {e}")
        return False
    
