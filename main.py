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
    reset_video_verify,  # NEW
    dashboard_callback   # NEW
)
from database import db
from health_server import run_health_server

# Import Terabox handlers (+ cancel)
from terabox_handlers import handle_terabox_link, cancel_leech_callback, cancel_current_leech

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

try:
    from random_videos import send_random_video, handle_random_video_callback, auto_save_video
    RANDOM_VIDEOS_ENABLED = True
except ImportError:
    logger.warning("⚠️ random_videos.py not found - Random videos feature disabled")
    RANDOM_VIDEOS_ENABLED = False

try:
    from channel_monitor import cleanup_invalid_videos
    CHANNEL_MONITOR_ENABLED = True
except ImportError:
    logger.warning("⚠️ channel_monitor.py not found - Auto-cleanup disabled")
    CHANNEL_MONITOR_ENABLED = False

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
   ✅ Enabled with split>300MB, cancel, and concurrency caps

🎬 Random Videos:
   {'✅ Enabled with SEPARATE video verification' if RANDOM_VIDEOS_ENABLED else '❌ Disabled (file not found)'}

🗑️ Channel Monitor:
   {'✅ Auto-cleanup enabled' if CHANNEL_MONITOR_ENABLED else '❌ Manual cleanup only'}

📊 Dashboard Menu:
   ✅ Interactive dashboard enabled

===== STARTUP COMPLETE =====
"""
    print(startup_info)
    logger.info("Bot configuration loaded successfully")

async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        handled = await handle_terabox_link(update, context)
        if not handled:
            await leech_attempt(update, context)
    except Exception as e:
        logger.error(f"❌ Message router error: {e}")
        await update.message.reply_text("❌ An error occurred while processing your message. Please try again.")

def main():
    try:
        display_startup_info()
        logger.info("🏥 Starting health server...")
        run_health_server()

        logger.info("🤖 Creating bot application...")
        application = Application.builder().token(BOT_TOKEN).build()

        logger.info("⚙️ Registering handlers...")
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("leech", leech_attempt))
        application.add_handler(CommandHandler("stats", stats))
        application.add_handler(CommandHandler("cancel", cancel_current_leech))  # NEW

        if RANDOM_VIDEOS_ENABLED:
            application.add_handler(CommandHandler("videos", send_random_video))
            application.add_handler(CallbackQueryHandler(handle_random_video_callback, pattern="^random_video$"))
            application.add_handler(MessageHandler(
                filters.ChatType.CHANNEL & (filters.VIDEO | filters.Document.ALL),
                auto_save_video
            ))

        if CHANNEL_MONITOR_ENABLED:
            application.add_handler(CommandHandler("cleanup_videos", cleanup_invalid_videos))

        application.add_handler(CommandHandler("testforward", test_forward))
        application.add_handler(CommandHandler("testapi", test_shortlink))
        application.add_handler(CommandHandler("resetverify", reset_verify))
        application.add_handler(CommandHandler("resetvideos", reset_video_verify))

        application.add_handler(CallbackQueryHandler(dashboard_callback))  # dashboard
        application.add_handler(CallbackQueryHandler(cancel_leech_callback, pattern=r"^cancel_leech:\d+$"))  # NEW

        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
        application.add_handler(CallbackQueryHandler(verify_callback))  # keep last

        application.run_polling(allowed_updates=["message", "callback_query", "channel_post"])

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
