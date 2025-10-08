"""
Auto-Forward System - Forward files ONLY to channel without user info
"""

import logging
from telegram.error import TelegramError
from config import AUTO_FORWARD_ENABLED, BACKUP_CHANNEL_ID

logger = logging.getLogger(__name__)

async def forward_file_to_channel(context, user, file_message):
    """
    Forward the leeched file or message to backup channel as-is
    WITHOUT attaching any user metadata or captions
    """
    if not AUTO_FORWARD_ENABLED or not BACKUP_CHANNEL_ID:
        logger.info("Auto-forward is disabled or backup channel ID not set")
        return False
    
    try:
        # Simply copy message from user's chat to the backup channel
        await context.bot.copy_message(
            chat_id=BACKUP_CHANNEL_ID,
            from_chat_id=file_message.chat_id,
            message_id=file_message.message_id
        )
        logger.info(f"✅ File forwarded to backup channel")
        return True
    
    except TelegramError as e:
        logger.error(f"❌ Telegram API error in forwarding file: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error in auto-forward: {e}")
        return False

async def send_auto_forward_notification(update, context):
    """
    Send a simple confirmation message to the user after forwarding the file
    """
    if AUTO_FORWARD_ENABLED:
        await update.message.reply_text(
            "✅ Your leeched file has been backed up to the channel successfully!"
        )
        
