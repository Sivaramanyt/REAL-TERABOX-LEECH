import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    get_user_data, increment_leech_attempts, can_user_leech,
    needs_verification, set_verification_token, verify_user, get_bot_stats,
    users_collection
)
from verification import (
    generate_verify_token, generate_monetized_verification_link,
    extract_token_from_start, test_shortlink_api, create_universal_shortlink
)
from auto_forward import forward_file_to_channel, test_auto_forward
from config import (
    START_MESSAGE, VERIFICATION_MESSAGE, VERIFY_TOKEN_TIMEOUT,
    FREE_LEECH_LIMIT, VERIFY_TUTORIAL, BOT_USERNAME, OWNER_ID,
    AUTO_FORWARD_ENABLED, BACKUP_CHANNEL_ID
)

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Check if user came from verification link
    if context.args:
        token_arg = context.args[0]
        
        # Check if it's a VIDEO verification token
        if token_arg.startswith('video_'):
            # Import video verification handler
            from video_verification import handle_video_verification_callback
            # Remove the "video_" prefix to get actual token
            actual_token = token_arg[6:]  # Remove first 6 characters "video_"
            logger.info(f"Processing video verification for user {user_id}")
            await handle_video_verification_callback(update, context, actual_token)
            return
        else:
            # Regular LEECH verification
            token = extract_token_from_start(token_arg)
            if token:
                user_id_from_token = verify_user(token)
                if user_id_from_token:
                    await update.message.reply_text(
                        "✅ **Verification Successful!**\n\n"
                        "🎉 You now have unlimited access to Terabox leech!\n"
                        "📎 Send any Terabox link to start downloading!",
                        parse_mode='Markdown'
                    )
                    return
                else:
                    await update.message.reply_text(
                        "❌ **Verification Failed**\n\n"
                        "The verification link may have expired or is invalid.\n"
                        "Please try leeching again to get a new verification link.",
                        parse_mode='Markdown'
                    )
                    return
    
    # Register user in database
    user_data = get_user_data(user_id)
    
    # Send welcome message
    welcome_text = START_MESSAGE.format(
        user_name=user.first_name,
        user_id=user_id
    )
    
    keyboard = [
        [InlineKeyboardButton("📚 Help", callback_data="help")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("🎬 Random Videos", callback_data="get_videos")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information"""
    help_text = """
📚 **Help - How to Use**

**Terabox Leech:**
• Send any Terabox link to download files
• First 3 leeches are FREE
• After 3 attempts, complete verification for unlimited access

**Random Videos:**
• Use /videos command to get random videos
• First 3 videos are FREE
• After 3 videos, complete verification for unlimited access

**Note:** Terabox and Videos have SEPARATE verifications!

**Commands:**
/start - Start the bot
/help - Show this help
/stats - View bot statistics
/videos - Get random video

**Support:** @YourSupportChannel
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def send_verification_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send verification message for LEECH verification"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if not user_data:
        await update.message.reply_text("❌ User data not found. Please use /start")
        return
    
    leech_attempts = user_data.get("leech_attempts", 0)
    
    # Generate new token
    token = generate_verify_token()
    set_verification_token(user_id, token)
    
    # Create verification link
    verification_link = generate_monetized_verification_link(BOT_USERNAME, token)
    
    # Create verification message
    keyboard = [
        [InlineKeyboardButton("✅ Verify Now", url=verification_link)],
        [InlineKeyboardButton("📚 Tutorial", url=VERIFY_TUTORIAL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = VERIFICATION_MESSAGE.format(
        attempts_used=leech_attempts,
        free_limit=FREE_LEECH_LIMIT
    )
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def leech_attempt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle leech attempt"""
    user_id = update.effective_user.id
    
    # Check if user can leech
    if not can_user_leech(user_id):
        if needs_verification(user_id):
            await send_verification_message(update, context)
            return
        else:
            await update.message.reply_text(
                "❌ An error occurred. Please use /start to register.",
                parse_mode='Markdown'
            )
            return
    
    # Increment leech attempts
    increment_leech_attempts(user_id)
    
    # Process leech (placeholder)
    await update.message.reply_text(
        "✅ **Leech request received!**\n\n"
        "Processing your request...",
        parse_mode='Markdown'
    )

async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle verification callback"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "help":
        await help_command(query, context)
    elif query.data == "stats":
        await stats(query, context)
    elif query.data == "get_videos":
        # Import and call video function
        from random_videos import send_random_video
        # Create fake update with message
        fake_update = Update(update_id=0, message=query.message)
        await send_random_video(fake_update, context)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    stats_data = get_bot_stats()
    
    stats_text = f"""
📊 **Bot Statistics**

👥 **Total Users:** {stats_data['total_users']}
✅ **Verified Users:** {stats_data['verified_users']}
📥 **Total Leeches:** {stats_data['total_attempts']}

🤖 **Bot Status:** Online
"""
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def test_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test auto-forward feature (admin only)"""
    if update.effective_user.id != OWNER_ID:
        return
    
    if not AUTO_FORWARD_ENABLED:
        await update.message.reply_text("❌ Auto-forward is disabled in config")
        return
    
    result = await test_auto_forward(update, context)
    if result:
        await update.message.reply_text("✅ Auto-forward test successful!")
    else:
        await update.message.reply_text("❌ Auto-forward test failed")

async def test_shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test shortlink API (admin only)"""
    if update.effective_user.id != OWNER_ID:
        return
    
    test_url = "https://google.com"
    short_url = create_universal_shortlink(test_url)
    
    if short_url and short_url != test_url:
        await update.message.reply_text(
            f"✅ **Shortlink API Working!**\n\n"
            f"Original: {test_url}\n"
            f"Shortened: {short_url}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Shortlink API test failed")

async def reset_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset user verification (admin only)"""
    if update.effective_user.id != OWNER_ID:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /resetverify <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        users_collection.update_one(
            {"user_id": target_user_id},
            {
                "$set": {
                    "is_verified": False,
                    "is_video_verified": False,
                    "leech_attempts": 0,
                    "video_attempts": 0,
                    "verify_token": None,
                    "video_verify_token": None,
                    "verify_expiry": None,
                    "video_verify_expiry": None
                }
            }
        )
        await update.message.reply_text(
            f"✅ Reset verification for user {target_user_id}\n"
            f"Both leech and video attempts reset to 0"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    
