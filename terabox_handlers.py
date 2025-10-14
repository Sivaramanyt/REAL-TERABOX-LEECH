"""
Terabox Handlers - WITH CONCURRENT PROCESSING
Multiple users can download/upload simultaneously
"""

import logging
import re
import asyncio
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


async def process_terabox_download(update: Update, context: ContextTypes.DEFAULT_TYPE, terabox_url: str, user_id: int, status_msg):
    """
    Background task for downloading and uploading
    This runs independently for each user
    """
    user = update.effective_user
    file_path = None
    
    try:
        # Step 1: Extract file information
        logger.info(f"📋 [User {user_id}] Extracting file info")
        
        await status_msg.edit_text(
            "📋 **Fetching file information...**",
            parse_mode='Markdown'
        )
        
        # ✅ FIXED: New API returns {"files": [...]}
        result = extract_terabox_data(terabox_url)
        files = result.get("files", [])
        
        if not files:
            await status_msg.edit_text(
                "❌ **No files found!**",
                parse_mode='Markdown'
            )
            return
        
        # Process first file
        file_info = files[0]
        
        # ✅ FIXED: Use correct keys from new API
        filename = file_info.get('name', 'Terabox File')
        size_readable = file_info.get('size', 'Unknown')
        download_url = file_info.get('download_url')
        
        # Convert size to bytes for validation
        file_size = 0
        try:
            # Try to parse size string like "18.08 MB"
            size_parts = size_readable.split()
            if len(size_parts) == 2:
                size_value = float(size_parts[0])
                size_unit = size_parts[1].upper()
                
                if size_unit == 'KB':
                    file_size = int(size_value * 1024)
                elif size_unit == 'MB':
                    file_size = int(size_value * 1024 * 1024)
                elif size_unit == 'GB':
                    file_size = int(size_value * 1024 * 1024 * 1024)
                elif size_unit == 'B':
                    file_size = int(size_value)
        except:
            pass
        
        # Increment attempts
        increment_leech_attempts(user_id)
        user_data = get_user_data(user_id)
        used_attempts = user_data.get("leech_attempts", 0)
        is_verified = user_data.get("is_verified", False)
        
        logger.info(f"✅ [User {user_id}] File: {filename} - {size_readable}")
        
        # Validate
        if not download_url:
            await status_msg.edit_text(
                "❌ **Failed to get download link.**",
                parse_mode='Markdown'
            )
            return
        
        # Check size (2GB limit)
        max_size = 2 * 1024 * 1024 * 1024
        if file_size > max_size:
            await status_msg.edit_text(
                f"❌ **File too large!**\n\n"
                f"📊 **Size:** {size_readable}\n"
                f"📊 **Max:** 2GB",
                parse_mode='Markdown'
            )
            return
        
        # Show info
        await status_msg.edit_text(
            f"📁 **File Found!**\n\n"
            f"📝 `{filename}`\n"
            f"📊 {size_readable}\n"
            f"🔢 Attempt #{used_attempts}\n\n"
            f"⬇️ **Downloading...**",
            parse_mode='Markdown'
        )
        
        # Step 2: Download
        logger.info(f"⬇️ [User {user_id}] Starting download")
        file_path = await download_file(download_url, filename, status_msg)
        logger.info(f"✅ [User {user_id}] Download complete")
        
        # Step 3: Upload
        await status_msg.edit_text(
            "📤 **Uploading to Telegram...**",
            parse_mode='Markdown'
        )
        
        caption = f"📄 **{filename}**\n📊 {size_readable}\n🤖 @{context.bot.username}"
        sent_message = await upload_to_telegram(update, context, file_path, caption)
        logger.info(f"✅ [User {user_id}] Upload complete")
        
        # Step 4: Auto-forward
        if AUTO_FORWARD_ENABLED and sent_message:
            try:
                await forward_file_to_channel(context, user, sent_message)
                logger.info(f"✅ [User {user_id}] File forwarded")
            except Exception as e:
                logger.error(f"⚠️ [User {user_id}] Forward failed: {e}")
        
        # Step 5: Cleanup
        cleanup_file(file_path)
        file_path = None
        
        try:
            await status_msg.delete()
        except:
            pass
        
        # Step 6: Send completion message
        if not is_verified and used_attempts < FREE_LEECH_LIMIT:
            remaining = FREE_LEECH_LIMIT - used_attempts
            await update.message.reply_text(
                f"✅ **File uploaded!**\n\n"
                f"⏳ **Remaining:** {remaining}/{FREE_LEECH_LIMIT}",
                parse_mode='Markdown'
            )
        elif used_attempts >= FREE_LEECH_LIMIT and not is_verified:
            await update.message.reply_text("✅ **File uploaded!**", parse_mode='Markdown')
            await send_verification_message(update, context)
        else:
            await update.message.reply_text(
                "✅ **File uploaded!**\n♾️ **Status:** Premium",
                parse_mode='Markdown'
            )
    
    except Exception as e:
        logger.error(f"❌ [User {user_id}] Error: {e}")
        if file_path:
            cleanup_file(file_path)
        
        try:
            await status_msg.edit_text(
                f"❌ **Error:**\n`{str(e)}`",
                parse_mode='Markdown'
            )
        except:
            pass


async def handle_terabox_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main handler - Creates background task for each user
    """
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Check pattern
    if not TERABOX_PATTERN.search(message_text):
        return False
    
    match = TERABOX_PATTERN.search(message_text)
    terabox_url = match.group(0)
    
    logger.info(f"📦 [User {user_id}] Terabox link detected")
    
    # Check permissions
    if not can_user_leech(user_id):
        if needs_verification(user_id):
            await send_verification_message(update, context)
            return True
        else:
            await update.message.reply_text(
                "❌ **Error checking account.**\nUse /start",
                parse_mode='Markdown'
            )
            return True
    
    # Send initial message
    status_msg = await update.message.reply_text(
        "🔍 **Processing...**",
        parse_mode='Markdown'
    )
    
    # CREATE BACKGROUND TASK - This allows concurrent processing
    asyncio.create_task(
        process_terabox_download(update, context, terabox_url, user_id, status_msg)
    )
    
    # Return immediately - don't wait for download to finish
    return True
            
