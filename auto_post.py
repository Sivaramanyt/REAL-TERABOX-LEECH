# auto_post.py
import logging
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

    lines = [
        f"🎬 {title}",
        f"⏱ {dur_txt}   •   📦 {size_txt}",
        "",
        f"👉 Get it on bot: {deep_link}",
    ]
    return "\n".join(lines)

async def post_preview_to_channel(context, forwarded_msg, meta: dict):
    """
    Post a preview to the main channel after a successful forward to backup:
    - Prefer Telegram-provided thumbnail from the copied message
    - Fallback to text-only if no thumbnail is available
    """
    if not AUTO_POST_ENABLED or not POST_CHANNEL_ID:
        logger.info("Auto-post disabled or POST_CHANNEL_ID missing")
        return False

    try:
        deep = build_deep_link_for_message(forwarded_msg.message_id)
        caption = _mk_caption(meta, deep)
        kb = [[InlineKeyboardButton("🔗 Get on bot", url=deep)]]
        rm = InlineKeyboardMarkup(kb)

        # Thumbnail fallback chain
        thumb_file_id = None

        # 1) Video thumbnail (most reliable when original was sent via sendVideo)
        if getattr(forwarded_msg, "video", None) and getattr(forwarded_msg.video, "thumbnail", None):
            thumb_file_id = forwarded_msg.video.thumbnail.file_id

        # 2) Document thumbnail (when some videos are sent as documents with thumbs)
        elif getattr(forwarded_msg, "document", None) and getattr(forwarded_msg.document, "thumbnail", None):
            thumb_file_id = forwarded_msg.document.thumbnail.file_id

        # 3) Photo messages (if original was a photo)
        elif getattr(forwarded_msg, "photo", None) and len(forwarded_msg.photo) > 0:
            thumb_file_id = forwarded_msg.photo[-1].file_id

        # Debug log to see which branch was used
        try:
            logger.info(
                f"Poster thumb chosen: {bool(thumb_file_id)} | "
                f"has_video={bool(getattr(forwarded_msg,'video',None))} | "
                f"has_doc={bool(getattr(forwarded_msg,'document',None))} | "
                f"has_photo={bool(getattr(forwarded_msg,'photo',None))}"
            )
        except Exception:
            pass

        if thumb_file_id:
            await context.bot.send_photo(
                chat_id=POST_CHANNEL_ID,
                photo=thumb_file_id,
                caption=caption,
                reply_markup=rm
            )
        else:
            # Fallback: text-only post
            await context.bot.send_message(
                chat_id=POST_CHANNEL_ID,
                text=caption,
                reply_markup=rm
            )

        logger.info("✅ Auto-post preview sent")
        return True

    except Exception as e:
        logger.error(f"❌ Auto-post error: {e}")
        return False
        
