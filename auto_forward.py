"""
Auto Forward System - Forwards ALL user leeched files to channel
FIXED: Uses correct config variable names
"""

import logging
from telegram import Message
from telegram.ext import ContextTypes
from config import AUTO_FORWARD_ENABLED, AUTO_FORWARD_CHANNEL

logger = logging.getLogger(__name__)

async def forward_file_to_channel(context: ContextTypes.DEFAULT_TYPE, user, sent_message: Message):
    """
    Forward ANY file to channel (not just owner's files)
    """
    try:
        if not AUTO_FORWARD_ENABLED:
            logger.info("⚠️ Auto-forward is disabled")
            return False
        
        if not AUTO_FORWARD_CHANNEL:
            logger.warning("⚠️ AUTO_FORWARD_CHANNEL not set")
            return False
        
        # Forward the message to channel
        forwarded = await sent_message.forward(chat_id=AUTO_FORWARD_CHANNEL)
        
        # Send credit message
        user_link = f"[{user.first_name}](tg://user?id={user.id})"
        credit_msg = f"📤 Uploaded by: {user_link}\n🆔 User ID: `{user.id}`"
        
        await context.bot.send_message(
            chat_id=AUTO_FORWARD_CHANNEL,
            text=credit_msg,
            parse_mode='Markdown',
            reply_to_message_id=forwarded.message_id
        )
        
        logger.info(f"✅ Auto-forwarded file from user {user.id} to channel")
        return True
        
    except Exception as e:
        logger.error(f"❌ Auto-forward error: {e}")
        return False

async def test_auto_forward(context: ContextTypes.DEFAULT_TYPE):
    """
    Test if auto-forward is configured correctly
    """
    try:
        if not AUTO_FORWARD_ENABLED:
            return False, "Auto-forward is disabled"
        
        if not AUTO_FORWARD_CHANNEL:
            return False, "AUTO_FORWARD_CHANNEL not configured"
        
        # Try to send a test message
        test_msg = await context.bot.send_message(
            chat_id=AUTO_FORWARD_CHANNEL,
            text="✅ Auto-forward test successful!"
        )
        
        # Delete test message
        await test_msg.delete()
        
        return True, "Auto-forward working correctly"
        
    except Exception as e:
        return False, f"Error: {str(e)}"
        
