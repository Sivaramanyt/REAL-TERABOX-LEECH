"""
Terabox Leech Bot with Universal Shortlink Verification & Auto-Forward & Random Videos
"""

import logging
import asyncio
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from config import *
from handlers import (
    start, help_command, leech_attempt, verify_callback,
    stats, test_forward, test_shortlink, reset_verify,
    reset_video_verify
)
from database import init_db
from health_server import run_health_server

# 🎯 IMPORT: Terabox handler
from terabox_handlers import handle_terabox_link

# ✅ CONFIGURE LOGGING FIRST (BEFORE ANY TRY-EXCEPT BLOCKS)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# 🎬 NEW: Import random video handlers (BOTH command and callback)
try:
    from random_videos import send_random_video, handle_next_video_callback
except ImportError as e:
    logger.warning(f"⚠️ random_videos.py import failed: {e}")
    RANDOM_VIDEOS_ENABLED = False
    send_random_video = None
    handle_next_video_callback = None
else:
    RANDOM_VIDEOS_ENABLED = True

# 🎬 Try to import auto_save_video function
try:
    from random_videos import auto_save_video
    AUTO_SAVE_ENABLED = True
except ImportError:
    logger.warning("⚠️ auto_save_video not found - Auto-save disabled")
    AUTO_SAVE_ENABLED = False
    auto_save_video = None

def print_startup_banner():
    """Print startup configuration"""
    print("\n🚀 ===== TERABOX LEECH BOT STARTUP ===== 🚀\n")
    print(f"📋 Bot Configuration:")
    print(f"   🤖 Bot Username: @{BOT_USERNAME}")
    print(f"   👤 Owner ID: {OWNER_ID}")
    print(f"   💾 Database: ✅ Connected\n")  # ✅ FIXED: Removed init_db() call
    
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

async def main():
    """Main bot function"""
    # ✅ FIXED: Initialize database FIRST, before banner
    if not init_db():
        logger.error("❌ Database initialization failed!")
        return
    
    # ✅ FIXED: Print banner AFTER init_db
    print_startup_banner()
    
    # Build application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ✅ BASIC HANDLERS
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats))
    
    # ✅ ADMIN HANDLERS
    application.add_handler(CommandHandler("testforward", test_forward))
    application.add_handler(CommandHandler("testapi", test_shortlink))
    application.add_handler(CommandHandler("resetverify", reset_verify))
    application.add_handler(CommandHandler("resetvideos", reset_video_verify))
    
    # ✅ CALLBACK HANDLERS
    application.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify$"))
    
    # 🎬 NEW: Random Videos handlers
    if RANDOM_VIDEOS_ENABLED:
        application.add_handler(CommandHandler("videos", send_random_video))
        application.add_handler(CallbackQueryHandler(handle_next_video_callback, pattern="^next_video$"))
        logger.info("✅ Random Videos handlers registered")
    
    # 🎬 NEW: Auto-save video from channel
    if AUTO_SAVE_ENABLED:
        from telegram.ext import MessageHandler, filters
        application.add_handler(MessageHandler(
            filters.VIDEO & filters.ChatType.CHANNEL,
            auto_save_video
        ))
        logger.info("✅ Auto-save video handler registered")
    
    # ✅ TERABOX HANDLER (Must be AFTER random videos to avoid conflicts)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_terabox_link
    ))
    
    logger.info("✅ All handlers registered")
    
    # Start health server
    run_health_server()
    logger.info("✅ Health server started on port 8000")
    
    # Start bot
    logger.info("🚀 Starting bot polling...")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        
