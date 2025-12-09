# adult_source_handlers.py
"""
Source channel → LuluStream → Adult channel automation.

When a video or a direct link is posted in SOURCE_ADULT_CHANNEL_ID,
bot uploads to LuluStream and posts thumbnail + Lulu link to ADULT_CHANNEL_ID.
"""

import re
import logging
from telegram import Update
from telegram.ext import ContextTypes

from adult_config import SOURCE_ADULT_CHANNEL_ID  # source channel ID from env
from adult_automation import (
    upload_to_lulustream,
    post_to_channel,
    save_posted_video,
    already_posted,
)

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"(https?://\S+)")


def _is_from_source_channel(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.id == SOURCE_ADULT_CHANNEL_ID)


async def handle_source_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Triggered when a VIDEO is posted in the source channel.
    """
    if not _is_from_source_channel(update):
        return

    msg = update.channel_post or update.message
    if not msg or not msg.video:
        return

    # Title from caption or default
    title = (msg.caption or "Untitled video").strip()

    # Get Telegram file direct URL
    file = await msg.video.get_file()
    download_url = file.file_path  # HTTPS URL usable by LuluStream

    if already_posted(download_url):
        logger.info("⏭ Skipping already posted source video")
        return

    logger.info(f"📥 Source channel video received: {title[:60]}")

    lululink = await upload_to_lulustream(download_url, title)
    if not lululink:
        logger.warning("⚠️ LuluStream upload failed for source video")
        return

    video_data = {
        "source": "SourceChannel",
        "title": title,
        "url": download_url,
        "download_url": download_url,
        "thumbnail": download_url,   # Telegram video URL as thumb
        "duration": msg.video.duration or 0,
        "views": 0,
        "tags": [],
    }

    ok = await post_to_channel(context.bot, video_data, lululink)
    if ok:
        video_data["lulustream_link"] = lululink
        save_posted_video(video_data)
        logger.info("✅ Source video forwarded to adult channel")


async def handle_source_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Triggered when a TEXT message with a URL is posted in the source channel.
    """
    if not _is_from_source_channel(update):
        return

    msg = update.channel_post or update.message
    if not msg or not msg.text:
        return

    m = URL_RE.search(msg.text)
    if not m:
        return

    download_url = m.group(1)
    title_line = msg.text.split("\n", 1)[0]
    title = title_line[:150] if title_line else "Untitled video"

    if already_posted(download_url):
        logger.info("⏭ Skipping already posted source link")
        return

    logger.info(f"📥 Source channel link received: {title[:60]} -> {download_url}")

    lululink = await upload_to_lulustream(download_url, title)
    if not lululink:
        logger.warning("⚠️ LuluStream upload failed for source link")
        return

    video_data = {
        "source": "SourceChannel",
        "title": title,
        "url": download_url,
        "download_url": download_url,
        "thumbnail": download_url,
        "duration": "0:00",
        "views": 0,
        "tags": [],
        "lulustream_link": lululink,
    }

    ok = await post_to_channel(context.bot, video_data, lululink)
    if ok:
        save_posted_video(video_data)
        logger.info("✅ Source link forwarded to adult channel")
    
