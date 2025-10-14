"""
Video Verification System - Separate from Leech Verification
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    get_user_data, set_video_verification_token, verify_video_user
)
from verification import generate_verify_token, create_universal_shortlink
from config import FREE_VIDEO_LIMIT, BOT_USERNAME

logger = logging.getLogger(__name__)

async def send_video_verification_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send video verification message"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if not user_data:
        await update.message.reply_text("❌ User data not found. Please use /start")
        return
    
    video_attempts = user_data.get("video_attempts", 0)
    
    # Generate token
    token = generate_verify_token()
    set_video_verification_token(user_id, token)
    
    # Create bot deep link
    video_token = f"video_{token}"
    bot_link = f"https://t.me/{BOT_USERNAME}?start={video_token}"
    
    # Create shortlink
    verification_link = create_universal_shortlink(bot_link)
    
    keyboard = [
        [InlineKeyboardButton("✅ Verify for Videos", url=verification_link)],
        [InlineKeyboardButton("📢 Join Channel", url="https://t.me/RARE_VIDEOS")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"🎬 **Video Verification Required**\n\n"
        f"You've used **{video_attempts}/{FREE_VIDEO_LIMIT}** free videos!\n\n"
        f"To continue watching random videos:\n\n"
        f"🔹 Click \"✅ Verify for Videos\" below\n"
        f"🔹 Complete the verification\n"
        f"🔹 Return and use `/videos`\n\n"
        f"**After verification:**\n"
        f"♾️ Unlimited random videos\n\n"
        f"**Note:** This is separate from Terabox leech verification."
    )

    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    logger.info(f"✅ Sent video verification to user {user_id}")

async def handle_video_verification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str):
    """Handle video verification callback"""
    user_id = update.effective_user.id
    
    logger.info(f"Video verification attempt for user {user_id}")
    
    if verify_video_user(user_id, token):
        await update.message.reply_text(
            "🎉 **Video Verification Successful!**\n\n"
            "✅ You now have unlimited access to random videos!\n"
            "🎬 Use `/videos` to watch videos!",
            parse_mode='Markdown'
        )
        logger.info(f"✅ Video verification SUCCESS for user {user_id}")
    else:
        await update.message.reply_text(
            "❌ **Video Verification Failed**\n\n"
            "The link may have expired.\n"
            "Try `/videos` again to get a new link.",
            parse_mode='Markdown'
        )
        logger.warning(f"❌ Video verification FAILED for user {user_id}")
                         
