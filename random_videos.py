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
        # Get video info
        video = message.video
        file_id = video.file_id
        file_name = video.file_name or f"video_{message.message_id}.mp4"
        file_size = video.file_size
        duration = video.duration
        caption = message.caption or ""
        
        # Save to database
        video_data = {
            'message_id': message.message_id,
            'file_id': file_id,
            'file_name': file_name,
            'file_size': file_size,
            'duration': duration,
            'caption': caption,
            'channel_id': VIDEO_STORAGE_CHANNEL,
            'sent_count': 0
        }
        
        # Insert if not already exists
        if not videos_collection.find_one({'file_id': file_id}):
            videos_collection.insert_one(video_data)
            logger.info(f"✅ Auto-saved video: {file_name}")
        
    except Exception as e:
        logger.error(f"❌ Error auto-saving video: {e}")

async def send_random_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Send a random video from saved collection
    WITH SEPARATE VIDEO VERIFICATION SYSTEM
    AUTO-REGISTERS new users
    FIXED: Increments attempts AFTER successful send
    """
    user_id = update.effective_user.id
    
    # Import verification functions
    from database import get_user_data, increment_video_attempts, users_collection
    from video_verification import send_video_verification_message
    from config import FREE_VIDEO_LIMIT
    
    try:
        # Get or CREATE user data (auto-register if needed)
        user_data = get_user_data(user_id)
        if not user_data:
            # User doesn't exist - create them automatically
            user_data = {
                "user_id": user_id,
                "leech_attempts": 0,
                "video_attempts": 0,
                "is_verified": False,
                "is_video_verified": False,
                "joined_date": datetime.now(),
                "last_activity": datetime.now()
            }
            users_collection.insert_one(user_data)
            logger.info(f"✅ Auto-registered new user {user_id} via /videos command")
        
        video_attempts = user_data.get("video_attempts", 0)
        is_video_verified = user_data.get("is_video_verified", False)
        
        # ✅ Check if user needs VIDEO verification BEFORE sending video
        if not is_video_verified and video_attempts >= FREE_VIDEO_LIMIT:
            await send_video_verification_message(update, context)
            return
        
        # Get total count
        total_videos = videos_collection.count_documents({})
        
        if total_videos == 0:
            await update.message.reply_text(
                "📭 **No videos available yet!**\n\n"
                "The admin hasn't added any videos to the collection yet.\n"
                "Please check back later!",
                parse_mode='Markdown'
            )
            return
        
        # Get random video
        random_videos = list(videos_collection.aggregate([{'$sample': {'size': 1}}]))
        
        if not random_videos:
            await update.message.reply_text(
                "❌ **Error getting video!**\n\n"
                "Please try again.",
                parse_mode='Markdown'
            )
            return
        
        random_video = random_videos[0]
        
        # Send "getting video" message
        status_msg = await update.message.reply_text(
            "🎬 **Getting random video for you...**",
            parse_mode='Markdown'
        )
        
        # Send the video - NO MARKDOWN to avoid parsing errors
        caption = random_video.get('caption', '')
        if caption:
            caption += "\n\n"
        caption += f"🎲 Random Video | 📊 Total: {total_videos}"
        
        # Create buttons
        keyboard = [
            [InlineKeyboardButton("🔄 Next Video", callback_data="random_video")],
            [InlineKeyboardButton("📢 Channel", url="https://t.me/RARE_VIDEOS")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_video(
            video=random_video['file_id'],
            caption=caption,
            reply_markup=reply_markup
        )
        
        # Delete status message
        await status_msg.delete()
        
        # Update sent count
        videos_collection.update_one(
            {'file_id': random_video['file_id']},
            {'$inc': {'sent_count': 1}}
        )
        
        # ✅ NOW increment user's video attempts AFTER successful send
        increment_video_attempts(user_id)
        user_data = get_user_data(user_id)  # Get fresh data
        used_attempts = user_data.get("video_attempts", 0)
        
        logger.info(f"✅ Sent random video to user {user_id} (Video attempt #{used_attempts})")
        
        # Show remaining attempts or verification message
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

async def handle_random_video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle "Next Video" button click
    WITH SEPARATE VIDEO VERIFICATION CHECK
    FIXED: Increments attempts AFTER successful send
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Import video verification functions
    from database import increment_video_attempts, get_user_data, users_collection
    from video_verification import send_video_verification_message
    from config import FREE_VIDEO_LIMIT
    
    try:
        # Get or CREATE user data (auto-register if needed)
        user_data = get_user_data(user_id)
        if not user_data:
            # User doesn't exist - create them automatically
            user_data = {
                "user_id": user_id,
                "leech_attempts": 0,
                "video_attempts": 0,
                "is_verified": False,
                "is_video_verified": False,
                "joined_date": datetime.now(),
                "last_activity": datetime.now()
            }
            users_collection.insert_one(user_data)
            logger.info(f"✅ Auto-registered new user {user_id} via video callback")
        
        video_attempts = user_data.get("video_attempts", 0)
        is_video_verified = user_data.get("is_video_verified", False)
        
        # ✅ Check if user can access videos BEFORE sending (don't increment yet!)
        if not is_video_verified and video_attempts >= FREE_VIDEO_LIMIT:
            await query.message.reply_text(
                "⏸️ **Free videos limit reached!**\n\n"
                "Please complete **video verification** to continue watching.",
                parse_mode='Markdown'
            )
            # Create fake update for verification
            fake_update = Update(update_id=0, message=query.message)
            await send_video_verification_message(fake_update, context)
            return
        
        # Get total count
        total_videos = videos_collection.count_documents({})
        
        if total_videos == 0:
            await query.edit_message_caption(
                caption="📭 **No more videos available!**",
                parse_mode='Markdown'
            )
            return
        
        # Get random video
        random_videos = list(videos_collection.aggregate([{'$sample': {'size': 1}}]))
        
        if not random_videos:
            await query.message.reply_text("❌ Error getting video!", parse_mode='Markdown')
            return
        
        random_video = random_videos[0]
        
        # Send new video
        caption = random_video.get('caption', '')
        if caption:
            caption += "\n\n"
        caption += f"🎲 Random Video | 📊 Total: {total_videos}"
        
        # Create buttons
        keyboard = [
            [InlineKeyboardButton("🔄 Next Video", callback_data="random_video")],
            [InlineKeyboardButton("📢 Channel", url="https://t.me/RARE_VIDEOS")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Delete old video and send new one
        await query.message.delete()
        
        await context.bot.send_video(
            chat_id=query.message.chat_id,
            video=random_video['file_id'],
            caption=caption,
            reply_markup=reply_markup
        )
        
        # Update sent count
        videos_collection.update_one(
            {'file_id': random_video['file_id']},
            {'$inc': {'sent_count': 1}}
        )
        
        # ✅ NOW increment attempts AFTER successful send
        increment_video_attempts(user_id)
        user_data = get_user_data(user_id)  # Get fresh data
        used_attempts = user_data.get("video_attempts", 0)
        
        logger.info(f"✅ Sent next video to user {user_id} (Video attempt #{used_attempts})")
        
        # Show remaining or verification
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
                text="⏸️ **Free limit reached!** Complete video verification for unlimited videos.",
                parse_mode='Markdown'
            )
        
    except Exception as e:
        logger.error(f"❌ Error in callback: {e}")
        await query.message.reply_text(
            f"❌ **Error:** {str(e)}",
            parse_mode='Markdown'
        )

async def video_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show video collection stats (admin only)
    """
    from config import OWNER_ID
    
    if update.effective_user.id != OWNER_ID:
        return
    
    total_videos = videos_collection.count_documents({})
    total_sent_cursor = list(videos_collection.aggregate([
        {'$group': {'_id': None, 'total': {'$sum': '$sent_count'}}}
    ]))
    
    sent_count = total_sent_cursor[0]['total'] if total_sent_cursor else 0
    
    # Get most popular video
    popular = videos_collection.find_one(sort=[('sent_count', -1)])
    
    response = (
        f"📊 **Video Collection Stats**\n\n"
        f"📹 **Total Videos:** {total_videos}\n"
        f"📤 **Total Sent:** {sent_count}\n\n"
    )
    
    if popular:
        response += (
            f"🏆 **Most Popular:**\n"
            f"📝 {popular['file_name']}\n"
            f"📊 Sent {popular['sent_count']} times"
        )
    
    await update.message.reply_text(response, parse_mode='Markdown')
    
