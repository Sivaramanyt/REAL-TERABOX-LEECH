import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (
    get_user_data, increment_leech_attempts, can_user_leech, 
    needs_verification, set_verification_token, verify_user, get_bot_stats
)
from verification import (
    generate_verify_token, generate_monetized_verification_link, 
    extract_token_from_start, test_shortlink_api, create_universal_shortlink
)
from auto_forward import forward_file_to_channel, send_auto_forward_notification, test_auto_forward
from config import (
    START_MESSAGE, VERIFICATION_MESSAGE, VERIFIED_MESSAGE, 
    FREE_LEECH_LIMIT, VERIFY_TUTORIAL, BOT_USERNAME, OWNER_ID,
    AUTO_FORWARD_ENABLED, BACKUP_CHANNEL_ID
)

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    if context.args:
        token = extract_token_from_start(context.args[0])
        if token:
            verified_user_id = verify_user(token)
            if verified_user_id:
                await update.message.reply_text(VERIFIED_MESSAGE, parse_mode='Markdown')
                return
            else:
                await update.message.reply_text(
                    "❌ Verification failed. Please try again.", parse_mode='Markdown'
                )
                return
    user_data = get_user_data(user_id)
    if not user_data:
        await update.message.reply_text("❌ Database error. Please try again later.")
        return
    used_attempts = user_data.get("leech_attempts", 0)
    is_verified = user_data.get("is_verified", False)
    if is_verified:
        verification_status = "✅ **Status:** Verified (Unlimited access)"
    else:
        remaining = FREE_LEECH_LIMIT - used_attempts
        verification_status = f"⏳ **Status:** {remaining} attempts remaining"
    message = START_MESSAGE.format(
        mention=user.mention_markdown(),
        used_attempts=used_attempts,
        verification_status=verification_status
    )
    await update.message.reply_text(message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 **Terabox Leech Bot Help**

- 3 free leech attempts
- After 3, you must verify (by visiting the shortlink)
- Unlimited access after verification
- All files auto-backed up to channel

**Commands:**
/start - Start
/help - Help
/leech - Leech
/stats - Stats

**Admin:**
/testforward - Test auto-forward
/testapi - Test universal shortlink
/debugapi - Deep shortlink debug

Bot will always try your latest shortlink service!
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def leech_attempt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user
    if not can_user_leech(user_id):
        if needs_verification(user_id):
            await send_verification_message(update, context)
            return
        else:
            await update.message.reply_text("❌ Error checking your account. Please try /start")
            return
    if increment_leech_attempts(user_id):
        user_data = get_user_data(user_id)
        used_attempts = user_data.get("leech_attempts", 0)
        is_verified = user_data.get("is_verified", False)
        success_message = await update.message.reply_text(
            f"✅ Leech Attempt #{used_attempts}\n"
            "🚀 Processing your request...\n"
            "📁 File: Sample.mp4\n"
            "📊 Status: Success (Simulated)\n"
            "📢 Auto-forwarding to backup channel..."
        )
        if AUTO_FORWARD_ENABLED:
            forward_success = await forward_file_to_channel(
                context, user, success_message, 
                original_link="https://terabox.com/s/simulated_link"
            )
            if forward_success:
                await send_auto_forward_notification(update, context)
        if not is_verified and used_attempts < FREE_LEECH_LIMIT:
            remaining = FREE_LEECH_LIMIT - used_attempts
            await update.message.reply_text(
                f"⏳ Remaining Free Attempts: {remaining}\n"
                "Note: This is a simulation. Real leeching will be added soon."
            )
        elif used_attempts >= FREE_LEECH_LIMIT and not is_verified:
            await send_verification_message(update, context)
    else:
        await update.message.reply_text("❌ Error processing your request. Please try again.")

async def send_verification_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    token = generate_verify_token()
    if set_verification_token(user_id, token):
        verify_link = generate_monetized_verification_link(BOT_USERNAME, token)
        if verify_link:
            message = (
                "🔒 Verification Required!\n\n"
                f"You have used all your free attempts ({FREE_LEECH_LIMIT}).\n"
                "To continue, please verify using the monetized link (supports bot):\n\n"
                f"🔗 Verification Link: {verify_link}\n"
                f"📺 Tutorial: {VERIFY_TUTORIAL}\n\n"
                "Note: Verification link = money for the bot owner!"
            )
            keyboard = [
                [InlineKeyboardButton("💰 Verify & Support", url=verify_link)],
                [InlineKeyboardButton("📺 How to Verify?", url=VERIFY_TUTORIAL)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup)
        else:
            await update.message.reply_text("❌ Error generating verification link. Check API config.")
    else:
        await update.message.reply_text("❌ Error setting up verification. Try again.")

async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please use the verification link above to complete verification.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    if not user_data:
        await update.message.reply_text("❌ Error getting your stats.")
        return
    used_attempts = user_data.get("leech_attempts", 0)
    is_verified = user_data.get("is_verified", False)
    join_date = user_data.get("joined_date", "Unknown")
    user_stats = f"""
👤 Your Stats

Leech AttemptPts: {used_attempts}
Verification Status: {'Verified' if is_verified else 'Not Verified'}
Joined: {join_date.strftime('%Y-%m-%d') if hasattr(join_date, 'strftime') else join_date}
Auto-Forward: {'Enabled' if AUTO_FORWARD_ENABLED else 'Disabled'}

{'🚀 Status: Unlimited Access' if is_verified else f'⏳ Remaining: {FREE_LEECH_LIMIT - used_attempts} free attempts'}
"""
    if user_id == OWNER_ID:
        bot_stats = get_bot_stats()
        bot_stats_text = f"""
Bot Stats (Admin Only)

Total Users: {bot_stats['total_users']}
Verified Users: {bot_stats['verified_users']}
Total AttemptPts: {bot_stats['total_attempts']}
BackuP Channel: {BACKUP_CHANNEL_ID if BACKUP_CHANNEL_ID else 'Not Set'}
Universal Shortlinks: Enabled
Monetization: Active
"""
        user_stats += bot_stats_text
    await update.message.reply_text(user_stats)

async def test_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ This command is only for admins.")
        return
    await test_auto_forward(context, update.effective_chat.id)

async def test_shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ This command is only for admins.")
        return
    await update.message.reply_text("🧪 Testing Universal Shortlink API...")
    if test_shortlink_api():
        await update.message.reply_text(
            "✅ Universal Shortlink API Test SUCCESSFUL!\n"
            "Your verification system will work with any shortlink service."
        )
    else:
        await update.message.reply_text(
            "❌ API Test Failed! Please check your API key and URL."
        )

async def debug_shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Admin only.")
        return
    await update.message.reply_text("🪛 Testing all shortlink formats...")
    # This triggers a test against all known formats
    link = create_universal_shortlink("https://google.com")
    await update.message.reply_text(
        f"Debug result: {link if link else 'No shortlink created.'}")

