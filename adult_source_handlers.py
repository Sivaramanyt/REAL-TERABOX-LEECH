# adult_source_handlers.py

import re
import logging
from telegram import Update
from telegram.ext import ContextTypes
from adult_config import ADULT_CHANNEL_ID, SOURCE_ADULT_CHANNEL_ID
from adult_automation import upload_to_lulustream, post_to_channel, save_posted_video

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"(https?://\S+)")

def is_from_source_channel(update: Update) -> bool:
    chat = update.effective_chat
    return chat and chat.id == SOURCE_ADULT_CHANNEL_ID

async def handle_source_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_from_source_channel(update):
        return

    msg = update.channel_post or update.message
    if not msg or not msg.video:
        return

    title = msg.caption or "Untitled video"

    # Get Telegram file direct URL
    file = await msg.video.get_file()
    download_url = file.file_path   # public HTTPS url

    video_data = {
        "source": "SourceChannel",
        "title": title,
        "url": download_url,
        "download_url": download_url,
        "thumbnail": None,          # will use LuluStream thumb or skip
        "duration": msg.video.duration or 0,
        "views": 0,
        "tags": [],
    }

    lululink = await upload_to_lulustream(download_url, title)
    if not lululink:
        await msg.reply_text("Lulu upload failed")
        return

    # If no thumb, you can pass video file itself; for now keep None or set to download_url
    video_data["thumbnail"] = download_url
    ok = await post_to_channel(context.bot, video_data, lululink)
    if ok:
        video_data["lulustream_link"] = lululink
        save_posted_video(video_data)

async def handle_source_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_from_source_channel(update):
        return

    msg = update.channel_post or update.message
    if not msg or not msg.text:
        return

    m = URL_RE.search(msg.text)
    if not m:
        return

    download_url = m.group(1)
    title = msg.text.split("\n", 1)[0][:150]

    video_data = {
        "source": "SourceChannel",
        "title": title,
        "url": download_url,
        "download_url": download_url,
        "thumbnail": None,
        "duration": "0:00",
        "views": 0,
        "tags": [],
    }

    lululink = await upload_to_lulustream(download_url, title)
    if not lululink:
        await msg.reply_text("Lulu upload failed")
        return

    video_data["thumbnail"] = download_url
    ok = await post_to_channel(context.bot, video_data, lululink)
    if ok:
        video_data["lulustream_link"] = lululink
        save_posted_video(video_data)
