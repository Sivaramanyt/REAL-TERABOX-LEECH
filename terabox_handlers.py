"""
Terabox Command Handlers
Integrates with existing verification system
Forwards the ACTUAL VIDEO FILE to backup channel
"""

import logging
import os
import re
from telegram import Update
from telegram.ext import ContextTypes

# Import your existing functions
from database import can_user_leech, increment_leech_attempts, get_user_data, needs_verification
from handlers import send_verification_message
from auto_forward import forward_file_to_channel, send_auto_forward_notification
from config import FREE_LEECH_LIMIT, AUTO_FORWARD_ENABLED

# Import new Terabox functions
from terabox_api import is_terabox_url, extract_terabox_data, format_size, TeraboxException
from terabox_downloader import download_file, upload_to_telegram, cleanup_file, get_safe_filename, DOWNLOAD_DIR

logger = logging.getLogger(__name__)

# Terabox URL pattern
TERABOX_PATTERN = re.compile(
    r'https?://(?:www\.)?(terabox|teraboxapp|1024tera|4funbox|teraboxshare)\.(com|app|fun)/(?:s/|wap/share/filelist\?surl=)[\w-]+',
    re.IGNORECASE
)

async def handle_terabox_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main handler for Terabox links
    Integrates with your existing verification system
    Forwards the UPLOADED VIDEO FILE, not the user's message
    """
    user_id = update.effective_user.id
    user = update.effective_user
    message_text = update.message.text
    
    # Check if message contains Terabox URL
    if not TERABOX_PATTERN.search(message_text):
        return False  # Not a Terabox link
    
    # Extract Terabox URL
    match = TERABOX_PATTERN.search(message_text)
    terabox_url = match.group(0)
    
    logger.info(f"📦 Terabox link detected from user {user_id}: {terabox_url}")
    
    # CHECK VERIFICATION STATUS (Using your existing function)
    if not can_user_leech(user_id):
        if needs_verification(user_id):
            await send_verification_message(update, context)
            return True
        else:
            await update.message.reply_text("❌ Error checking your account. Please try /start")
            return True
    
    # User can leech - proceed with download
    status_msg = await update.message.reply_text(
        "🔄 **Processing Terabox link...**\n"
        "⏳ Please wait...",
        parse_mode='Markdown'
    )
    
    try:
        # Extract file information from Terabox
        await status_msg.edit_text("🔍 **Fetching file information...**", parse_mode='Markdown')
        file_data = extract_terabox_data(terabox_url)
        
        # Increment leech attempts (Using your existing function)
        increment_leech_attempts(user_id)
        user_data = get_user_data(user_id)
        used_attempts = user_data.get("leech_attempts", 0)
        is_verified = user_data.get("is_verified", False)
        
        # Display file information
        if file_data["type"] == "file":
            # Single file
            file_info = file_data["files"][0]
            
            info_text = (
                f"📁 **File Information**\n\n"
                f"📝 Name: `{file_info['name']}`\n"
                f"📦 Size: {file_info['size_str']}\n"
                f"📊 Attempt: #{used_attempts}\n\n"
                f"⏬ **Downloading...**"
            )
            await status_msg.edit_text(info_text, parse_mode='Markdown')
            
            # Download file
            safe_filename = get_safe_filename(file_info['name'])
            file_path = os.path.join(DOWNLOAD_DIR, safe_filename)
            
            await download_file(file_info['url'], file_path)
            
            # Upload to Telegram and get the sent message
            await status_msg.edit_text("⬆️ **Uploading to Telegram...**", parse_mode='Markdown')
            
            caption = (
                f"📄 {file_info['name']}\n"
                f"📦 {file_info['size_str']}\n"
                f"🤖 Terabox Leech Bot"
            )
            
            # IMPORTANT: Get the sent message object
            sent_message = await upload_to_telegram(update, context, file_path, caption, file_info)
            
            # Auto-forward if enabled - Forward the UPLOADED FILE, not user's message
            if AUTO_FORWARD_ENABLED:
                try:
                    await forward_file_to_channel(context, user, sent_message)
                    await send_auto_forward_notification(update, context)
                except Exception as e:
                    logger.error(f"Auto-forward error: {e}")
            
            # Cleanup
            cleanup_file(file_path)
            await status_msg.delete()
            
            # Show remaining attempts
            if not is_verified and used_attempts < FREE_LEECH_LIMIT:
                remaining = FREE_LEECH_LIMIT - used_attempts
                await update.message.reply_text(
                    f"✅ **File uploaded successfully!**\n\n"
                    f"⏳ Remaining attempts: {remaining}/{FREE_LEECH_LIMIT}",
                    parse_mode='Markdown'
                )
            elif used_attempts >= FREE_LEECH_LIMIT and not is_verified:
                await update.message.reply_text("✅ **File uploaded successfully!**", parse_mode='Markdown')
                await send_verification_message(update, context)
            else:
                await update.message.reply_text("✅ **File uploaded successfully!**", parse_mode='Markdown')
        
        elif file_data["type"] == "folder":
            # Folder with multiple files
            total_files = len(file_data["files"])
            
            await status_msg.edit_text(
                f"📁 **Folder Detected**\n\n"
                f"📝 Name: `{file_data['title']}`\n"
                f"📦 Total Size: {format_size(file_data['total_size'])}\n"
                f"📄 Files: {total_files}\n\n"
                f"⏬ **Processing files...**",
                parse_mode='Markdown'
            )
            
            # Process each file
            for idx, file_info in enumerate(file_data["files"], 1):
                try:
                    await status_msg.edit_text(
                        f"⏬ **Downloading [{idx}/{total_files}]**\n\n"
                        f"📝 {file_info['name']}\n"
                        f"📦 {file_info['size_str']}",
                        parse_mode='Markdown'
                    )
                    
                    # Download
                    safe_filename = get_safe_filename(file_info['name'])
                    file_path = os.path.join(DOWNLOAD_DIR, safe_filename)
                    await download_file(file_info['url'], file_path)
                    
                    # Upload
                    await status_msg.edit_text(
                        f"⬆️ **Uploading [{idx}/{total_files}]**\n\n"
                        f"📝 {file_info['name']}",
                        parse_mode='Markdown'
                    )
                    
                    caption = f"📄 {file_info['name']} [{idx}/{total_files}]\n📦 {file_info['size_str']}"
                    sent_message = await upload_to_telegram(update, context, file_path, caption, file_info)
                    
                    # Auto-forward each file - Forward the UPLOADED FILE
                    if AUTO_FORWARD_ENABLED:
                        try:
                            await forward_file_to_channel(context, user, sent_message)
                        except Exception as e:
                            logger.error(f"Auto-forward error for file {idx}: {e}")
                    
                    # Cleanup
                    cleanup_file(file_path)
                    
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ Failed: {file_info['name']}\nError: {str(e)}"
                    )
            
            await status_msg.edit_text(
                f"✅ **Folder leech completed!**\n"
                f"📁 {total_files} files uploaded",
                parse_mode='Markdown'
            )
            
            # Show remaining attempts
            if not is_verified and used_attempts < FREE_LEECH_LIMIT:
                remaining = FREE_LEECH_LIMIT - used_attempts
                await update.message.reply_text(
                    f"⏳ Remaining attempts: {remaining}/{FREE_LEECH_LIMIT}",
                    parse_mode='Markdown'
                )
            elif used_attempts >= FREE_LEECH_LIMIT and not is_verified:
                await send_verification_message(update, context)
        
        return True
        
    except TeraboxException as e:
        await status_msg.edit_text(
            f"❌ **Terabox Error**\n\n{str(e)}",
            parse_mode='Markdown'
        )
        return True
    except Exception as e:
        logger.error(f"❌ Terabox handler error: {e}")
        await status_msg.edit_text(
            f"❌ **Error occurred**\n\n{str(e)}",
            parse_mode='Markdown'
        )
        return True
            
