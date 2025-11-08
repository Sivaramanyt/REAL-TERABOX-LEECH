import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (
    get_user_data, increment_leech_attempts, can_user_leech,
    needs_verification, set_verification_token, verify_token, get_user_stats,
    users_collection, verify_video_token
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
# ===== IMPORT MESSAGE TEMPLATES =====
from messages import (
    get_welcome_message, get_leech_menu_message, get_videos_menu_message,
    get_stats_message, get_help_message, get_premium_message, get_account_message,
    get_video_verification_message, get_video_verification_success_message,
    get_leech_verification_success_message, get_verification_link_message,
    get_error_messages, get_success_messages, get_help_command_message,
    get_leech_attempt_message, get_remaining_attempts_message, get_bot_stats_message,
    get_user_stats_message
)

from start_hooks import handle_start_v_param, handle_start_dl_param  # ADDED

logger = logging.getLogger(__name__)

# ===== DASHBOARD CALLBACK HANDLER =====
async def dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all dashboard button clicks"""
    
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    # LEECH MENU
    if query.data == "leech_menu":
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=get_leech_menu_message(),
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # HOT VIDEOS MENU
    elif query.data == "videos_menu":
        keyboard = [
            [InlineKeyboardButton("📹 Get Random Video", callback_data="get_video")],
            [InlineKeyboardButton("🔄 Next Video", callback_data="get_video")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=get_videos_menu_message(),
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # GET VIDEO
    elif query.data == "get_video":
        user_data = get_user_data(user_id)
        is_video_verified = user_data.get("is_video_verified", False)
        
        if is_video_verified:
            await query.edit_message_text(
                text="🎬 **Random Hot Video**\n\n📹 Sending video...",
                parse_mode="Markdown"
            )
        else:
            token = generate_verify_token()
            if set_verification_token(user_id, token):
                verify_link = generate_monetized_verification_link(BOT_USERNAME, token)
                keyboard = [[InlineKeyboardButton("✅ Verify & Get Videos", url=verify_link)]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    text=get_video_verification_message(),
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
    
    # STATS MENU
    elif query.data == "stats_menu":
        user_data = get_user_data(user_id)
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=get_stats_message(user_id, user_data, FREE_LEECH_LIMIT),
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # HELP MENU
    elif query.data == "help_menu":
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=get_help_message(),
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # PREMIUM MENU
    elif query.data == "premium_menu":
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=get_premium_message(),
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # ACCOUNT MENU
    elif query.data == "account_menu":
        user = query.from_user
        user_data = get_user_data(user_id)
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=get_account_message(user, user_id, user_data),
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # BACK BUTTON
    elif query.data == "back_menu":
        user_data = get_user_data(user_id)
        is_verified = user_data.get("is_verified", False)
        
        if is_verified:
            verification_status = "✅ **Status:** Verified (Unlimited access)"
        else:
            remaining = FREE_LEECH_LIMIT - user_data.get("leech_attempts", 0)
            verification_status = f"⏳ **Status:** {remaining} attempts remaining"
        
        keyboard = [
            [
                InlineKeyboardButton("🔗 Terabox Leech", callback_data="leech_menu"),
                InlineKeyboardButton("🔞 HOT VIDEOS 💦", callback_data="videos_menu")
            ],
            [
                InlineKeyboardButton("📊 My Stats", callback_data="stats_menu"),
                InlineKeyboardButton("ℹ️ Help", callback_data="help_menu")
            ],
            [
                InlineKeyboardButton("⭐ Premium", callback_data="premium_menu"),
                InlineKeyboardButton("🔐 Account", callback_data="account_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        user = query.from_user
        await query.edit_message_text(
            text=get_welcome_message(user, verification_status),
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )


# ===== START COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    logger.info(f"========== START COMMAND RECEIVED ==========")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Arguments: {context.args}")

    # ===== ADDED: Deep-link delivery and verification return branches =====
    if context.args and len(context.args) > 0:  # ADDED
        arg0 = context.args[0]                 # ADDED
        # 1) Channel poster deep-link delivery: v_<message_id>  (3 free then verify)  # ADDED
        handled = await handle_start_v_param(update, context, arg0)  # ADDED
        if handled:                                                   # ADDED
            return                                                     # ADDED
        # 2) Deep-link verification completion: dl_<token>             # ADDED
        handled = await handle_start_dl_param(update, context, arg0)  # ADDED
        if handled:                                                   # ADDED
            return       
    # Check if user came from verification link
    if context.args:
        full_token = extract_token_from_start(context.args[0])
        logger.info(f"Extracted token: {full_token}")
        if full_token:
            # VIDEO VERIFICATION
            if full_token.startswith("video_"):
                logger.info(f"✅ VIDEO VERIFICATION TOKEN DETECTED: {full_token}")
                actual_token = full_token.replace("video_", "", 1)
                verified_user_id = verify_video_token(actual_token)
                
                if verified_user_id:
                    validity_hours = VIDEO_VERIFY_TOKEN_TIMEOUT / 3600
                    if validity_hours >= 24:
                        validity_str = f"{int(validity_hours / 24)} days"
                    elif validity_hours >= 1:
                        validity_str = f"{int(validity_hours)} hours"
                    else:
                        validity_str = f"{int(VIDEO_VERIFY_TOKEN_TIMEOUT / 60)} minutes"
                    
                    user_data = get_user_data(verified_user_id)
                    video_verify_expiry = user_data.get("video_verify_expiry")
                    
                    await update.message.reply_text(
                        get_video_verification_success_message(validity_str, video_verify_expiry),
                        parse_mode='Markdown'
                    )
                    return
                else:
                    logger.warning(f"❌ Video verification FAILED for user {user_id}")
                    errors = get_error_messages()
                    await update.message.reply_text(errors["verification_failed"], parse_mode='Markdown')
                    return
            
            # LEECH VERIFICATION
            else:
                logger.info(f"LEECH VERIFICATION TOKEN: {full_token}")
                actual_token = full_token.replace("verify_", "", 1)
                verified_user_id = verify_token(actual_token)
                
                if verified_user_id:
                    validity_hours = VERIFY_TOKEN_TIMEOUT / 3600
                    if validity_hours >= 24:
                        validity_str = f"{int(validity_hours / 24)} days"
                    elif validity_hours >= 1:
                        validity_str = f"{int(validity_hours)} hours"
                    else:
                        validity_str = f"{int(VERIFY_TOKEN_TIMEOUT / 60)} minutes"
                    
                    user_data = get_user_data(verified_user_id)
                    verify_expiry = user_data.get("verify_expiry")
                    
                    await update.message.reply_text(
                        get_leech_verification_success_message(validity_str, verify_expiry),
                        parse_mode='Markdown'
                    )
                    return
                else:
                    logger.warning(f"❌ Leech verification FAILED for user {user_id}")
                    errors = get_error_messages()
                    await update.message.reply_text(errors["leech_failed"], parse_mode='Markdown')
                    return

    # Normal start - Show dashboard
    logger.info(f"No verification token - showing dashboard menu")
    user_data = get_user_data(user_id)
    if not user_data:
        errors = get_error_messages()
        await update.message.reply_text(errors["db_error"])
        return

    used_attempts = user_data.get("leech_attempts", 0)
    is_verified = user_data.get("is_verified", False)

    if is_verified:
        verification_status = "✅ **Status:** Verified (Unlimited access)"
    else:
        remaining = FREE_LEECH_LIMIT - used_attempts
        verification_status = f"⏳ **Status:** {remaining} attempts remaining"

    keyboard = [
        [
            InlineKeyboardButton("🔗 Terabox Leech", callback_data="leech_menu"),
            InlineKeyboardButton("🔞 HOT VIDEOS 💦", callback_data="videos_menu")
        ],
        [
            InlineKeyboardButton("📊 My Stats", callback_data="stats_menu"),
            InlineKeyboardButton("ℹ️ Help", callback_data="help_menu")
        ],
        [
            InlineKeyboardButton("⭐ Premium", callback_data="premium_menu"),
            InlineKeyboardButton("🔐 Account", callback_data="account_menu")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        get_welcome_message(user, verification_status),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


# ===== OTHER COMMANDS (KEEP AS IS) =====
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_help_command_message(), parse_mode='Markdown')


async def send_verification_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    token = generate_verify_token()
    if set_verification_token(user_id, token):
        verify_link = generate_monetized_verification_link(BOT_USERNAME, token)
        if verify_link:
            validity_hours = VERIFY_TOKEN_TIMEOUT / 3600
            if validity_hours >= 24:
                validity_str = f"{int(validity_hours / 24)} days"
            elif validity_hours >= 1:
                validity_str = f"{int(validity_hours)} hours"
            else:
                validity_str = f"{int(VERIFY_TOKEN_TIMEOUT / 60)} minutes"

            message = get_verification_link_message(verify_link, validity_str)
            keyboard = [
                [InlineKeyboardButton("✅ Verify Now", url=verify_link)],
                [InlineKeyboardButton("📺 How to Verify?", url="https://t.me/Sr_Movie_Links/52")],
                [InlineKeyboardButton("💬 ANY HELP", url="https://t.me/Siva9789")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            errors = get_error_messages()
            await update.message.reply_text(errors["api_error"])
    else:
        errors = get_error_messages()
        await update.message.reply_text(errors["setup_error"])


async def leech_attempt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user
    if not can_user_leech(user_id):
        if needs_verification(user_id):
            await send_verification_message(update, context)
            return
        else:
            errors = get_error_messages()
            await update.message.reply_text(errors["account_error"])
            return

    if increment_leech_attempts(user_id):
        user_data = get_user_data(user_id)
        used_attempts = user_data.get("leech_attempts", 0)
        is_verified = user_data.get("is_verified", False)

        success_message = await update.message.reply_text(
            get_leech_attempt_message(used_attempts)
        )

        if AUTO_FORWARD_ENABLED:
            await forward_file_to_channel(context, user, success_message)

        if not is_verified and used_attempts < FREE_LEECH_LIMIT:
            remaining = FREE_LEECH_LIMIT - used_attempts
            await update.message.reply_text(get_remaining_attempts_message(remaining))
        elif used_attempts >= FREE_LEECH_LIMIT and not is_verified:
            await send_verification_message(update, context)
    else:
        errors = get_error_messages()
        await update.message.reply_text(errors["request_error"])


async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please use the verification link above to complete verification.")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    if not user_data:
        errors = get_error_messages()
        await update.message.reply_text(errors["no_update"])
        return

    used_attempts = user_data.get("leech_attempts", 0)
    is_verified = user_data.get("is_verified", False)
    join_date = user_data.get("joined_date", "Unknown")

    user_stats = get_user_stats_message(user_id, used_attempts, is_verified, join_date, AUTO_FORWARD_ENABLED, FREE_LEECH_LIMIT)

    if user_id == OWNER_ID:
        try:
            total_users = users_collection.count_documents({})
            verified_users = users_collection.count_documents({"is_verified": True})
            pipeline = [{"$group": {"_id": None, "total": {"$sum": "$leech_attempts"}}}]
            total_attempts_result = list(users_collection.aggregate(pipeline))
            total_attempts = total_attempts_result[0]["total"] if total_attempts_result else 0
            user_stats += get_bot_stats_message(total_users, verified_users, total_attempts, BACKUP_CHANNEL_ID)
        except Exception as e:
            logger.error(f"Error getting bot stats: {e}")

    await update.message.reply_text(user_stats, parse_mode='Markdown')


async def test_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        errors = get_error_messages()
        await update.message.reply_text(errors["admin_only"])
        return
    await test_auto_forward(context, update.effective_chat.id)


async def test_shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        errors = get_error_messages()
        await update.message.reply_text(errors["admin_only"])
        return

    await update.message.reply_text("🧪 Testing Universal Shortlink API...")
    if test_shortlink_api():
        await update.message.reply_text("✅ Universal Shortlink API Test SUCCESSFUL!\nVerification will work with any shortlink.")
    else:
        await update.message.reply_text("❌ API Test Failed! Please check your API key and URL.")


async def debug_shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        errors = get_error_messages()
        await update.message.reply_text(errors["admin_only"])
        return

    await update.message.reply_text("🪛 Testing all shortlink formats...")
    link = create_universal_shortlink("https://google.com")
    await update.message.reply_text(f"Debug result: {link if link else 'No shortlink created.'}")


async def reset_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        errors = get_error_messages()
        await update.message.reply_text(errors["admin_only"])
        return

    try:
        if context.args:
            target_id = int(context.args[0])
        else:
            target_id = user_id

        result = users_collection.update_one(
            {"user_id": target_id},
            {"$set": {
                "is_verified": False,
                "leech_attempts": 0,
                "verify_token": None,
                "verify_expiry": None,
                "token_expiry": None,
                "is_video_verified": False,
                "video_attempts": 0,
                "video_verify_token": None,
                "video_token_expiry": None,
                "video_verify_expiry": None
            }}
        )

        if result.modified_count > 0:
            success = get_success_messages()
            await update.message.reply_text(
                f"✅ **FULL RESET COMPLETE** for user `{target_id}`\n\n"
                f"🔄 **Reset Items:**\n"
                f"• Video Verification\n"
                f"• Terabox Leech Verification\n"
                f"• All Attempt Counters\n"
                f"• Verification Tokens",
                parse_mode='Markdown'
            )
        else:
            errors = get_error_messages()
            await update.message.reply_text(errors["no_change"], parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def reset_video_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        errors = get_error_messages()
        await update.message.reply_text(errors["admin_only"])
        return

    if context.args and len(context.args) > 0:
        try:
            target_user_id = int(context.args[0])
        except:
            errors = get_error_messages()
            await update.message.reply_text(errors["invalid_user_id"])
            return
    else:
        target_user_id = user_id

    try:
        result = users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {
                "video_attempts": 0,
                "is_video_verified": False,
                "video_verify_token": None,
                "video_token_expiry": None,
                "video_verify_expiry": None
            }}
        )

        if result.modified_count > 0:
            success = get_success_messages()
            await update.message.reply_text(
                f"✅ **VIDEO RESET COMPLETE** for user {target_user_id}\n\n"
                f"🔄 **Reset Items:**\n"
                f"• Video Verification\n"
                f"• Video Attempts\n"
                f"• Verification Tokens",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"ℹ️ User {target_user_id} not found or already reset!",
                parse_mode='Markdown'
            )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
