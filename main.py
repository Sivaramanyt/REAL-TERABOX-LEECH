"""
Terabox Leech Bot with Universal Shortlink Verification & Auto-Forward & Random Videos
"""

import logging
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from config import *
from handlers import (
    start, help_command, leech_attempt, verify_callback,
    stats, test_forward, test_shortlink, reset_verify,
    reset_video_verify
)

# ✅ CHANGED: Removed init_db import (no longer exists in new database.py)
# from database import init_db  # ❌ REMOVED THIS LINE
from health_server import run_health_server

# 🎯 IMPORT: Terabox handler
from terabox_handlers import handle_terabox_link

# ✅ CONFIGURE LOGGING FIRST
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# 🎬 Import random video handlers
try:
    from random_videos import send_random_video, handle_next_video_callback, auto_save_video
    RANDOM_VIDEOS_ENABLED = True
    AUTO_SAVE_ENABLED = True
except ImportError as e:
    logger.warning(f"⚠️ random_videos.py import failed: {e}")
    RANDOM_VIDEOS_ENABLED = False
    AUTO_SAVE_ENABLED = False

def print_startup_banner():
    """Print startup configuration"""
    print("\n🚀 ===== TERABOX LEECH BOT STARTUP ===== 🚀\n")
    print(f"📋 Bot Configuration:")
    print(f"   🤖 Bot Username: @{BOT_USERNAME}")
    print(f"   👤 Owner ID: {OWNER_ID}")
    print(f"   💾 Database: ✅ Connected\n")
    
    print(f"💰 Monetization Setup:")
    print(f"   🌐 Universal Shortlinks: {'✅ Enabled' if SHORTLINK_API else '❌ Disabled'}")
    print(f"   🔗 Service URL: {SHORTLINK_URL if SHORTLINK_URL else 'Not Set'}")
    print(f"   🔑 API Key: {'✅ Set' if SHORTLINK_API else '❌ Missing'}\n")
    
    print(f"📢 Auto-Forward:")
    print(f"   {'✅ Enabled' if AUTO_FORWARD_ENABLED else '❌ Disabled'}")
    if AUTO_FORWARD_ENABLED and BACKUP_CHANNEL_ID:
        print(f"   📂 Channel ID: {BACKUP_CHANNEL_ID}\n")
    
    print(f"🎬 Random Videos:")
    print(f"   {'✅ Enabled' if RANDOM_VIDEOS_ENABLED else '❌ Disabled (file not found)'}")
    if RANDOM_VIDEOS_ENABLED:
        print(f"   📹 Free Limit: {FREE_VIDEO_LIMIT} videos")
        print(f"   ⏰ Validity: {VIDEO_VERIFY_TOKEN_TIMEOUT / 3600} hours\n")
    
    print(f"🔐 Verification Settings:")
    print(f"   🎟️ Free Leech Attempts: {FREE_LEECH_LIMIT}")
    print(f"   ⏰ Token Validity: {VERIFY_TOKEN_TIMEOUT / 3600} hours\n")
    print("=" * 50 + "\n")

# ✅ NO async def main() - just run directly!
if __name__ == '__main__':
    # ✅ CHANGED: Removed init_db() call - database auto-connects on import
    # Database connection happens automatically when handlers import database functions
    logger.info("✅ Database module loaded - auto-connecting to MongoDB")
    
    print_startup_banner()
    
    # Build application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("testforward", test_forward))
    application.add_handler(CommandHandler("testapi", test_shortlink))
    application.add_handler(CommandHandler("resetverify", reset_verify))
    application.add_handler(CommandHandler("resetvideos", reset_video_verify))
    application.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify$"))
    
    # Random videos handlers
    if RANDOM_VIDEOS_ENABLED:
        application.add_handler(CommandHandler("videos", send_random_video))
        application.add_handler(CallbackQueryHandler(handle_next_video_callback, pattern="^next_video$"))
        logger.info("✅ Random Videos handlers registered")
    
    # Auto-save video handler
    if AUTO_SAVE_ENABLED:
        application.add_handler(MessageHandler(
            filters.VIDEO & filters.ChatType.CHANNEL,
            auto_save_video
        ))
        logger.info("✅ Auto-save video handler registered")
    
    # Terabox handler
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_terabox_link
    ))
    
    logger.info("✅ All handlers registered")
    
    # Start health server
    run_health_server()
    logger.info("✅ Health server started")
    
    # Start bot
    logger.info("🚀 Starting bot polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    
