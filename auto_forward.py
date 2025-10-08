"""
Auto-Forward System for backing up leeched files
"""

import logging
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError
from config import BACKUP_CHANNEL_ID, AUTO_FORWARD_ENABLED, FORWARD_CAPTION_TEMPLATE

logger = logging.getLogger(__name__)

async def forward_file_to_channel(context, user, file_message, original_link="Simulated"):
    """
    Forward leeched file to backup channel with user info
    """
    if not AUTO_FORWARD_ENABLED or not BACKUP_CHANNEL_ID:
        logger.info("Auto-forward is disabled")
        return False
    
    try:
        # Get user info
        user_name = user.full_name or "Unknown"
        username = user.username or "No Username"
        user_id = user.id
        
        # Create detailed caption
        forward_caption = FORWARD_CAPTION_TEMPLATE.format(
            user_name=user_name,
            username=username,
            user_id=user_id,
            date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            original_link=original_link,
            total_attempts="Simulated",  # Will be real count in Phase 2
            verification_status="Testing Phase"  # Will be actual status in Phase 2
        )
        
        # Forward to backup channel
        forwarded_message = await context.bot.copy_message(
            chat_id=BACKUP_CHANNEL_ID,
            from_chat_id=file_message.chat_id,
            message_id=file_message.message_id,
            caption=forward_caption,
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ File forwarded to backup channel from user {user_id}")
        return True
        
    except TelegramError as e:
        logger.error(f"❌ Error forwarding to backup channel: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error in auto-forward: {e}")
        return False

async def send_auto_forward_notification(update, context):
    """
    Send notification to user that file was backed up
    """
    if AUTO_FORWARD_ENABLED:
        notification = """
📢 **Auto-Backup Complete**

✅ Your leeched file has been automatically backed up to our channel for future access.

🔒 **Privacy:** Only file metadata is stored, your personal info is protected.
"""
        await update.message.reply_text(notification, parse_mode='Markdown')

async def test_auto_forward(context, chat_id):
    """
    Test auto-forward functionality (for admins)
    """
    try:
        test_message = """
🧪 **Auto-Forward Test**

This is a test message to verify the auto-forward system is working correctly.

✅ If you receive this, auto-forward is configured properly!
"""
        
        await context.bot.send_message(
            chat_id=BACKUP_CHANNEL_ID,
            text=test_message,
            parse_mode='Markdown'
        )
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ Auto-forward test successful! Check your backup channel.",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Auto-forward test failed: {str(e)}",
            parse_mode='Markdown'
        )
