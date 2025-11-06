# messages.py - All message templates for dashboard

from config import FREE_LEECH_LIMIT, BOT_USERNAME

# ===== DASHBOARD WELCOME MESSAGE =====
def get_welcome_message(user, verification_status):
    """Get main dashboard welcome message"""
    return f"""
🎉 **Welcome to Terabox Leech Bot!**

👤 **User:** {user.mention_markdown()}

{verification_status}

📌 **Available Features:**
• 🔗 Terabox File Leech
• 🔞 Hot Videos 💦
• 📊 Statistics & Analytics
• ⭐ Premium Membership

👇 **Choose an option below:**
"""


# ===== MENU MESSAGES =====
def get_leech_menu_message():
    """Leech menu message"""
    return """
🔗 **Terabox Leech System**

**How to use:**
1️⃣ Copy Terabox link
2️⃣ Send link to this bot
3️⃣ Get instant download link
4️⃣ Download at high speed ⚡

**Features:**
✅ Instant extraction
✅ High speed downloads
✅ Auto file forwarding
✅ No file limits
✅ 24/7 working

**Send any Terabox link:**
"""


def get_videos_menu_message():
    """Hot videos menu message"""
    return """
🔞 **HOT VIDEOS 💦**

**Get Random Videos:**
Click below to get hot videos!

📌 **Features:**
✅ Unlimited videos
✅ HD Quality
✅ Fast streaming
✅ Auto quality adjust
✅ No restrictions

⚠️ **18+ Only**
"""


def get_stats_message(user_id, user_data, FREE_LEECH_LIMIT):
    """User statistics message"""
    used_attempts = user_data.get("leech_attempts", 0)
    is_verified = user_data.get("is_verified", False)
    is_video_verified = user_data.get("is_video_verified", False)
    
    return f"""
📊 **Your Statistics**

👤 **Leech Stats:**
✅ Downloads: {used_attempts}
⏱️ Total Time: {used_attempts * 2}s
📦 Total Size: {used_attempts * 100} MB

🎬 **Video Stats:**
📹 Videos Watched: 0
⏱️ Watch Time: 0m
🔥 Favorite Videos: 0

💳 **Account Status:**
🎯 Leech: {'✅ Verified' if is_verified else '⏳ ' + str(FREE_LEECH_LIMIT - used_attempts) + ' free attempts'}
🔞 Videos: {'✅ Verified' if is_video_verified else '❌ Not verified'}

👇 Next Plan Upgrade: Premium
"""


def get_help_message():
    """Help menu message"""
    return """
ℹ️ **Help & Support**

❓ **Frequently Asked:**

**Q: How to leech files?**
A: Send Terabox link → Get download link

**Q: How to get hot videos?**
A: Click 🔞 Videos → Verify → Unlimited videos

**Q: How long is validity?**
A: 24 hours after verification

**Q: Any restrictions?**
A: No! Unlimited downloads & videos

📧 **Support:**
💬 Chat: @your_support
📞 Call: @your_support
📧 Email: support@yourbot.com

**Commands:**
/start - Dashboard
/help - Help
/stats - Statistics
/videos - Get videos
"""


def get_premium_message():
    """Premium membership message"""
    return """
⭐ **Premium Membership**

💎 **Benefits:**
✅ Unlimited leech downloads
✅ 10 simultaneous downloads
✅ Priority support
✅ Ad-free experience
✅ 500 GB/month limit

🔞 **Hot Videos:**
✅ Unlimited videos
✅ HD Quality always
✅ Early access to new content
✅ No ads
✅ Download videos

💰 **Pricing:**
• 1 Month: $2.99
• 3 Months: $7.99
• 1 Year: $19.99

✨ **Current Plan:** Free (3 attempts)

🔗 [Buy Premium](https://t.me/your_bot)
"""


def get_account_message(user, user_id, user_data):
    """Account information message"""
    is_verified = user_data.get("is_verified", False)
    is_video_verified = user_data.get("is_video_verified", False)
    
    return f"""
🔐 **Account Information**

👤 **Profile:**
📛 Name: {user.first_name} {user.last_name or ''}
🆔 ID: `{user.id}`
📱 Username: @{user.username or 'N/A'}

📅 **Account Status:**
📊 Plan: Free
🎯 Leech: {'✅ Verified' if is_verified else '❌ Not Verified'}
🔞 Videos: {'✅ Verified' if is_video_verified else '❌ Not Verified'}

⚙️ **Settings:**
🔔 Notifications: ON
🎬 Quality: Auto
🌐 Language: English

📈 **Usage:**
📁 Files Leeched: {user_data.get('leech_attempts', 0)}
🎬 Videos Watched: 0
💾 Storage Used: 0 GB
"""


# ===== VERIFICATION MESSAGES =====
def get_video_verification_message():
    """Video verification required message"""
    return """
🔒 **Verification Required for Videos!**

Verify to unlock:
✅ Unlimited hot videos
✅ HD streaming
✅ No restrictions
✅ 24 hour validity

👇 Click below to verify:
"""


def get_video_verification_success_message(validity_str, video_verify_expiry):
    """Video verification success message"""
    message = (
        "🎉 **Video Verification Successful!**\n\n"
        f"✅ You now have unlimited random videos!\n\n"
        f"⏰ **Validity:** {validity_str}\n"
    )
    
    if video_verify_expiry:
        expiry_time = video_verify_expiry.strftime('%Y-%m-%d %H:%M:%S IST')
        message += f"📅 **Expires On:** {expiry_time}\n\n"
    
    message += "🎬 Use /videos to watch unlimited random videos!"
    return message


def get_leech_verification_success_message(validity_str, verify_expiry):
    """Leech verification success message"""
    message = (
        "🎉 **Verification Successful!**\n\n"
        f"✅ You now have unlimited access!\n\n"
        f"⏰ **Validity:** {validity_str}\n"
    )
    
    if verify_expiry:
        expiry_time = verify_expiry.strftime('%Y-%m-%d %H:%M:%S IST')
        message += f"📅 **Expires On:** {expiry_time}\n\n"
    
    message += "🚀 Start using the bot to leech files!"
    return message


def get_verification_link_message(verify_link, validity_str):
    """General verification link message"""
    return (
        "🔒 **Verification Required!**\n\n"
        "Click below to verify:\n\n"
        f"🔗 {verify_link}\n\n"
        f"✨ **Unlimited access for {validity_str} after verification!**"
    )


# ===== ERROR MESSAGES =====
def get_error_messages():
    """All error messages dictionary"""
    return {
        "db_error": "❌ Database error. Please try again later.",
        "verification_failed": "❌ Verification failed or expired. Please try again.",
        "leech_failed": "❌ Leech verification FAILED. Please try again.",
        "no_change": "ℹ️ No change made. User may not exist or already reset.",
        "invalid_user_id": "❌ Invalid user ID!",
        "user_not_found": "❌ User not found!",
        "admin_only": "❌ Admin command only!",
        "api_error": "❌ Error generating verification link. Check API config.",
        "setup_error": "❌ Error setting up verification. Try again.",
        "account_error": "❌ Error checking your account. Please try /start",
        "request_error": "❌ Error processing your request. Please try again.",
        "no_update": "❌ Error getting your stats.",
    }


def get_success_messages():
    """All success messages dictionary"""
    return {
        "leech_reset": "✅ **LEECH RESET COMPLETE**\n🔄 User will need to verify again!",
        "video_reset": "✅ **VIDEO RESET COMPLETE**\n🔄 User will need to verify again!",
        "full_reset": "✅ **FULL RESET COMPLETE**\n🔄 Both features reset!",
    }


# ===== HELP MESSAGES =====
def get_help_command_message():
    """Help command message"""
    return """
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


def get_leech_attempt_message(used_attempts):
    """Leech attempt success message"""
    return (
        f"✅ Leech Attempt #{used_attempts}\n"
        "🚀 Processing your request...\n"
        "📁 File: Sample.mp4\n"
        "📊 Status: Success (Simulated)\n"
        "📢 Auto-forwarding to backup channel..."
    )


def get_remaining_attempts_message(remaining):
    """Remaining attempts message"""
    return (
        f"⏳ Remaining Free Attempts: {remaining}\n"
        "Note: This is a simulation. Real leeching will be added soon."
    )


# ===== BOT STATS MESSAGE =====
def get_bot_stats_message(total_users, verified_users, total_attempts, BACKUP_CHANNEL_ID):
    """Bot statistics message for admin"""
    return f"""
📊 **Bot Stats (Admin)**

👥 Total Users: {total_users}
✅ Verified Users: {verified_users}
📈 Total Attempts: {total_attempts}
📢 Backup Channel: {BACKUP_CHANNEL_ID if BACKUP_CHANNEL_ID else 'Not Set'}
🔗 Universal Shortlinks: Enabled
💰 Monetization: Active
"""


def get_user_stats_message(user_id, used_attempts, is_verified, join_date, AUTO_FORWARD_ENABLED, FREE_LEECH_LIMIT):
    """Individual user stats message"""
    return f"""
👤 **Your Stats**

📊 Leech Attempts: {used_attempts}
✅ Verification Status: {'Verified' if is_verified else 'Not Verified'}
📅 Joined: {join_date.strftime('%Y-%m-%d') if hasattr(join_date, 'strftime') else join_date}
📢 Auto-Forward: {'Enabled' if AUTO_FORWARD_ENABLED else 'Disabled'}
{'🚀 Status: Unlimited Access' if is_verified else f'⏳ Remaining: {FREE_LEECH_LIMIT - used_attempts} free attempts'}
"""
