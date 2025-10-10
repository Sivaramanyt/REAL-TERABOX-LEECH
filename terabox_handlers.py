"""
Terabox Handlers - Using WORKING processor.py method
"""

import logging
import os
import re
from telegram import Update
from telegram.ext import ContextTypes
from pathlib import Path

from database import can_user_leech, increment_leech_attempts, get_user_data, needs_verification
from handlers import send_verification_message
from auto_forward import forward_file_to_channel
from config import FREE_LEECH_LIMIT, AUTO_FORWARD_ENABLED, DOWNLOAD_DIR, LOGGER

# Import working processor functions
from processor import extract_terabox_info, download_with_micro_chunks_only, format_size

logger = logging.getLogger(__name__)

TERABOX_PATTERN = re.compile(
    r'https?://(?:www\.)?(terabox|teraboxapp|1024tera|4funbox|teraboxshare|teraboxurl|1024terabox|terafileshare|teraboxlink|terasharelink)\.(com|app|fun)/(?:s/|wap/share/filelist\?surl=)[\w-]+',
    re.IGNORECASE
)

async def handle_terabox_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main handler using WORKING processor method"""
    user_id = update.effective_user.id
    user = update.effective_user
    message_text = update.message.text
    
    if not TERABOX_PATTERN.search(message_text):
        return False
    
    match = TERABOX_PATTERN.search(message_text)
    terabox_url = match.group(0)
    
    logger.info(f"📦 Terabox link from user {user_id}")
    
    # Check verification
    if not can_user_leech(user_id):
        if needs_verification(user_id):
            await send_verification_message(update, context)
            return True
        else:
            await update.message.reply_text("❌ Error checking account. Try /start")
            return True
    
    status_msg = await update.message.reply_text("🔍 **Processing Terabox link...**", parse_mode='Markdown')
    
    try:
        # Step 1: Extract file info using WORKING API
        await status_msg.edit_text("📋 **Using wdzone-terabox-api...**", parse_mode='Markdown')
        file_info = extract_terabox_info(terabox_url)
        
        filename = file_info['filename']
        file_size = file_info['size']
        download_url = file_info['download_url']
        
        # Increment attempts
        increment_leech_attempts(user_id)
        user_data = get_user_data(user_id)
        used_attempts = user_data.get("leech_attempts", 0)
        is_verified = user_data.get("is_verified", False)
        
        logger.info(f"✅ File: {filename}, {format_size(file_size)}")
        
        if not download_url:
            await status_msg.edit_text("❌ **No download URL found**", parse_mode='Markdown')
            return True
        
        # Step 2: Size check
        if file_size > 2 * 1024 * 1024 * 1024:
            await status_msg.edit_text(
                f"❌ **File too large!**\n\n📊 **Size:** {format_size(file_size)}\n**Max:** 2GB",
                parse_mode='Markdown'
            )
            return True
        
        await status_msg.edit_text(
            f"📁 **File Found**\n"
            f"📝 {filename}\n"
            f"📊 {format_size(file_size)}\n"
            f"📊 Attempt #{used_attempts}\n\n"
            f"🔬 **Starting download...**",
            parse_mode='Markdown'
        )
        
        # Step 3: Download using WORKING micro-chunk method
        file_path = Path(DOWNLOAD_DIR) / filename
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        
        await download_with_micro_chunks_only(download_url, file_path, filename, status_msg, file_size)
        logger.info(f"✅ Download complete: {filename}")
        
        # Step 4: Upload to Telegram
        await status_msg.edit_text("📤 **Uploading to Telegram...**", parse_mode='Markdown')
        
        caption = f"📄 {filename}\n📊 {format_size(file_size)}\n🤖 Terabox Leech Bot"
        
        try:
            with open(file_path, 'rb') as file:
                if filename.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.webm', '.m4v', '.3gp', '.ts')):
                    sent_message = await update.message.reply_video(
                        video=file,
                        caption=caption,
                        supports_streaming=True,
                        read_timeout=300,
                        write_timeout=300
                    )
                elif filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
                    sent_message = await update.message.reply_photo(
                        photo=file,
                        caption=caption
                    )
                else:
                    sent_message = await update.message.reply_document(
                        document=file,
                        caption=caption,
                        read_timeout=300,
                        write_timeout=300
                    )
        except Exception as upload_error:
            logger.error(f"❌ Upload error: {upload_error}")
            await status_msg.edit_text(f"❌ **Upload failed:** {str(upload_error)}", parse_mode='Markdown')
            return True
        
        logger.info(f"✅ Upload complete: {filename}")
        
        # Step 5: Auto-forward (ALL users)
        if AUTO_FORWARD_ENABLED and sent_message:
            try:
                await forward_file_to_channel(context, user, sent_message)
                logger.info(f"✅ File forwarded from user {user_id}")
            except Exception as e:
                logger.error(f"❌ Forward failed: {e}")
        
        # Step 6: Cleanup
        try:
            file_path.unlink(missing_ok=True)
        except:
            pass
        
        try:
            await status_msg.delete()
        except:
            pass
        
        # Show remaining attempts
        if not is_verified and used_attempts < FREE_LEECH_LIMIT:
            remaining = FREE_LEECH_LIMIT - used_attempts
            await update.message.reply_text(
                f"✅ **File uploaded!**\n⏳ Remaining: {remaining}/{FREE_LEECH_LIMIT}",
                parse_mode='Markdown'
            )
        elif used_attempts >= FREE_LEECH_LIMIT and not is_verified:
            await update.message.reply_text("✅ **File uploaded!**", parse_mode='Markdown')
            await send_verification_message(update, context)
        else:
            await update.message.reply_text("✅ **File uploaded successfully!**", parse_mode='Markdown')
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Handler error: {e}")
        await status_msg.edit_text(f"❌ **Error:** {str(e)}", parse_mode='Markdown')
        return True
        
