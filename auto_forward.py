"""
Auto-Forward System - Forward files AND save to File Store silently
"""

import logging
from telegram.error import TelegramError
from config import AUTO_FORWARD_ENABLED, BACKUP_CHANNEL_ID
from database import save_file

logger = logging.getLogger(__name__)


async def forward_file_to_channel(context, user, file_message):
    """
    Forward file to channel and silently save to File Store
    NO messages sent to user
    """
    if not AUTO_FORWARD_ENABLED or not BACKUP_CHANNEL_ID:
        logger.info("Auto-forward is disabled or backup channel ID not set")
        return False
    
    try:
        # Step 1: Copy message to channel
        forwarded_msg = await context.bot.copy_message(
            chat_id=BACKUP_CHANNEL_ID,
            from_chat_id=file_message.chat_id,
            message_id=file_message.message_id
        )
        
        logger.info(f"✅ File forwarded to backup channel from user {user.id}")
        
        # Step 2: Silently save to File Store (NO user notification)
        try:
            # Determine file type and ID
            file_type = None
            file_id = None
            
            if file_message.document:
                file_type = "document"
                file_id = file_message.document.file_id
            elif file_message.video:
                file_type = "video"
                file_id = file_message.video.file_id
            elif file_message.audio:
                file_type = "audio"
                file_id = file_message.audio.file_id
            elif file_message.photo:
                file_type = "photo"
                file_id = file_message.photo[-1].file_id
            
            if file_id and file_type:
                # ✅ Silently save to file store with channel message ID
                save_file(
                    channel_post_id=forwarded_msg.message_id,
                    file_type=file_type,
                    file_id=file_id
                )
                
                logger.info(f"✅ File saved to store: msg_id={forwarded_msg.message_id}")
            else:
                logger.warning("⚠️ Could not determine file type for file store")
        
        except Exception as e:
            logger.error(f"❌ Error saving to file store: {e}")
            # Don't fail the whole process if file store fails
        
        return True
    
    except TelegramError as e:
        logger.error(f"❌ Telegram API error in forwarding file: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error in auto-forward: {e}")
        return False
            
