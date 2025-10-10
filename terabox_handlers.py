"""
Terabox Handlers - With mandatory auto-forward for ALL users
"""

import logging
import os
import re
from telegram import Update
from telegram.ext import ContextTypes

from database import can_user_leech, increment_leech_attempts, get_user_data, needs_verification
from handlers import send_verification_message
from auto_forward import forward_file_to_channel
from config import FREE_LEECH_LIMIT, AUTO_FORWARD_ENABLED

from terabox_api import is_terabox_url, extract_terabox_data, format_size, TeraboxException
from terabox_downloader import download_file, upload_to_telegram, cleanup_file, get_safe_filename, DOWNLOAD_DIR

logger = logging.getLogger(__name__)

TERABOX_PATTERN = re.compile(
    r'https?://(?:www\.)?(terabox|teraboxapp|1024tera|4funbox|teraboxshare|teraboxurl|1024terabox|terafileshare|teraboxlink|terasharelink)\.(com|app|fun)/(?:s/|wap/share/filelist\?surl=)[\w-]+',
    re.IGNORECASE
)

async def handle_terabox_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main handler with guaranteed auto-forward"""
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
    
    status_msg = await update.message.reply_text("🔄 **Processing...**", parse_mode='Markdown')
    
    try:
        # Extract file info
        await status_msg.edit_text("🔍 **Fetching file info...**", parse_mode='Markdown')
        file_data = extract_terabox_data(terabox_url)
        
        # Increment attempts
        increment_leech_attempts(user_id)
        user_data = get_user_data(user_id)
        used_attempts = user_data.get("leech_attempts", 0)
        is_verified = user_data.get("is_verified", False)
        
        if file_data["type"] == "file":
            file_info = file_data["files"][0]
            
            # Show file info
            info_text = (
                f"📁 **File Information**\n\n"
                f"📝 {file_info['name']}\n"
                f"📦 {file_info['size_str']}\n"
                f"📊 Attempt #{used_attempts}"
            )
            await status_msg.edit_text(info_text, parse_mode='Markdown')
            
            # Prepare download
            safe_filename = get_safe_filename(file_info['name'])
            file_path = os.path.join(DOWNLOAD_DIR, safe_filename)
            
            # Download with live progress
            await download_file(
                url=file_info['url'],
                file_path=file_path,
                total_size=file_info['size'],
                status_message=status_msg
            )
            
            # Upload
            await status_msg.edit_text("⬆️ **Uploading to Telegram...**", parse_mode='Markdown')
            
            caption = f"📄 {file_info['name']}\n📦 {file_info['size_str']}\n🤖 Terabox Leech Bot"
            sent_message = await upload_to_telegram(update, context, file_path, caption, file_info)
            
            # ALWAYS FORWARD (regardless of who uploaded)
            if AUTO_FORWARD_ENABLED and sent_message:
                try:
                    await forward_file_to_channel(context, user, sent_message)
                    logger.info(f"✅ File forwarded to channel from user {user_id}")
                except Exception as e:
                    logger.error(f"❌ Forward failed: {e}")
            
            # Cleanup
            cleanup_file(file_path)
            await status_msg.delete()
            
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
        
    except TeraboxException as e:
        await status_msg.edit_text(f"❌ **Terabox Error**\n\n{str(e)}", parse_mode='Markdown')
        return True
    except Exception as e:
        logger.error(f"❌ Handler error: {e}")
        await status_msg.edit_text(f"❌ **Error**\n\n{str(e)}", parse_mode='Markdown')
        return True
                                   
