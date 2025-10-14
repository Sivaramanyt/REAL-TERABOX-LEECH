"""
Video Verification System - Separate from Leech Verification
FIXED: Proper user_id extraction from all contexts (message, callback, effective_user)
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

def get_user_id_from_update(update: Update) -> int:
    """
    SAFELY extract user_id from update in ANY context
    Handles: message, callback_query, effective_user
    """
    try:
        # Priority 1: From callback query (button clicks)
        if update.callback_query:
            return update.callback_query.from_user.id
        
        # Priority 2: From message (direct commands)
        if update.message:
            return update.message.from_user.id
        
        # Priority 3: From effective_user (fallback)
        if update.effective_user:
            return update.effective_user.id
        
        # Should never reach here, but log if it does
        logger.error("❌ Could not extract user_id from update!")
        return None
    except Exception as e:
        logger.error(f"❌ Error extracting user_id: {e}")
        return None

async def send_video_verification_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Send video verification message
    FIXED: Properly extracts user_id from any context
    """
    # ✅ FIXED: Get user_id safely from any context
    user_id = get_user_id_from_update(update)
    
    if not user_id:
        logger.error("❌ Cannot send verification - user_id not found")
        return
    
    user_data = get_user_data(user_id)
    
    if not user_data:
        message_text = "❌ User data not found. Please use /start"
        
        # Send to appropriate context
        if update.message:
            await update.message.reply_text(message_text)
        elif update.callback_query:
            await update.callback_query.message.reply_text(message_text)
        return
    
    video_attempts = user_data.get("video_attempts", 0)
    
    # Generate token
    token = generate_verify_token()
    set_video_verification_token(user_id, token)
    
    logger.info(f"✅ Generated video verification token for user {user_id}: video_{token}")
    
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
    
    # Send to appropriate context
    if update.message:
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    logger.info(f"✅ Sent video verification to user {user_id}")

async def handle_video_verification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str):
    """
    Handle video verification callback when user returns from shortlink
    FIXED: Properly extracts user_id from any context
    """
    # ✅ FIXED: Get user_id safely from any context
    user_id = get_user_id_from_update(update)
    
    if not user_id:
        logger.error("❌ Cannot verify - user_id not found")
        return
    
    logger.info(f"🔍 Video verification attempt for user {user_id} with token: video_{token}")
    
    if verify_video_user(user_id, token):
        success_message = (
            "🎉 **Video Verification Successful!**\n\n"
            "✅ You now have unlimited access to random videos!\n"
            "🎬 Use `/videos` to watch videos!"
        )
        
        # Send to appropriate context
        if update.message:
            await update.message.reply_text(success_message, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.message.reply_text(success_message, parse_mode='Markdown')
        
        logger.info(f"✅ Video verification SUCCESS for user {user_id}")
    else:
        fail_message = (
            "❌ **Video Verification Failed**\n\n"
            "**Possible reasons:**\n"
            "🔸 The link has expired (6 hours timeout)\n"
            "🔸 You clicked an old verification link\n"
            "🔸 Token mismatch or already used\n\n"
            "**Solution:**\n"
            "Try `/videos` again to get a NEW verification link!"
        )
        
        # Send to appropriate context
        if update.message:
            await update.message.reply_text(fail_message, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.message.reply_text(fail_message, parse_mode='Markdown')
        
        logger.warning(f"❌ Video verification FAILED for user {user_id}")
    
