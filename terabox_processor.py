"""
Terabox Processor - Coordinates detection, API fetch, download, and upload
"""

from telegram import Update
from telegram.ext import ContextTypes
import logging
from terabox_detector import is_terabox_link, extract_terabox_links, clean_terabox_link
from terabox_api import get_terabox_info, format_file_size, TeraboxAPIError
from file_downloader import download_file
from telegram_uploader import upload_file

logger = logging.getLogger(__name__)

async def process_terabox_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or update.message.caption
    if not text:
        return
    
    links = extract_terabox_links(text)
    if not links:
        return
    
    # Assume only one terabox link per message
    link = clean_terabox_link(links[0])
    
    await update.message.reply_text(f"🔎 Fetching info for Terabox link:\n{link}")
    
    try:
        info = await get_terabox_info(link)
    except TeraboxAPIError as err:
        await update.message.reply_text(f"❌ Error fetching Terabox info: {err}")
        return
    
    filename = info['filename']
    size_str = format_file_size(info['size'])
    download_url = info['download_url'] or info['direct_link']
    if not download_url:
        await update.message.reply_text("❌ No valid download URL found.")
        return
    
    await update.message.reply_text(f"📥 Starting download: {filename} ({size_str})")
    
    try:
        file_path = await download_file(download_url, filename)
    except Exception as err:
        await update.message.reply_text(f"❌ Download failed: {err}")
        return
    
    await update.message.reply_text(f"📤 Uploading to Telegram: {filename}")
    try:
        await upload_file(update, file_path, filename)
        await update.message.reply_text("✅ Leech complete!")
    except Exception as err:
        await update.message.reply_text(f"❌ Upload failed: {err}")
