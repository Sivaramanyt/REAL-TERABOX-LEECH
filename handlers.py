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
        token = extract_token_from_start(context.args[0])
        if token:
            verified_user_id = verify_user(token)
            if verified_user_id:
                # Calculate validity time automatically
                validity_hours = VERIFY_TOKEN_TIMEOUT / 3600
                
                # Format validity time
                if validity_hours >= 24:
                    validity_str = f"{int(validity_hours / 24)} days"
                elif validity_hours >= 1:
                    validity_str = f"{int(validity_hours)} hours"
                else:
                    validity_str = f"{int(VERIFY_TOKEN_TIMEOUT / 60)} minutes"
                
                # Get user data to show expiry time
                user_data = get_user_data(verified_user_id)
                verify_expiry = user_data.get("verify_expiry")
                
                success_message = (
                    "🎉 **Verification Successful!**\n\n"
                    f"✅ You now have unlimited access!\n\n"
                    f"⏰ **Validity:** {validity_str}\n"
                )
                
                if verify_expiry:
                    expiry_time = verify_expiry.strftime('%Y-%m-%d %H:%M:%S IST')
                    success_message += f"📅 **Expires On:** {expiry_time}\n\n"
                
                success_message += "🚀 Start using the bot to leech files!"
                await update.message.reply_text(success_message, parse_mode='Markdown')
                return
            else:
                await update.message.reply_text(
                    "❌ Verification failed. Please try again.",
                    parse_mode='Markdown'
                )
                return
    
    # Normal start message
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

• 3 free leech attempts
• After 3, click verification link
• Unlimited access after verification
• All files auto-backed up to channel

**Commands:**
/start - Start bot
/help - Show this help
/stats - View your stats
/videos - Get random videos

**Admin Commands:**
/testforward - Test auto-forward
/testapi - Test shortlink API
/debugapi - Debug shortlink
/resetverify - Reset all verification
/resetvideos - Reset video verification only

Bot uses universal shortlinks for monetization!
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def send_verification_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Send verification message with improved template
    Matches video verification style
    """
    user_id = update.effective_user.id
    token = generate_verify_token()
    
    if set_verification_token(user_id, token):
        verify_link = generate_monetized_verification_link(BOT_USERNAME, token)
        
        if verify_link:
            # Calculate validity time
            validity_hours = VERIFY_TOKEN_TIMEOUT / 3600
            if validity_hours >= 24:
                validity_str = f"{int(validity_hours / 24)} days"
            elif validity_hours >= 1:
                validity_str = f"{int(validity_hours)} hours"
            else:
                validity_str = f"{int(VERIFY_TOKEN_TIMEOUT / 60)} minutes"
            
            # NEW TEMPLATE matching your screenshot requirements
            message = (
                "🔒 **Verification Required!**\n\n"
                "Click below to verify:\n\n"
                f"🔗 {verify_link}\n\n"
                f"✨ **Unlimited access for {validity_str} after verification!**"
            )
            
            # UPDATED KEYBOARD with your requirements
            keyboard = [
                [InlineKeyboardButton("✅ Verify Now", url=verify_link)],
                [InlineKeyboardButton("📺 How to Verify?", url="https://t.me/Sr_Movie_Links/52")],
                [InlineKeyboardButton("💬 ANY HELP", url="https://t.me/Siva9789")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Error generating verification link. Check API config.")
    else:
        await update.message.reply_text("❌ Error setting up verification. Try again.")

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
            await forward_file_to_channel(context, user, success_message)
        
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
👤 **Your Stats**

📊 Leech Attempts: {used_attempts}
✅ Verification Status: {'Verified' if is_verified else 'Not Verified'}
📅 Joined: {join_date.strftime('%Y-%m-%d') if hasattr(join_date, 'strftime') else join_date}
📢 Auto-Forward: {'Enabled' if AUTO_FORWARD_ENABLED else 'Disabled'}
{'🚀 Status: Unlimited Access' if is_verified else f'⏳ Remaining: {FREE_LEECH_LIMIT - used_attempts} free attempts'}
"""
    
    # Show bot stats for owner
    if user_id == OWNER_ID:
        bot_stats = get_bot_stats()
        bot_stats_text = f"""
📊 **Bot Stats (Admin)**

👥 Total Users: {bot_stats['total_users']}
✅ Verified Users: {bot_stats['verified_users']}
📈 Total Attempts: {bot_stats['total_attempts']}
📢 Backup Channel: {BACKUP_CHANNEL_ID if BACKUP_CHANNEL_ID else 'Not Set'}
🔗 Universal Shortlinks: Enabled
💰 Monetization: Active
"""
        user_stats += bot_stats_text
    
    await update.message.reply_text(user_stats, parse_mode='Markdown')

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
            "Verification will work with any shortlink."
        )
    else:
        await update.message.reply_text("❌ API Test Failed! Please check your API key and URL.")

async def debug_shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Admin only.")
        return
    
    await update.message.reply_text("🪛 Testing all shortlink formats...")
    link = create_universal_shortlink("https://google.com")
    await update.message.reply_text(f"Debug result: {link if link else 'No shortlink created.'}")

async def reset_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    IMPROVED RESET FUNCTION - Resets BOTH video and Terabox leech verification
    """
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Only the bot owner can use this command.")
        return
    
    try:
        if context.args:
            target_id = int(context.args[0])
        else:
            target_id = user_id
        
        # ✅ FIXED: RESET BOTH VIDEO AND TERABOX LEECH VERIFICATION (using correct field names)
        result = users_collection.update_one(
            {"user_id": target_id},
            {
                "$set": {
                    # Leech verification
                    "is_verified": False,
                    "leech_attempts": 0,
                    "verify_token": None,
                    "verify_expiry": None,
                    "token_expiry": None,
                    # Video verification (correct field names)
                    "is_video_verified": False,  # ✅ FIXED: was "video_verified"
                    "video_attempts": 0,
                    "video_verify_token": None,
                    "video_token_expiry": None,
                    "video_verify_expiry": None
                }
            }
        )
        
        if result.modified_count > 0:
            await update.message.reply_text(
                f"✅ **FULL RESET COMPLETE** for user `{target_id}`\n\n"
                f"🔄 **Reset Items:**\n"
                f"• Video Verification\n"
                f"• Terabox Leech Verification\n"
                f"• All Attempt Counters\n"
                f"• Verification Tokens\n\n"
                f"User will now need to verify again for both features!",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "ℹ️ No change made. User may not exist or already reset.",
                parse_mode='Markdown'
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ✅ NEW FUNCTION: Reset only video verification
async def reset_video_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Reset ONLY video verification for a user (Admin only)
    Usage: /resetvideos or /resetvideos <user_id>
    """
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Admin command only!")
        return
    
    # Get user_id from command or use self
    if context.args and len(context.args) > 0:
        try:
            target_user_id = int(context.args[0])
        except:
            await update.message.reply_text("❌ Invalid user ID!")
            return
    else:
        target_user_id = user_id
    
    try:
        result = users_collection.update_one(
            {"user_id": target_user_id},
            {
                "$set": {
                    "video_attempts": 0,
                    "is_video_verified": False,
                    "video_verify_token": None,
                    "video_token_expiry": None,
                    "video_verify_expiry": None
                }
            }
        )
        
        if result.modified_count > 0:
            await update.message.reply_text(
                f"✅ **VIDEO RESET COMPLETE** for user {target_user_id}\n\n"
                f"🔄 **Reset Items:**\n"
                f"• Video Verification\n"
                f"• Video Attempts\n"
                f"• Verification Tokens\n\n"
                f"User will now need to verify again for videos after 3 attempts!",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"⚠️ User {target_user_id} not found or already reset!",
                parse_mode='Markdown'
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
                
