"""
Channel Monitor - Auto-remove deleted videos from database
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from database import db

logger = logging.getLogger(__name__)

videos_collection = db['saved_videos']

async def handle_deleted_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Automatically remove deleted videos from database
    Triggered when a message is deleted in the storage channel
    """
    
    # Get the deleted message info
    if not update.channel_post:
        return
    
    deleted_message = update.channel_post
    
    # Check if it's from your storage channel
    from config import VIDEO_STORAGE_CHANNEL
    
    if deleted_message.chat.id != VIDEO_STORAGE_CHANNEL:
        return
    
    try:
        # Delete from database using message_id
        result = videos_collection.delete_one({
            "message_id": deleted_message.message_id,
            "channel_id": VIDEO_STORAGE_CHANNEL
        })
        
        if result.deleted_count > 0:
            logger.info(f"✅ Auto-removed deleted video from database: msg_id={deleted_message.message_id}")
        else:
            logger.info(f"ℹ️ Deleted message not found in videos database: msg_id={deleted_message.message_id}")
            
    except Exception as e:
        logger.error(f"❌ Error removing deleted video from database: {e}")


async def cleanup_invalid_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command: /cleanup_videos
    Manually scan and remove videos with invalid file_ids
    """
    user_id = update.effective_user.id
    
    # Check if user is admin/owner
    from config import OWNER_ID
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Only the bot owner can use this command.")
        return
    
    await update.message.reply_text("🔍 **Scanning for invalid videos...**\n\nThis may take a moment.")
    
    try:
        invalid_count = 0
        total_count = videos_collection.count_documents({})
        
        # Get all videos
        all_videos = list(videos_collection.find({}))
        
        for video in all_videos:
            try:
                # Try to get file info from Telegram
                await context.bot.get_file(video['file_id'])
            except Exception:
                # File not found - delete from database
                videos_collection.delete_one({"_id": video["_id"]})
                invalid_count += 1
                logger.info(f"🗑️ Removed invalid video: {video.get('file_name', 'Unknown')}")
        
        await update.message.reply_text(
            f"✅ **Cleanup Complete!**\n\n"
            f"📊 Total videos scanned: {total_count}\n"
            f"🗑️ Invalid videos removed: {invalid_count}\n"
            f"✅ Valid videos remaining: {total_count - invalid_count}"
        )
        
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}")
        await update.message.reply_text(f"❌ **Cleanup failed:** {str(e)}")
