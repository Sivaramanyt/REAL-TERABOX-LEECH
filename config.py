"""
Configuration file for Terabox Leech Bot with Universal Shortlinks & Auto-Forward & Random Videos
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "TeraboxLeechBot")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Database Configuration
MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME", "terabox_bot")

# ========== NEW: TERABOX COOKIE AUTHENTICATION ==========
TERABOX_COOKIE = os.getenv("TERABOX_COOKIE", "")  # Cookie-based method for when APIs fail

# AUTO-FORWARD CONFIGURATION
BACKUP_CHANNEL_ID = int(os.getenv("BACKUP_CHANNEL_ID", "0"))  # Your channel ID
AUTO_FORWARD_ENABLED = os.getenv("AUTO_FORWARD_ENABLED", "True").lower() == "true"

# UNIVERSAL SHORTLINK CONFIGURATION 💰
SHORTLINK_API = os.getenv("SHORTLINK_API")  # Your API key
SHORTLINK_URL = os.getenv("SHORTLINK_URL")  # Your service URL

# Verification Configuration
VERIFY_TUTORIAL = os.getenv("VERIFY_TUTORIAL", "https://youtube.com/watch?v=example")

# Bot Settings
FREE_LEECH_LIMIT = int(os.getenv("FREE_LEECH_LIMIT", "3"))
VERIFY_TOKEN_TIMEOUT = int(os.getenv("VERIFY_TOKEN_TIMEOUT", "43200"))  # 1 hour

# ========== NEW: VIDEO FEATURE CONFIGURATION ==========
VIDEO_STORAGE_CHANNEL = int(os.getenv("VIDEO_STORAGE_CHANNEL", "0"))  # Your private channel ID for videos
FREE_VIDEO_LIMIT = int(os.getenv("FREE_VIDEO_LIMIT", "3"))  # Same as leech limit
VIDEO_VERIFY_TOKEN_TIMEOUT = int(os.getenv("VIDEO_VERIFY_TOKEN_TIMEOUT", "43200"))  # ✅ NEW: 6 hours (21600 seconds)

# Deep-link (channel poster click) gating
FREE_DEEPLINK_LIMIT = int(os.getenv("FREE_DEEPLINK_LIMIT", "3"))
DEEP_LINK_VERIFY_TOKEN_TIMEOUT = int(os.getenv("DEEP_LINK_VERIFY_TOKEN_TIMEOUT", "43200"))

# Auto-post previews to main channel
AUTO_POST_ENABLED = os.getenv("AUTO_POST_ENABLED", "true").lower() == "true"
POST_CHANNEL_ID = int(os.getenv("POST_CHANNEL_ID", "0"))
# Add to your config.py

# Add these lines to your existing config.py

# ============= LULUSTREAM CONFIGURATION =============
LULUSTREAM_API_KEY = os.environ.get("LULUSTREAM_API_KEY", "")

# Source channel - Where you upload videos
SOURCE_CHANNEL_ID = int(os.environ.get("SOURCE_CHANNEL_ID", "0"))

# Adult channel - Where Lulustream links will be posted
ADULT_CHANNEL_ID = int(os.environ.get("ADULT_CHANNEL_ID", "0"))

AUTO_LULUSTREAM = os.environ.get("AUTO_LULUSTREAM", "True")
LULU_TAGS = os.environ.get("LULU_TAGS", "tamil,adult,movies,hd")
LULU_FOLDER_ID = os.environ.get("LULU_FOLDER_ID", "")
# ===================================================


# Messages
START_MESSAGE = """
🤖 **Welcome {mention}!**

🚀 **Terabox Leech Bot with Random Videos**

📥 Send me any Terabox link to start downloading
🎬 Use /videos to watch random videos

✨ **Features:**
• 3 Free leech attempts (Terabox)
• 3 Free random videos
• Universal shortlink verification 💰
• Auto-backup to channel 📢
• Unlimited access after verification

**IMPORTANT:** Terabox leech and Videos have SEPARATE verifications!

📊 Your Stats: {used_attempts}/3 leech attempts used
{verification_status}

💡 **Commands:**
/start - Start the bot
/help - Get help
/videos - Get random video (NEW!)
/stats - Check your stats

🌐 **Universal Shortlinks:** Works with ANY service!
"""

VERIFICATION_MESSAGE = """
🔒 **Verification Required!**

You have used all your free attempts ({limit}).
To continue using the bot, please verify your account.

**How to verify:**
1. Click the monetized verification link below 💰
2. Complete the verification process
3. Come back and try again

🔗 **Verification Link:** {verify_link}
📺 **Tutorial:** {tutorial}

⏰ This verification link expires in 1 hour.

💰 **Note:** Each verification click helps support the bot!

**This is for LEECH only. Videos have separate verification.**
"""

VERIFIED_MESSAGE = """
✅ **Verification Successful!**

🎉 Congratulations! Your account has been verified.

🚀 You now have unlimited access to the bot.
Use /leech to start downloading files!

💰 **Thank you for supporting us through verification!**
"""

# Auto-forward message template
FORWARD_CAPTION_TEMPLATE = """
🤖 **Auto-Forward from Leech Bot**

👤 **User:** {user_name} (@{username})
🆔 **User ID:** {user_id}
📅 **Date:** {date}
🔗 **Original Link:** {original_link}

📊 **User Stats:** {total_attempts} total attempts
✅ **Verification Status:** {verification_status}

💰 **Revenue:** Monetized verification active
🌐 **Shortlinks:** Universal system enabled

#LeechBot #AutoBackup #Monetized
"""

# Validation
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is required")
if not MONGODB_URL:
    raise ValueError("MONGODB_URL is required")
if not SHORTLINK_API:
    raise ValueError("SHORTLINK_API is required - Get from your shortlink service")
if not SHORTLINK_URL:
    raise ValueError("SHORTLINK_URL is required - Get from your shortlink service")
if AUTO_FORWARD_ENABLED and not BACKUP_CHANNEL_ID:
    raise ValueError("BACKUP_CHANNEL_ID is required when auto-forward is enabled")

# Configuration status
print("🚀 Configuration loaded successfully!")
print(f"🤖 Bot: {BOT_USERNAME}")
print(f"🌐 Shortlinks: {'Enabled' if SHORTLINK_API else 'Disabled'}")
print(f"📢 Auto-Forward: {'Enabled' if AUTO_FORWARD_ENABLED else 'Disabled'}")
print(f"💰 Monetization: {'Active' if SHORTLINK_API and SHORTLINK_URL else 'Inactive'}")
print(f"🎬 Random Videos: {'Configured' if VIDEO_STORAGE_CHANNEL else 'Not configured'}")
print(f"🍪 Cookie Method: {'Enabled' if TERABOX_COOKIE else 'Disabled (API-only)'}")
print(f"🔗 Deep-link gate: {FREE_DEEPLINK_LIMIT} free, timeout {DEEP_LINK_VERIFY_TOKEN_TIMEOUT}s")
print(f"AUTO_POST_ENABLED={AUTO_POST_ENABLED}, POST_CHANNEL_ID={POST_CHANNEL_ID}")
