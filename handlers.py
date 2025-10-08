import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_user_data, increment_leech_attempts, can_user_leech, needs_verification, set_verification_token, verify_user, get_bot_stats, users_collection
from verification import generate_verify_token, generate_monetized_verification_link, extract_token_from_start, test_shortlink_api, create_universal_shortlink
from auto_forward import forward_file_to_channel, send_auto_forward_notification, test_auto_forward
from config import START_MESSAGE, VERIFICATION_MESSAGE, VERIFIED_MESSAGE, FREE_LEECH_LIMIT, VERIFY_TUTORIAL, BOT_USERNAME, OWNER_ID, AUTO_FORWARD_ENABLED, BACKUP_CHANNEL_ID
from terabox_processor import process_terabox_links

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
                await update.message.reply_text("❌ Verification failed. Please try again.", parse_mode='Markdown')
                return
    user_data = get_user_data(user_id)
    if not user_data:
        await update.message.reply_text("❌ Database error. Please try again later.")
        return
    used_attempts = user_data.get("leech_attempts", 0)
    is_verified = user_data.get("is_verified", False)
    verification_status = (
        "✅ **Status:** Verified (Unlimited access)"
        if is_verified else f"⏳ **Status:** {FREE_LEECH_LIMIT - used_attempts} attempts remaining"
    )
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
- After 3, click monetized shortlink to verify
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
/resetverify - Reset user's verification status (Admin only)

Bot always uses your latest shortlink service!
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def leech_attempt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not can_user_leech(user_id):
        if needs_verification(user_id):
            await send_verification_message(update, context)
            return
        else:
            await update.message.reply_text("❌ You have reached your free attempt limit.")
            return
    # Call your real Terabox processing here
    await process_terabox_links(update, context)

async def send_verification_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    token = generate_verify_token()
    if set_verification_token(user_id, token):
        verify_link = generate_monetized_verification_link(BOT_USERNAME, token)
        keyboard = [
            [InlineKeyboardButton("Verify Now", url=verify_link)],
            [InlineKeyboardButton("How to Verify?", url=VERIFY_TUTORIAL)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🔒 Verification Required!\n\nYou have used all your free attempts ({FREE_LEECH_LIMIT}).\n"
            f"To continue, verify using the link below:\n\n🔗 Verification Link: {verify_link}\n📺 Tutorial: {VERIFY_TUTORIAL}\n\n"
            "Note: Verification click = money for this bot.",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("❌ Verification error, please try again.")

async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please use the verification link above to complete verification.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    if not user_data:
        await update.message.reply_text("❌ Error retrieving your stats.")
        return
    used_attempts = user_data.get("leech_attempts", 0)
    is_verified = user_data.get("is_verified", False)
    join_date = user_data.get("joined_date", "Unknown")
    stats_message = (f"👤 Your Stats\n\nLeech Attempts: {used_attempts}\n"
                     f"Verification Status: {'Verified' if is_verified else 'Not Verified'}\n"
                     f"Joined: {join_date}\n"
                     f"Auto-Forward: {'Enabled' if AUTO_FORWARD_ENABLED else 'Disabled'}\n"
                     f"{'🚀 Status: Unlimited Access' if is_verified else f'⏳ Remaining: {FREE_LEECH_LIMIT - used_attempts} free attempts'}")
    if user_id == OWNER_ID:
        bot_stats = get_bot_stats()
        stats_message += (f"\n\nBot Stats (Admin)\nTotal Users: {bot_stats['total_users']}\n"
                          f"Verified Users: {bot_stats['verified_users']}\n"
                          f"Total Attempts: {bot_stats['total_attempts']}\n"
                          f"Backup Channel: {BACKUP_CHANNEL_ID if BACKUP_CHANNEL_ID else 'Not Set'}")
    await update.message.reply_text(stats_message)

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
        await update.message.reply_text("✅ Universal Shortlink API Test SUCCESSFUL!\nVerification will work with any shortlink.")
    else:
        await update.message.reply_text("❌ API Test Failed! Check API key and URL.")

async def debug_shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Admin only.")
        return
    await update.message.reply_text("🪛 Testing all shortlink formats...")
    link = create_universal_shortlink("https://google.com")
    await update.message.reply_text(f"Debug result: {link if link else 'No shortlink created.'}")

async def reset_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Only the bot owner can use this command.")
        return
    try:
        if context.args:
            target_user_id = int(context.args[0])
        else:
            target_user_id = user_id
        result = users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"is_verified": False, "leech_attempts": 0}}
        )
        if result.modified_count > 0:
            await update.message.reply_text(f"✅ Verification RESET for user {target_user_id}. User will now see verification link again.")
        else:
            await update.message.reply_text("ℹ️ No change. User may not exist or already unverified.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error resetting verification: {e}")

# Add any additional handlers you have here, unchanged.
