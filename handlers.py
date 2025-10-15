import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    get_user_data, increment_leech_attempts, can_user_leech,
    needs_verification, set_verification_token, verify_token,  # ✅ FIXED: Changed from verify_user
    get_user_stats, users_collection, verify_video_token,  # ✅ FIXED: Changed from verify_video_user
    reset_user_verification, reset_video_verification
)

from verification import (
    generate_verify_token, generate_monetized_verification_link,
    extract_token_from_start, test_shortlink_api, create_universal_shortlink
)

from auto_forward import forward_file_to_channel, test_auto_forward
from config import (
    START_MESSAGE, VERIFICATION_MESSAGE, VERIFY_TOKEN_TIMEOUT,
    FREE_LEECH_LIMIT, VERIFY_TUTORIAL, BOT_USERNAME, OWNER_ID,
    AUTO_FORWARD_ENABLED, BACKUP_CHANNEL_ID, VIDEO_VERIFY_TOKEN_TIMEOUT
)

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # ✅ DEBUG: Log ALL start commands
    logger.info(f"🔵 START command from user {user_id}: {context.args if context.args else 'No args'}")
    
    # Initialize or get user
    get_user_data(user_id)
    
    # Check if there's a token argument
    if context.args:
        token_arg = context.args[0]
        logger.info(f"🔵 Processing token: {token_arg}")
        
        # Extract actual token
        actual_token = extract_token_from_start(token_arg)
        logger.info(f"🔵 Extracted token: {actual_token}")
        
        # Check if it's a video verification token
        if token_arg.startswith("video_verify_"):
            logger.info(f"🎬 Attempting VIDEO verification for token: {actual_token}")
            verified_user_id = verify_video_token(actual_token)  # ✅ FIXED: Changed function call
            
            if verified_user_id:
                await update.message.reply_text(
                    "✅ **Video Verification Successful!**\n\n"
                    f"♾️ You now have **unlimited video access** for {VIDEO_VERIFY_TOKEN_TIMEOUT // 3600} hours!\n\n"
                    "🎬 Use /videos to watch random videos anytime!",
                    parse_mode='Markdown'
                )
                logger.info(f"✅ VIDEO verification successful for user {verified_user_id}")
                return
            else:
                await update.message.reply_text(
                    "❌ **Video Verification Failed**\n\n"
                    "Your verification link is invalid or expired.\n\n"
                    "Use /videos to get a new verification link.",
                    parse_mode='Markdown'
                )
                logger.warning(f"❌ VIDEO verification failed for token: {actual_token}")
                return
        
        # Otherwise treat as leech verification
        logger.info(f"🔐 Attempting LEECH verification for token: {actual_token}")
        verified_user_id = verify_token(actual_token)  # ✅ FIXED: Changed function call
        
        if verified_user_id:
            await update.message.reply_text(
                "✅ **Verification Successful!**\n\n"
                f"🎉 You can now leech unlimited files for {VERIFY_TOKEN_TIMEOUT // 3600} hours!\n\n"
                "📂 Just send me any Terabox link to start.",
                parse_mode='Markdown'
            )
            logger.info(f"✅ LEECH verification successful for user {verified_user_id}")
            return
        else:
            await update.message.reply_text(
                "❌ **Verification Failed**\n\n"
                "Your verification link is invalid or expired.\n\n"
                "Please request a new link by attempting to leech a file.",
                parse_mode='Markdown'
            )
            logger.warning(f"❌ LEECH verification failed for token: {actual_token}")
            return
    
    # No token - send welcome message
    welcome = START_MESSAGE.format(
        user_name=user.first_name,
        bot_username=BOT_USERNAME
    )
    
    keyboard = [
        [InlineKeyboardButton("📖 Help", callback_data="help")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message"""
    help_text = (
        "📖 **How to Use This Bot**\n\n"
        "1️⃣ Send me a Terabox link\n"
        "2️⃣ I'll process and send you the file\n\n"
        f"🎟️ **Free Leeches:** {FREE_LEECH_LIMIT} files\n"
        f"⏰ **Verification Validity:** {VERIFY_TOKEN_TIMEOUT // 3600} hours\n\n"
        "🎬 **Random Videos:** Use /videos to watch random videos\n\n"
        "**Commands:**\n"
        "/start - Start the bot\n"
        "/help - Show this help\n"
        "/stats - View your stats\n"
        "/videos - Watch random videos"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def leech_attempt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle leech attempt - just show verification"""
    user_id = update.effective_user.id
    
    if can_user_leech(user_id):
        await update.message.reply_text(
            "✅ You can leech! Send me a Terabox link.",
            parse_mode='Markdown'
        )
    else:
        # Generate verification
        token = generate_verify_token()
        set_verification_token(user_id, token)
        
        verify_link = generate_monetized_verification_link(token, is_video=False)
        
        message = VERIFICATION_MESSAGE.format(
            free_limit=FREE_LEECH_LIMIT,
            verify_link=verify_link,
            timeout_hours=VERIFY_TOKEN_TIMEOUT // 3600,
            tutorial=VERIFY_TUTORIAL
        )
        
        keyboard = [[InlineKeyboardButton("🔗 Verify Now", url=verify_link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle verify button callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Generate verification
    token = generate_verify_token()
    set_verification_token(user_id, token)
    
    verify_link = generate_monetized_verification_link(token, is_video=False)
    
    message = VERIFICATION_MESSAGE.format(
        free_limit=FREE_LEECH_LIMIT,
        verify_link=verify_link,
        timeout_hours=VERIFY_TOKEN_TIMEOUT // 3600,
        tutorial=VERIFY_TUTORIAL
    )
    
    keyboard = [[InlineKeyboardButton("🔗 Verify Now", url=verify_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user stats"""
    user_id = update.effective_user.id
    user_stats = get_user_stats(user_id)
    
    if not user_stats:
        await update.message.reply_text("❌ No stats found. Use /start first.")
        return
    
    stats_text = (
        "📊 **Your Stats**\n\n"
        f"🎟️ **Leech Attempts:** {user_stats['leech_attempts']}/{FREE_LEECH_LIMIT}\n"
        f"✅ **Leech Verified:** {'Yes' if user_stats['is_verified'] else 'No'}\n\n"
        f"🎬 **Video Attempts:** {user_stats['video_attempts']}\n"
        f"✅ **Video Verified:** {'Yes' if user_stats['is_video_verified'] else 'No'}"
    )
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def test_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Test auto-forward"""
    if update.effective_user.id != OWNER_ID:
        return
    
    result = await test_auto_forward(update.message)
    await update.message.reply_text(result, parse_mode='Markdown')

async def test_shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Test shortlink API"""
    if update.effective_user.id != OWNER_ID:
        return
    
    result = test_shortlink_api()
    await update.message.reply_text(result, parse_mode='Markdown')

async def reset_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Reset user verification"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Admin only command")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /resetverify <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        success = reset_user_verification(target_user_id)
        
        if success:
            await update.message.reply_text(f"✅ Reset verification for user {target_user_id}")
        else:
            await update.message.reply_text(f"❌ Failed to reset user {target_user_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def reset_video_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Reset video verification"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Admin only command")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /resetvideos <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        success = reset_video_verification(target_user_id)
        
        if success:
            await update.message.reply_text(f"✅ Reset video verification for user {target_user_id}")
        else:
            await update.message.reply_text(f"❌ Failed to reset user {target_user_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")
    
