from database import get_user_data, needs_verification
from verification import send_verification_message
from terabox_detector import is_terabox_link
from terabox_processor import process_terabox_links
from telegram.ext import ContextTypes

async def terabox_link_handler(update: 'telegram.Update', context: ContextTypes.DEFAULT_TYPE):
    user = get_user_data(update.effective_user.id)
    if not user or not user.get("is_verified", False):
        if needs_verification(update.effective_user.id):
            await send_verification_message(update, context)
            return
        # Optional: allow free attempts here or ignore
        return

    text = update.message.text or update.message.caption
    if text and is_terabox_link(text):
        await process_terabox_links(update, context)
