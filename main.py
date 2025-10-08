"""
Terabox Leech Bot with Universal Shortlink Verification & Auto-Forward
"""

import logging
import asyncio
import sys
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from config import *
# FIXED IMPORT - Add missing test_shortlink function
from handlers import (
    start, help_command, leech_attempt, verify_callback, 
    stats, test_forward, test_shortlink
)
from database import init_db
from health_server import run_health_server

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def display_startup_info():
    """Display startup information"""
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

===== STARTUP COMPLETE ===== 
"""
    print(startup_info)
    logger.info("Bot configuration loaded successfully")

def main():
    """Start the bot"""
    try:
        # Display startup info
        display_startup_info()
        
        # Start health server
        logger.info("🏥 Starting health server...")
        run_health_server()
        
        # Initialize database
        logger.info("💾 Initializing database...")
        init_db()
        
        # Create application
        logger.info("🤖 Creating bot application...")
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        logger.info("⚙️ Registering handlers...")
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("leech", leech_attempt))
        application.add_handler(CommandHandler("stats", stats))
        application.add_handler(CommandHandler("testforward", test_forward))
        application.add_handler(CommandHandler("testapi", test_shortlink))
        
        # Message handler
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, leech_attempt))
        
        # Callback handler
        application.add_handler(CallbackQueryHandler(verify_callback))
        
        logger.info("🚀 Bot started successfully with Universal Shortlinks!")
        
        # Run the bot
        application.run_polling(allowed_updates=["message", "callback_query"])
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
        
