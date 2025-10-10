"""
Terabox Handlers - Complete working version
Uses: terabox_api.py + terabox_downloader.py
With: Verification + Auto-forward integration
"""

import logging
import re
from telegram import Update
from telegram.ext import ContextTypes

from database import can_user_leech, increment_leech_attempts, get_user_data, needs_verification
from handlers import send_verification_message
from auto_forward import forward_file_to_channel
from config import FREE_LEECH_LIMIT, AUTO_FORWARD_ENABLED

# Import terabox modules
from terabox_api import extract_terabox_data, format_size
from terabox_downloader import download_file, upload_to_telegram, cleanup_file

logger = logging.getLogger(__name__)

TERABOX_PATTERN = re.compile(
    r'https?://(?:www\.)?(terabox|teraboxapp|1024tera|4funbox|teraboxshare|teraboxurl|1024terabox|terafileshare|teraboxlink|terasharelink)\.(com|app|fun)/(?:s/|wap/share/filelist\?surl=)[\w-]+',
    re.IGNORECASE
)

async def handle_terabox_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main Terabox link handler
    Complete flow: Detect → Extract → Download → Upload → Forward
    """
    user_id = update.effective_user.id
    user = update.effective_user
    message_text = update.message.text
    
    # Check if message contains Terabox link
    if not TERABOX_PATTERN.search(message_text):
        return False
    
    match = TERABOX_PATTERN.search(message_text)
    terabox_url = match.group(0)
    
    logger.info(f"📦 Terabox link detected from user {user_id}")
    
    # Check if user can leech
    if not can_user_leech(user_id):
        if needs_verification(user_id):
            await send_verification_message(update, context)
            return True
        else:
            await update.message.reply_text(
                "❌ **Error checking your account.**\n\n"
                "Please use /start to register.",
                parse_mode='Markdown'
            )
            return True
    
    # Send initial processing message
    status_msg = await update.message.reply_text(
        "🔍 **Processing Terabox link...**",
        parse_mode='Markdown'
    )
    
    file_path = None
    
    try:
        # Step 1: Extract file information from Terabox
        logger.info(f"📋 Extracting file info from: {terabox_url}")
        
        await status_msg.edit_text(
            "📋 **Fetching file information...**",
            parse_mode='Markdown'
        )
        
        file_info = extract_terabox_data(terabox_url)
        
        filename = file_info['filename']
        file_size = file_info['size']
        size_readable = file_info['size_readable']
        download_url = file_info['download_url']
        
        # Increment user's leech attempts
        increment_leech_attempts(user_id)
        user_data = get_user_data(user_id)
        used_attempts = user_data.get("leech_attempts", 0)
        is_verified = user_data.get("is_verified", False)
        
        logger.info(f"✅ File info extracted: {filename} - {size_readable}")
        
        # Validate download URL
        if not download_url:
            await status_msg.edit_text(
                "❌ **Failed to get download link.**\n\n"
                "The file might be private or the link is invalid.",
                parse_mode='Markdown'
            )
            return True
        
        # Check file size limit (2GB)
        max_size = 2 * 1024 * 1024 * 1024  # 2GB in bytes
        if file_size > max_size:
            await status_msg.edit_text(
                f"❌ **File too large!**\n\n"
                f"📊 **File Size:** {size_readable}\n"
                f"📊 **Maximum Allowed:** 2GB\n\n"
                f"Please try a smaller file.",
                parse_mode='Markdown'
            )
            return True
        
        # Show file information
        await status_msg.edit_text(
            f"📁 **File Found!**\n\n"
            f"📝 **Name:** `{filename}`\n"
            f"📊 **Size:** {size_readable}\n"
            f"🔢 **Attempt:** #{used_attempts}\n\n"
            f"⬇️ **Starting download...**",
            parse_mode='Markdown'
        )
        
        # Step 2: Download file
        logger.info(f"⬇️ Starting download: {filename}")
        
        file_path = await download_file(download_url, filename, status_msg)
        
        logger.info(f"✅ Download completed: {file_path}")
        
        # Step 3: Upload to Telegram
        await status_msg.edit_text(
            "📤 **Uploading to Telegram...**\n\n"
            "⏳ Please wait...",
            parse_mode='Markdown'
        )
        
        bot_username = context.bot.username
        caption = (
            f"📄 **{filename}**\n"
            f"📊 **Size:** {size_readable}\n"
            f"🤖 **Bot:** @{bot_username}"
        )
        
        sent_message = await upload_to_telegram(update, context, file_path, caption)
        
        logger.info(f"✅ Upload completed for user {user_id}")
        
        # Step 4: Auto-forward to channel (if enabled)
        if AUTO_FORWARD_ENABLED and sent_message:
            try:
                await forward_file_to_channel(context, user, sent_message)
                logger.info(f"✅ File auto-forwarded from user {user_id}")
            except Exception as forward_error:
                logger.error(f"⚠️ Auto-forward failed: {forward_error}")
        
        # Step 5: Cleanup downloaded file
        cleanup_file(file_path)
        file_path = None
        
        # Step 6: Delete status message
        try:
            await status_msg.delete()
        except:
            pass
        
        # Step 7: Send completion message based on user status
        if not is_verified and used_attempts < FREE_LEECH_LIMIT:
            # User still has free attempts
            remaining = FREE_LEECH_LIMIT - used_attempts
            await update.message.reply_text(
                f"✅ **File uploaded successfully!**\n\n"
                f"⏳ **Free attempts remaining:** {remaining}/{FREE_LEECH_LIMIT}",
                parse_mode='Markdown'
            )
        elif used_attempts >= FREE_LEECH_LIMIT and not is_verified:
            # User exhausted free attempts
            await update.message.reply_text(
                "✅ **File uploaded successfully!**",
                parse_mode='Markdown'
            )
            await send_verification_message(update, context)
        else:
            # Verified user
            await update.message.reply_text(
                "✅ **File uploaded successfully!**\n\n"
                "♾️ **Status:** Premium (Unlimited access)",
                parse_mode='Markdown'
            )
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Handler error for user {user_id}: {str(e)}")
        
        # Cleanup on error
        if file_path:
            cleanup_file(file_path)
        
        # Send error message
        try:
            await status_msg.edit_text(
                f"❌ **Error occurred:**\n\n"
                f"`{str(e)}`\n\n"
                f"Please try again or contact support.",
                parse_mode='Markdown'
            )
        except:
            try:
                await update.message.reply_text(
                    f"❌ **Error:** {str(e)}",
                    parse_mode='Markdown'
                )
            except:
                pass
        
        return True
        
