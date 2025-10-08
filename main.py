"""
Terabox Leech Bot with Verification System & Auto-Forward
Phase 1: Verification-Only Bot (No actual leeching)
Author: Sivaramany
"""

import logging
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from config import *
from handlers import start, help_command, leech_attempt, verify_callback, stats, test_forward
from database import init_db

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Start the bot."""
    # Initialize database
    init_db()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("leech", leech_attempt))
    application.add_handler(CommandHandler("stats", stats))
    
    # Admin commands
    application.add_handler(CommandHandler("testforward", test_forward))
    
    # Message handler for text (fake leech attempts)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, leech_attempt))
    
    # Callback query handler for verification
    application.add_handler(CallbackQueryHandler(verify_callback))
    
    logger.info("🚀 Terabox Leech Bot started successfully with auto-forward!")
    
    # Run the bot
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == '__main__':
    main()
  
