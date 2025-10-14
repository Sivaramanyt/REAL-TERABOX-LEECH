"""
Random Videos Handler - SEPARATE verification from Terabox leech
"""
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import users_collection, get_user_data
from verification import generate_verify_token, generate_monetized_verification_link
from config import BOT_USERNAME, VERIFY_TOKEN_TIMEOUT

logger = logging.getLogger(__name__)

# Video verification settings
FREE_VIDEO_LIMIT = 3
VIDEO_STORAGE_CHANNEL = -1002819858433  # Your backup channel

# 🎬 ADD YOUR VIDEO MESSAGE IDs HERE (Replace with actual message IDs from your channel)
VIDEO_MESSAGE_IDS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]

async def handle_videos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /videos command with SEPARATE verification system
    """
    user_id = update.effective_user.id
    
    # Get user data
    user_data = get_user_data(user_id)
    if not user_data:
        await update.message.reply_text("❌ Database error. Try /start first")
        return
    
    video_attempts = user_data.get("video_attempts", 0)
    video_verified = user_data.get("video_verified", False)
    
    # Check if user needs verification
    if not video_verified and video_attempts >= FREE_VIDEO_LIMIT:
        await send_video_verification_message(update, context)
        return
    
    # User can watch video
    await send_random_video(update, context, user_data, video_attempts, video_verified)

async def send_random_video(update: Update, context: ContextTypes.DEFAULT_TYPE, user_data, video_attempts, video_verified):
    """
    Send random video to user and update attempts
    """
    user_id = update.effective_user.id
    
    # Increment video attempts if not verified
    if not video_verified:
        users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"video_attempts": 1}}
        )
        video_attempts += 1
    
    try:
        # 🎬 FORWARD ACTUAL VIDEO from storage channel
        random_video_id = random.choice(VIDEO_MESSAGE_IDS)
        
        # Forward video from storage channel
        await context.bot.forward_message(
            chat_id=user_id,
            from_chat_id=VIDEO_STORAGE_CHANNEL,
            message_id=random_video_id
        )
        
        # Confirmation message
        await update.message.reply_text("✅ Video sent!")
        
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        await update.message.reply_text(
            f"❌ Error sending video. Please try again.\n\n"
            f"Debug: Video ID {random_video_id}, Channel: {VIDEO_STORAGE_CHANNEL}"
        )
        return
    
    # Show status
    if video_verified:
        status_msg = "♾️ **Status:** Video Verified (Unlimited videos)"
    else:
        remaining = FREE_VIDEO_LIMIT - video_attempts
        status_msg = f"⏳ **Remaining:** {remaining}/{FREE_VIDEO_LIMIT} free videos"
        
        if remaining == 0:
            status_msg += "\n\n🔒 **Next video requires verification!**"
    
    await update.message.reply_text(status_msg, parse_mode='Markdown')

async def send_video_verification_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Send VIDEO verification message (SEPARATE from leech verification)
    """
    user_id = update.effective_user.id
    token = generate_verify_token()
    
    # Store video verification token
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"video_verify_token": token}}
    )
    
    verify_link = generate_monetized_verification_link(BOT_USERNAME, token)
    
    if not verify_link:
        await update.message.reply_text("❌ Error generating verification link")
        return
    
    # Calculate validity time
    validity_hours = VERIFY_TOKEN_TIMEOUT / 3600
    if validity_hours >= 24:
        validity_str = f"{int(validity_hours / 24)} days"
    elif validity_hours >= 1:
        validity_str = f"{int(validity_hours)} hours"
    else:
        validity_str = f"{int(VERIFY_TOKEN_TIMEOUT / 60)} minutes"
    
    message = (
        "🎬 **Video Verification Required!**\n\n"
        f"You've used {FREE_VIDEO_LIMIT} free videos!\n\n"
        "Click below to verify:\n\n"
        f"🔗 {verify_link}\n\n"
        f"✨ **Unlimited videos for {validity_str} after verification!**\n\n"
        "**Note:** This is separate from Terabox leech verification."
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Verify for Videos", url=verify_link)],
        [InlineKeyboardButton("📺 How to Verify?", url="https://t.me/Sr_Movie_Links/52")],
        [InlineKeyboardButton("💬 ANY HELP", url="https://t.me/Siva9789")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
