# auto_post.py
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import AUTO_POST_ENABLED, POST_CHANNEL_ID, BOT_USERNAME
from deep_link_gate import build_deep_link_for_message

logger = logging.getLogger(__name__)

def _mk_caption(meta: dict, deep_link: str) -> str:
    title = meta.get("file_name") or meta.get("caption") or "Video"
    size = meta.get("file_size")
    dur = meta.get("duration")
    size_txt = f"{(size or 0) / (1024*1024):.1f} MB" if size else "—"
    dur_txt = f"{int((dur or 0)//60)} min" if dur else "—"
    lines = [
        f"🎬 {title}",
        f"⏱ {dur_txt}   •   📦 {size_txt}",
        "",
        f"👉 Get it on bot: {deep_link}",
    ]
    return "\n".join(lines)

async def post_preview_to_channel(context, forwarded_msg, meta: dict):
    if not AUTO_POST_ENABLED or not POST_CHANNEL_ID:
        return False
    try:
        deep = build_deep_link_for_message(forwarded_msg.message_id)
        caption = _mk_caption(meta, deep)
        kb = [[InlineKeyboardButton("🔗 Get on bot", url=deep)]]
        rm = InlineKeyboardMarkup(kb)

        thumb_file_id = None
        if getattr(forwarded_msg, "video", None) and forwarded_msg.video.thumbnail:
            thumb_file_id = forwarded_msg.video.thumbnail.file_id
        elif getattr(forwarded_msg, "document", None) and forwarded_msg.document.thumbnail:
            thumb_file_id = forwarded_msg.document.thumbnail.file_id

        if thumb_file_id:
            await context.bot.send_photo(POST_CHANNEL_ID, photo=thumb_file_id, caption=caption, reply_markup=rm)
        else:
            await context.bot.send_message(POST_CHANNEL_ID, text=caption, reply_markup=rm)
        logger.info("✅ Auto-post preview sent")
        return True
    except Exception as e:
        logger.error(f"❌ Auto-post error: {e}")
        return False
