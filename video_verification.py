"""
Video Verification System - Separate from Leech Verification
Users must verify separately for videos after 3 video attempts
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    get_user_data, needs_video_verification, set_video_verification_token, 
    verify_video_user
)
from verification import generate_verify_token, generate_monetized_verification_link
from config import FREE_VIDEO_LIMIT, BOT_USERNAME

logger = logging.getLogger(__name__)

async def send_video_verification_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send video verification message (separate from leech verification)"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if not user_data:
        await update.message.reply_text("❌ User data not found. Please use /start")
        return
    
    video_attempts = user_data.get("video_attempts", 0)
    
    # Generate new video verification token
    token = generate_verify_token()
    set_video_verification_token(user_id, token)
    
    # Create verification link with "video_" prefix to distinguish from leech verification
    video_token = f"video_{token}"
    verification_link = generate_monetized_verification_link(BOT_USERNAME, video_token)
    
    # Create verification message
    keyboard = [
        [InlineKeyboardButton("✅ Verify for Videos", url=verification_link)],
        [InlineKeyboardButton("📢 Join Channel", url="https://t.me/RARE_VIDEOS")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"🎬 **Video Verification Required**\n\n"
        f"You've used **{video_attempts}/{FREE_VIDEO_LIMIT}** free videos!\n\n"
        f"To continue watching random videos, please complete the verification:\n\n"
        f"🔹 Click \"✅ Verify for Videos\" below\n"
        f"🔹 Complete the verification process\n"
        f"🔹 Return and use `/videos` command\n\n"
        f"**After verification:**\n"
        f"♾️ **Unlimited random videos**\n"
        f"🎯 **Instant access**\n"
        f"⚡ **No more limits**\n\n"
        f"**Note:** This is separate from Terabox leech verification. Each feature requires its own verification."
    )

    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def handle_video_verification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str):
    """Handle video verification callback when user returns from verification"""
    user_id = update.effective_user.id
    
    # Verify the token for videos
    if verify_video_user(user_id, token):
        await update.message.reply_text(
            "🎉 **Video Verification Successful!**\n\n"
            "✅ You now have **unlimited access** to random videos!\n"
            "🎬 Use `/videos` to watch random videos anytime!",
            parse_mode='Markdown'
        )
        logger.info(f"✅ Video verification completed for user {user_id}")
    else:
        await update.message.reply_text(
            "❌ **Video Verification Failed**\n\n"
            "The verification link may have expired or is invalid.\n"
            "Please try watching videos again to get a new verification link.",
            parse_mode='Markdown'
        )
        logger.warning(f"❌ Video verification failed for user {user_id}")
