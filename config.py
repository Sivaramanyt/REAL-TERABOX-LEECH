"""
Configuration file for Terabox Leech Bot with Universal Shortlinks & Auto-Forward
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
VERIFY_TOKEN_TIMEOUT = int(os.getenv("VERIFY_TOKEN_TIMEOUT", "3600"))  # 1 hour

# ========== NEW: VIDEO FEATURE CONFIGURATION ==========
# Add these BEFORE the "# Validation" section

# Video Storage Configuration
VIDEO_STORAGE_CHANNEL = int(os.getenv("VIDEO_STORAGE_CHANNEL", "0"))  # Your private channel ID for videos
FREE_VIDEO_LIMIT = int(os.getenv("FREE_VIDEO_LIMIT", "3"))  # Same as leech limit

# Messages
START_MESSAGE = """
🤖 **Welcome {mention}!**

🚀 **Terabox Leech Bot**
📥 Send me any text or use /leech to simulate downloading

✨ **Features:**
• 3 Free leech attempts
• Universal shortlink verification 💰
• Auto-backup to channel 📢
• Unlimited access after verification

📊 Your Stats: {used_attempts}/3 attempts used
{verification_status}

💡 **Commands:**
/start - Start the bot
/help - Get help
/leech - Simulate leech attempt
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
