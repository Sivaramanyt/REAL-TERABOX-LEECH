"""
Telegram Uploader - Uploads files to Telegram with progress updates
"""

import os
import asyncio
from telegram import Update
from telegram.constants import ChatAction
import logging

logger = logging.getLogger(__name__)

async def upload_file(update: Update, file_path: str, filename: str):
    """
    Uploads file to Telegram chat
    """
    try:
        chat = update.effective_chat
        
        # Send upload action
        await update.bot.send_chat_action(chat_id=chat.id, action=ChatAction.UPLOAD_DOCUMENT)
        
        with open(file_path, "rb") as file_obj:
            message = await update.bot.send_document(
                chat_id=chat.id,
                document=file_obj,
                filename=filename
            )
        logger.info(f"Uploaded {filename} to chat {chat.id}")
        return message
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise
    finally:
        try:
            # Clean up file after upload
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file {file_path} after upload")
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
