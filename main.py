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
    stats, test_forward, test_shortlink, reset_verify
)
from database import init_db
from health_server import run_health_server

# 🎯 Terabox handler import
from terabox_handlers import handle_terabox_link

# 🎬 NEW: Random videos imports
from random_videos import auto_save_video, send_random_video, handle_random_video_callback, video_stats_command

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

def display_startup_info():
    startup_info = f"""
🚀 ===== TERABOX LEECH BOT STARTUP ===== 🚀

📋 Bot Configuration:
   🤖 Bot Username: @{BOT_USERNAME}
   👤 Owner ID: {OWNER_ID}
   💾 Database: {'✅ Connected' if MONGODB_URL else '❌ Not configured'}

💰 Monetization Setup:
   🌐 Universal Shortlinks: {'✅ Enabled' if SHORTLINK_API else '❌ Disabled'}
   🔗 Service URL: {SHORTLINK_URL if SHORTLINK_URL else 'Not configured'}
   💵 Revenue System: {'✅ Active' if SHORTLINK_API and SHORTLINK_URL else '❌ Inactive'}

📢 Auto-Forward System:
   📡 Status: {'✅ Enabled' if AUTO_FORWARD_ENABLED else '❌ Disabled'}
   📝 Channel ID: {BACKUP_CHANNEL_ID if BACKUP_CHANNEL_ID else 'Not configured'}

📦 Terabox Leech:
   ✅ Enabled with verification integration

🎬 Random Videos:
   ✅ Enabled with SEPARATE video verification
   📺 Storage Channel: {VIDEO_STORAGE_CHANNEL if VIDEO_STORAGE_CHANNEL else 'Not configured'}

===== STARTUP COMPLETE =====
"""
    print(startup_info)
    logger.info("Bot configuration loaded successfully")

async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route messages to appropriate handler"""
    try:
        # Try Terabox handler first
        handled = await handle_terabox_link(update, context)
        
        # If not a Terabox link, fall back to existing leech_attempt
        if not handled:
            await leech_attempt(update, context)
    except Exception as e:
        logger.error(f"❌ Message router error: {e}")
        await update.message.reply_text(
            "❌ An error occurred while processing your message. Please try again."
        )

def main():
    try:
        display_startup_info()
        
        logger.info("🏥 Starting health server...")
        run_health_server()
        
        logger.info("💾 Initializing database...")
        init_db()
        
        logger.info("🤖 Creating bot application...")
        application = Application.builder().token(BOT_TOKEN).build()
        
        logger.info("⚙️ Registering handlers...")
        
        # Command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("leech", leech_attempt))
        application.add_handler(CommandHandler("stats", stats))
        
        # 🎬 NEW: Random video commands
        application.add_handler(CommandHandler("videos", send_random_video))
        application.add_handler(CommandHandler("videostats", video_stats_command))
        
        # Admin commands
        application.add_handler(CommandHandler("testforward", test_forward))
        application.add_handler(CommandHandler("testapi", test_shortlink))
        application.add_handler(CommandHandler("resetverify", reset_verify))
        
        # 🎬 NEW: Auto-save videos from storage channel
        application.add_handler(MessageHandler(
            filters.ChatType.CHANNEL & filters.VIDEO,
            auto_save_video
        ))
        
        # Message router for text messages
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
        
        # 🎬 NEW: Random video callback handler
        application.add_handler(CallbackQueryHandler(
            handle_random_video_callback,
            pattern="^random_video$"
        ))
        
        # Callback query handler (existing)
        application.add_handler(CallbackQueryHandler(verify_callback))
        
        logger.info("🚀 Bot started successfully with Terabox Leech, Random Videos (SEPARATE verification), Universal Shortlinks!")
        
        application.run_polling(allowed_updates=["message", "callback_query", "channel_post"])
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
        
