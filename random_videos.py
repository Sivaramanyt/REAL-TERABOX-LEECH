"""
Random Video Feature with SEPARATE Video Verification System
Videos and Leech have independent verification systems
AUTO-REGISTERS users who use /videos without /start
FIXED: Increments attempts AFTER successful video send (not before)
"""

import logging
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_db

logger = logging.getLogger(__name__)

# MongoDB collection for videos
db = get_db()
videos_collection = db['saved_videos']

async def auto_save_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Automatically save videos posted in storage channel
    Bot must be admin in the channel
    """
    message = update.channel_post
    if not message:
        return
    
    # Check if message is from storage channel
    from config import VIDEO_STORAGE_CHANNEL
    if message.chat.id != VIDEO_STORAGE_CHANNEL:
        return
    
    # Check if message has video
    if not message.video:
        return
    
    try:
        # Save video info to database
        video_data = {
            "message_id": message.message_id,
            "file_id": message.video.file_id,
            "file_unique_id": message.video.file_unique_id,
            "duration": message.video.duration,
            "width": message.video.width,
            "height": message.video.height,
            "file_size": message.video.file_size,
            "caption": message.caption if message.caption else None,
            "saved_date": datetime.utcnow(),
            "channel_id": message.chat.id
        }
        
        # Check if video already exists (by file_unique_id)
        existing = videos_collection.find_one({"file_unique_id": video_data["file_unique_id"]})
        
        if not existing:
            videos_collection.insert_one(video_data)
            logger.info(f"✅ Video saved: msg_id={message.message_id}, file_size={video_data['file_size']}")
        else:
            logger.info(f"ℹ️ Video already exists: {video_data['file_unique_id']}")
            
    except Exception as e:
        logger.error(f"❌ Error saving video: {e}")

async def send_random_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Send a random video from saved collection
    AUTO-REGISTERS user if they haven't used /start
    FIXED: Increments attempts AFTER successful send
    """
    from database import (
        get_user_data, increment_video_attempts,
        can_user_watch_video, needs_video_verification
    )
    from video_verification import send_video_verification_message
    from config import FREE_VIDEO_LIMIT
    
    user_id = update.effective_user.id
    
    try:
        # ✅ FIXED: Get or create user data (auto-registers if needed)
        user_data = get_user_data(user_id)
        if not user_data:
            logger.error(f"❌ Failed to get/create user data for {user_id}")
            await update.message.reply_text(
                "❌ Error accessing database. Please try /start first.",
                parse_mode='Markdown'
            )
            return
        
        # Get current video attempts and verification status
        used_attempts = user_data.get("video_attempts", 0)
        is_video_verified = user_data.get("is_video_verified", False)
        
        logger.info(f"🎬 Video request from user {user_id}: attempts={used_attempts}, verified={is_video_verified}")
        
        # Check if user can watch (BEFORE incrementing)
        if not can_user_watch_video(user_id):
            if needs_video_verification(user_id):
                await send_video_verification_message(update, context)
                return
            else:
                await update.message.reply_text(
                    "❌ Error checking video permissions. Try /start",
                    parse_mode='Markdown'
                )
                return
        
        # Get total videos count
        total_videos = videos_collection.count_documents({})
        
        if total_videos == 0:
            await update.message.reply_text(
                "❌ **No videos available yet!**\n\n"
                "Videos will be added soon.",
                parse_mode='Markdown'
            )
            return
        
        # Get random video
        random_video = list(videos_collection.aggregate([{"$sample": {"size": 1}}]))[0]
        
        # ✅ CRITICAL: Send video BEFORE incrementing attempts
        # Create inline keyboard with "Next Video" button
        keyboard = [[InlineKeyboardButton("🎬 Next Video", callback_data="next_video")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        caption = random_video.get('caption', '🎬 Random Video')
        
        await update.message.reply_video(
            video=random_video['file_id'],
            caption=caption,
            reply_markup=reply_markup
        )
        
        logger.info(f"✅ Video sent to user {user_id}")
        
        # ✅ FIXED: Increment AFTER successful send
        increment_video_attempts(user_id)
        
        # Get FRESH user data after increment
        user_data = get_user_data(user_id)
        used_attempts = user_data.get("video_attempts", 0)
        is_video_verified = user_data.get("is_video_verified", False)
        
        # ✅ Show remaining attempts or verification message
        if not is_video_verified and used_attempts < FREE_VIDEO_LIMIT:
            remaining = FREE_VIDEO_LIMIT - used_attempts
            await update.message.reply_text(
                f"✅ **Video sent successfully!**\n\n"
                f"⏳ **Free videos remaining:** {remaining}/{FREE_VIDEO_LIMIT}",
                parse_mode='Markdown'
            )
        elif used_attempts >= FREE_VIDEO_LIMIT and not is_video_verified:
            await update.message.reply_text(
                "✅ **Video sent successfully!**",
                parse_mode='Markdown'
            )
            await send_video_verification_message(update, context)
        else:
            await update.message.reply_text(
                "✅ **Video sent!**\n\n"
                "♾️ **Status:** Video Verified (Unlimited videos)",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"❌ Error sending random video: {e}")
        await update.message.reply_text(
            f"❌ **Error:** {str(e)}",
            parse_mode='Markdown'
        )

async def handle_next_video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle "Next Video" button clicks
    FIXED: Increments attempts AFTER successful send
    """
    from database import (
        get_user_data, increment_video_attempts,
        can_user_watch_video, needs_video_verification
    )
    from video_verification import send_video_verification_message
    from config import FREE_VIDEO_LIMIT
    
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        # Get user data
        user_data = get_user_data(user_id)
        if not user_data:
            await query.message.reply_text(
                "❌ Error accessing database. Please try /start",
                parse_mode='Markdown'
            )
            return
        
        # Get current video attempts and verification status (BEFORE increment)
        used_attempts = user_data.get("video_attempts", 0)
        is_video_verified = user_data.get("is_video_verified", False)
        
        logger.info(f"🎬 Next video callback from user {user_id}: attempts={used_attempts}, verified={is_video_verified}")
        
        # Check if user can watch (BEFORE incrementing)
        if not can_user_watch_video(user_id):
            if needs_video_verification(user_id):
                await send_video_verification_message(update, context)
                return
            else:
                await query.message.reply_text(
                    "❌ Error checking video permissions. Try /start",
                    parse_mode='Markdown'
                )
                return
        
        # Get total videos
        total_videos = videos_collection.count_documents({})
        
        if total_videos == 0:
            await query.message.reply_text(
                "❌ **No videos available!**",
                parse_mode='Markdown'
            )
            return
        
        # Get random video
        random_video = list(videos_collection.aggregate([{"$sample": {"size": 1}}]))[0]
        
        # ✅ CRITICAL: Send video BEFORE incrementing
        keyboard = [[InlineKeyboardButton("🎬 Next Video", callback_data="next_video")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        caption = random_video.get('caption', '🎬 Random Video')
        
        await context.bot.send_video(
            chat_id=query.message.chat_id,
            video=random_video['file_id'],
            caption=caption,
            reply_markup=reply_markup
        )
        
        logger.info(f"✅ Next video sent to user {user_id}")
        
        # ✅ FIXED: Increment AFTER successful send
        increment_video_attempts(user_id)
        
        # Get FRESH user data after increment
        user_data = get_user_data(user_id)
        used_attempts = user_data.get("video_attempts", 0)
        is_video_verified = user_data.get("is_video_verified", False)
        
        # ✅ Show remaining or verification using FRESH data
        if not is_video_verified and used_attempts < FREE_VIDEO_LIMIT:
            remaining = FREE_VIDEO_LIMIT - used_attempts
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"⏳ **Free videos remaining:** {remaining}/{FREE_VIDEO_LIMIT}",
                parse_mode='Markdown'
            )
        elif used_attempts >= FREE_VIDEO_LIMIT and not is_video_verified:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="⏸️ **Free limit reached!** Complete video verification below:",
                parse_mode='Markdown'
            )
            await send_video_verification_message(update, context)
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="♾️ **Unlimited videos available!**",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"❌ Error in next video callback: {e}")
        await query.message.reply_text(
            f"❌ **Error:** {str(e)}",
            parse_mode='Markdown'
                )
        
