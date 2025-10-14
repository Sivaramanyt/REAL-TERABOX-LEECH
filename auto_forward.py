"""
Auto-Forward System - Forward files AND save to File Store
Compatible with your existing database structure
"""

import logging
from datetime import datetime
from telegram.error import TelegramError
from config import AUTO_FORWARD_ENABLED, BACKUP_CHANNEL_ID

logger = logging.getLogger(__name__)


async def forward_file_to_channel(context, user, file_message):
    """
    Forward ANY user's leeched file to backup channel AND save to file store
    """
    if not AUTO_FORWARD_ENABLED or not BACKUP_CHANNEL_ID:
        logger.info("Auto-forward is disabled or backup channel ID not set")
        return False
    
    try:
        # Step 1: Copy message from user's chat to the backup channel
        forwarded_msg = await context.bot.copy_message(
            chat_id=BACKUP_CHANNEL_ID,
            from_chat_id=file_message.chat_id,
            message_id=file_message.message_id
        )
        
        logger.info(f"✅ File forwarded to backup channel from user {user.id}")
        
        # ✅ Step 2: Save to File Store database (silently, no user notification)
        try:
            # Import database connection
            import pymongo
            from config import MONGODB_URL, DATABASE_NAME
            
            client = pymongo.MongoClient(MONGODB_URL)
            db = client[DATABASE_NAME]
            file_store_collection = db.file_store
            
            # Determine file type and ID
            file_type = None
            file_id = None
            file_name = "File"
            
            if file_message.document:
                file_type = "document"
                file_id = file_message.document.file_id
                file_name = file_message.document.file_name or "Document"
            elif file_message.video:
                file_type = "video"
                file_id = file_message.video.file_id
                file_name = file_message.video.file_name or "Video"
            elif file_message.audio:
                file_type = "audio"
                file_id = file_message.audio.file_id
                file_name = file_message.audio.file_name or "Audio"
            elif file_message.photo:
                file_type = "photo"
                file_id = file_message.photo[-1].file_id
                file_name = "Photo"
            
            if file_id and file_type:
                # Save to file store collection
                file_store_collection.insert_one({
                    "channel_post_id": forwarded_msg.message_id,
                    "file_type": file_type,
                    "file_id": file_id,
                    "file_name": file_name,
                    "caption": file_message.caption or "",
                    "uploaded_at": datetime.now(),
                    "uploader_id": user.id
                })
                
                logger.info(f"✅ File saved to store: msg_id={forwarded_msg.message_id}, type={file_type}")
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


async def send_auto_forward_notification(update, context):
    """
    Send a simple confirmation message to the user after forwarding the file
    """
    if AUTO_FORWARD_ENABLED:
        await update.message.reply_text(
            "✅ Your leeched file has been backed up to the channel successfully!"
        )


async def test_auto_forward(context, chat_id):
    """
    Test auto-forward functionality (Admin only)
    """
    try:
        if not AUTO_FORWARD_ENABLED:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Auto-forward is disabled. Enable it in config."
            )
            return
        
        if not BACKUP_CHANNEL_ID:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Backup channel ID not configured."
            )
            return
        
        # Send test message to backup channel
        test_message = await context.bot.send_message(
            chat_id=BACKUP_CHANNEL_ID,
            text=f"🧪 **Auto-Forward Test**\n\n"
                 f"📅 Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                 f"🤖 Bot: Working correctly\n"
                 f"📢 Channel: Active\n\n"
                 f"✅ Auto-forward system is functioning properly!"
        )
        
        # Confirm to admin
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ **Auto-Forward Test Successful!**\n\n"
                 f"📢 Test message sent to backup channel\n"
                 f"🆔 Channel ID: {BACKUP_CHANNEL_ID}\n"
                 f"📨 Message ID: {test_message.message_id}\n\n"
                 f"Auto-forward system is working correctly!"
        )
    
    except TelegramError as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **Auto-Forward Test Failed**\n\n"
                 f"Error: {str(e)}\n\n"
                 f"Check:\n"
                 f"• Bot is admin in backup channel\n"
                 f"• Channel ID is correct: {BACKUP_CHANNEL_ID}\n"
                 f"• Bot has send message permissions"
        )
    
    except Exception as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **Auto-Forward Test Error**\n\nUnexpected error: {str(e)}"
                )
        
