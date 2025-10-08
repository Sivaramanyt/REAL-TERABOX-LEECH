"""
Terabox Leech Bot with Universal Shortlink Verification & Auto-Forward
Phase 1: Verification-Only Bot (No actual leeching yet)

Features:
- 3 Free leech attempts with verification system
- Universal shortlink support (works with ANY service)
- Auto-forward to backup channel
- Monetized verification links 
- MongoDB user tracking
- Admin management tools

Author: Sivaramany
Version: 2.0 - Universal Shortlinks Edition
"""

import logging
import asyncio
import sys
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from config import *
from handlers import (
    start, help_command, leech_attempt, verify_callback, 
    stats, test_forward, test_shortlink
)
from database import init_db
from health_server import run_health_server

# Configure advanced logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def display_startup_info():
    """Display startup information and configuration status"""
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
   
⚙️ Bot Settings:
   🎫 Free Attempts: {FREE_LEECH_LIMIT}
   ⏰ Token Timeout: {VERIFY_TOKEN_TIMEOUT}s
   📚 Tutorial: {'✅ Set' if VERIFY_TUTORIAL else '❌ Not set'}

🎯 Phase Status: Phase 1 - Verification System (Testing)
🔄 Next Phase: Real Terabox Leeching Implementation

===== STARTUP COMPLETE ===== 
"""
    print(startup_info)
    logger.info("Bot configuration loaded and validated successfully")

def validate_configuration():
    """Validate all required configuration"""
    errors = []
    warnings = []
    
    # Critical validations
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is missing - Get from @BotFather")
    if not MONGODB_URL:
        errors.append("MONGODB_URL is missing - Setup MongoDB database")
    if not OWNER_ID or OWNER_ID == 0:
        errors.append("OWNER_ID is missing - Get from @userinfobot")
    
    # Monetization validations
    if not SHORTLINK_API:
        warnings.append("SHORTLINK_API is missing - Verification links won't earn money")
    if not SHORTLINK_URL:
        warnings.append("SHORTLINK_URL is missing - Verification system disabled")
    
    # Auto-forward validations
    if AUTO_FORWARD_ENABLED and (not BACKUP_CHANNEL_ID or BACKUP_CHANNEL_ID == 0):
        warnings.append("BACKUP_CHANNEL_ID is missing - Auto-forward disabled")
    
    # Display results
    if errors:
        logger.error("❌ CRITICAL CONFIGURATION ERRORS:")
        for error in errors:
            logger.error(f"   • {error}")
        logger.error("Bot cannot start with these errors!")
        sys.exit(1)
    
    if warnings:
        logger.warning("⚠️ CONFIGURATION WARNINGS:")
        for warning in warnings:
            logger.warning(f"   • {warning}")
        logger.warning("Bot will start but some features may be limited")
    
    logger.info("✅ Configuration validation passed")

async def setup_bot_commands(application):
    """Setup bot commands menu for users"""
    try:
        from telegram import BotCommand
        
        commands = [
            BotCommand("start", "🚀 Start the bot"),
            BotCommand("help", "❓ Get help information"),
            BotCommand("leech", "📥 Make a leech attempt"),
            BotCommand("stats", "📊 Check your statistics"),
        ]
        
        # Add admin commands for owner
        admin_commands = commands + [
            BotCommand("testapi", "🧪 Test shortlink API (Admin)"),
            BotCommand("testforward", "📢 Test auto-forward (Admin)"),
        ]
        
        # Set commands
        await application.bot.set_my_commands(commands)
        logger.info("✅ Bot commands menu set successfully")
        
    except Exception as e:
        logger.warning(f"Could not set bot commands: {e}")

def main():
    """
    Main function - Initialize and start the bot
    """
    try:
        # Display startup information
        display_startup_info()
        
        # Validate configuration
        validate_configuration()
        
        # Start health server for cloud deployment (Koyeb, Railway, etc.)
        logger.info("🏥 Starting health server...")
        run_health_server()
        
        # Initialize database
        logger.info("💾 Initializing database...")
        init_db()
        
        # Create bot application
        logger.info("🤖 Creating bot application...")
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add command handlers
        logger.info("⚙️ Registering command handlers...")
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("leech", leech_attempt))
        application.add_handler(CommandHandler("stats", stats))
        
        # Add admin command handlers
        application.add_handler(CommandHandler("testforward", test_forward))
        application.add_handler(CommandHandler("testapi", test_shortlink))
        
        # Add message handlers
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            leech_attempt
        ))
        
        # Add callback query handler for verification
        application.add_handler(CallbackQueryHandler(verify_callback))
        
        # Setup bot commands menu (async)
        application.job_queue.run_once(
            lambda context: asyncio.create_task(setup_bot_commands(application)),
            when=1
        )
        
        # Success message
        logger.info("🎉 ===== BOT STARTUP SUCCESSFUL ===== 🎉")
        logger.info(f"🚀 {BOT_USERNAME} is now running with Universal Shortlinks!")
        logger.info("💰 Monetization system active - Ready to earn!")
        logger.info("📢 Auto-forward system ready")
        logger.info("🌐 Universal shortlink support enabled")
        logger.info("👥 Waiting for user interactions...")
        
        # Start the bot
        application.run_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True  # Ignore old messages
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Fatal error during bot startup: {e}")
        logger.error("🔧 Please check your configuration and try again")
        sys.exit(1)
    finally:
        logger.info("👋 Bot shutdown complete")

def graceful_shutdown():
    """Handle graceful shutdown"""
    logger.info("🛑 Initiating graceful shutdown...")
    # Add any cleanup tasks here if needed
    logger.info("✅ Shutdown complete")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        graceful_shutdown()
    except Exception as e:
        logger.error(f"❌ Unhandled exception: {e}")
        sys.exit(1)
    
