"""
Command and message handlers with universal shortlink support
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (
    get_user_data, increment_leech_attempts, can_user_leech, 
    needs_verification, set_verification_token, verify_user, get_bot_stats
)
from verification import generate_verify_token, generate_monetized_verification_link, extract_token_from_start, test_shortlink_api
from auto_forward import forward_file_to_channel, send_auto_forward_notification, test_auto_forward
from config import (
    START_MESSAGE, VERIFICATION_MESSAGE, VERIFIED_MESSAGE, 
    FREE_LEECH_LIMIT, VERIFY_TUTORIAL, BOT_USERNAME, OWNER_ID,
    AUTO_FORWARD_ENABLED, BACKUP_CHANNEL_ID
)

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id
    
    # Check if it's a verification start
    if context.args:
        token = extract_token_from_start(context.args[0])
        if token:
            verified_user_id = verify_user(token)
            if verified_user_id:
                await update.message.reply_text(VERIFIED_MESSAGE, parse_mode='Markdown')
                return
            else:
                await update.message.reply_text(
                    "❌ **Invalid or expired verification token.**\n\n"
                    "Please request a new verification link.",
                    parse_mode='Markdown'
                )
                return
    
    # Get user data
    user_data = get_user_data(user_id)
    if not user_data:
        await update.message.reply_text("❌ Database error. Please try again later.")
        return
    
    # Format start message
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
    """Handle /help command"""
    help_text = """
🤖 **Terabox Leech Bot Help**

**How it works:**
1. You get 3 free leech attempts
2. After 3 attempts, you need to verify
3. Once verified, unlimited access
4. All files auto-backed up to channel 📢

**Commands:**
/start - Start the bot
/help - Show this help message
/leech - Make a leech attempt
/stats - Check your stats

**Admin Commands:**
/testforward - Test auto-forward (Admin only)
/testapi - Test shortlink API (Admin only)

**Verification Process:**
1. Use all 3 free attempts
2. Bot will provide monetized verification link
3. Complete the verification (earns you money 💰)
4. Enjoy unlimited access!

**Note:** This is currently in testing phase. 
Actual Terabox leeching will be added later.

**Universal Shortlinks:** 
Bot supports all shortlink services - arolinks, gplinks, shrinkme, and more!
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def leech_attempt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle leech attempts (simulated) with auto-forward"""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # Check if user can make attempt
    if not can_user_leech(user_id):
        if needs_verification(user_id):
            await send_verification_message(update, context)
            return
        else:
            await update.message.reply_text("❌ Error checking your account. Please try /start")
            return
    
    # Increment attempts
    if increment_leech_attempts(user_id):
        user_data = get_user_data(user_id)
        used_attempts = user_data.get("leech_attempts", 0)
        is_verified = user_data.get("is_verified", False)
        
        # Simulate successful leech
        success_message = await update.message.reply_text(
            f"✅ **Leech Attempt #{used_attempts}**\n\n"
            "🚀 Processing your request...\n"
            "📁 File: Sample_File.mp4\n"
            "📊 Status: Success (Simulated)\n"
            "📢 Auto-forwarding to backup channel...",
            parse_mode='Markdown'
        )
        
        # AUTO-FORWARD THE FILE ⭐
        if AUTO_FORWARD_ENABLED:
            # In Phase 2, this will be the actual downloaded file
            # For now, forward the success message as simulation
            forward_success = await forward_file_to_channel(
                context, user, success_message, 
                original_link="https://terabox.com/s/simulated_link"
            )
            
            if forward_success:
                await send_auto_forward_notification(update, context)
        
        # Show remaining attempts for non-verified users
        if not is_verified and used_attempts < FREE_LEECH_LIMIT:
            remaining = FREE_LEECH_LIMIT - used_attempts
            await update.message.reply_text(
                f"⏳ **Remaining Free Attempts:** {remaining}\n\n"
                "**Note:** This is a simulation. Real leeching will be added later!",
                parse_mode='Markdown'
            )
        elif used_attempts >= FREE_LEECH_LIMIT and not is_verified:
            # User has used all attempts, send verification
            await send_verification_message(update, context)
    else:
        await update.message.reply_text("❌ Error processing your request. Please try again.")

async def send_verification_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send verification message with monetized shortlink"""
    user_id = update.effective_user.id
    
    # Generate verification token
    token = generate_verify_token()
    
    # Save token to database
    if set_verification_token(user_id, token):
        # Generate monetized verification link using universal system
        verify_link = generate_monetized_verification_link(BOT_USERNAME, token)
        
        if verify_link:
            message = VERIFICATION_MESSAGE.format(
                limit=FREE_LEECH_LIMIT,
                verify_link=verify_link,
                tutorial=VERIFY_TUTORIAL
            )
            
            # Create inline keyboard
            keyboard = [
                [InlineKeyboardButton("💰 Verify Now (Earn Money)", url=verify_link)],
                [InlineKeyboardButton("📺 How to Verify?", url=VERIFY_TUTORIAL)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message, 
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "❌ Error generating verification link. Please try again later."
            )
    else:
        await update.message.reply_text(
            "❌ Error setting up verification. Please try again later."
        )

async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle verification callback queries"""
    query = update.callback_query
    await query.answer()
    
    # This can be used for additional verification steps if needed
    await query.edit_message_text("Please use the verification link to complete the process.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    user_id = update.effective_user.id
    
    # User stats
    user_data = get_user_data(user_id)
    if not user_data:
        await update.message.reply_text("❌ Error getting your stats.")
        return
    
    used_attempts = user_data.get("leech_attempts", 0)
    is_verified = user_data.get("is_verified", False)
    join_date = user_data.get("joined_date", "Unknown")
    
    user_stats = f"""
👤 **Your Stats**

📊 **Leech Attempts:** {used_attempts}
✅ **Verification Status:** {'Verified' if is_verified else 'Not Verified'}
📅 **Joined:** {join_date.strftime('%Y-%m-%d') if hasattr(join_date, 'strftime') else join_date}
📢 **Auto-Forward:** {'Enabled' if AUTO_FORWARD_ENABLED else 'Disabled'}

{f'🚀 **Status:** Unlimited Access' if is_verified else f'⏳ **Remaining:** {FREE_LEECH_LIMIT - used_attempts} free attempts'}
"""
    
    # Bot stats (only for owner)
    if user_id == OWNER_ID:
        bot_stats = get_bot_stats()
        bot_stats_text = f"""

🤖 **Bot Stats** (Admin Only)

👥 **Total Users:** {bot_stats['total_users']}
✅ **Verified Users:** {bot_stats['verified_users']}
📊 **Total Attempts:** {bot_stats['total_attempts']}
📢 **Backup Channel:** {BACKUP_CHANNEL_ID if BACKUP_CHANNEL_ID else 'Not Set'}
🔗 **Universal Shortlinks:** Enabled
💰 **Monetization:** Active
"""
        user_stats += bot_stats_text
    
    await update.message.reply_text(user_stats, parse_mode='Markdown')

async def test_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test auto-forward functionality (Admin only)"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ This command is only for admins.")
        return
    
    await test_auto_forward(context, update.effective_chat.id)

async def test_shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test universal shortlink API (Admin only)"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ This command is only for admins.")
        return
    
    await update.message.reply_text("🧪 **Testing Universal Shortlink API...**", parse_mode='Markdown')
    
    # Test the API
    if test_shortlink_api():
        await update.message.reply_text(
            "✅ **Universal Shortlink API Test Successful!**\n\n"
            "🌐 **Service:** Auto-detected\n"
            "💰 **Monetization:** Working\n" 
            "🔗 **Verification Links:** Will work perfectly\n\n"
            "Your verification system is ready to earn money!",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ **Universal Shortlink API Test Failed**\n\n"
            "🔧 **Please check:**\n"
            "• SHORTLINK_API key is correct\n"
            "• SHORTLINK_URL is valid\n"
            "• Service is online\n\n"
            "💡 **Tip:** Bot will fallback to direct links if shortlink fails.",
            parse_mode='Markdown'
        )
        
