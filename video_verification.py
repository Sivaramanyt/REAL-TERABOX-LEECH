"""
Video Verification System - Separate from Leech Verification
FIXED: Proper user_id extraction from all contexts (message, callback, effective_user)
FIXED: Direct shortlink creation without verify_ prefix
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
        
        logger.error("❌ Could not extract user_id from update")
        return None
    except Exception as e:
        logger.error(f"❌ Error extracting user_id: {e}")
        return None

async def send_video_verification_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Send VIDEO verification message with shortlink
    FIXED: Uses direct shortlink without verify_ prefix
    """
    user_id = get_user_id_from_update(update)
    
    if not user_id:
        logger.error("❌ Could not extract user_id from update")
        return
    
    # Generate random token (no prefix)
    token = generate_verify_token()
    
    # Store token in database (no prefix)
    if not set_video_verification_token(user_id, token):
        await update.effective_message.reply_text(
            "❌ **Error setting up verification**\n\nPlease try again.",
            parse_mode='Markdown'
        )
        return
    
    logger.info(f"✅ Generated video verification token for user {user_id}: video_{token}")
    
    # ✅ FIXED: Create Telegram deep link with video_ prefix
    telegram_url = f"https://t.me/{BOT_USERNAME}?start=video_{token}"
    
    # ✅ FIXED: Create shortlink directly (not using generate_monetized_verification_link)
    shortlink = create_universal_shortlink(telegram_url)
    
    if not shortlink or shortlink == telegram_url:
        logger.error("❌ Failed to create video verification shortlink")
        shortlink = telegram_url
    
    logger.info(f"🔗 Video verification shortlink created: {shortlink}")
    
    # Send verification message
    message = (
        "🎬 **Video Verification Required**\n\n"
        f"You've used **{FREE_VIDEO_LIMIT}/{FREE_VIDEO_LIMIT}** free videos!\n\n"
        "To continue watching random videos:\n\n"
        "🔹 Click \"✅ Verify for Videos\" below\n"
        "🔹 Complete the verification\n"
        "🔹 Return and use /videos\n\n"
        "**After verification:**\n"
        "♾️ Unlimited random videos\n\n"
        "**Note:** This is **separate** from Terabox leech verification."
    )
    
    # Create inline keyboard
    keyboard = [
        [InlineKeyboardButton("✅ VERIFY FOR VIDEOS", url=shortlink)],
        [InlineKeyboardButton("📺 HOW TO VERIFY?", url="https://t.me/Sr_Movie_Links/52")],  # ← CHANGED
        [InlineKeyboardButton("💬 ANY HELP", url="https://t.me/Siva9789")]  # ← ADDED NEW BUTTON
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.effective_message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_video_verification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle video verification button clicks
    This is called when user clicks "Verify for Videos" button
    """
    query = update.callback_query
    await query.answer()
    
    user_id = get_user_id_from_update(update)
    
    if not user_id:
        await query.message.reply_text("❌ Error: Could not identify user")
        return
    
    # Check if user is already verified
    user_data = get_user_data(user_id)
    if user_data and user_data.get("is_video_verified", False):
        await query.message.reply_text(
            "✅ **Already Verified!**\n\n"
            "You already have unlimited video access!\n\n"
            "Use /videos to watch random videos.",
            parse_mode='Markdown'
        )
        return
    
    # Send verification message
    await send_video_verification_message(update, context)
            
