"""
Terabox Handlers - WITH CONCURRENT PROCESSING + RESOLVER FALLBACK + RELAXED VERIFICATION

Multiple users can download/upload simultaneously.
"""

import logging
import re
import asyncio
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    can_user_leech, increment_leech_attempts, get_user_data,
    needs_verification, set_verification_token
)
from auto_forward import forward_file_to_channel
from config import (
    FREE_LEECH_LIMIT, AUTO_FORWARD_ENABLED, BOT_USERNAME
)
# Optional toggle from config; default to True if missing
try:
    from config import USE_TBX_RESOLVER  # bool
except Exception:
    USE_TBX_RESOLVER = True

from verification import generate_verify_token, generate_monetized_verification_link

# Import terabox modules
from terabox_api import extract_terabox_data, format_size
from terabox_downloader import download_file, upload_to_telegram, cleanup_file

# Async HTTP client for resolver fallback
import aiohttp
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ===== Broadened pattern to include mirrors like terasharefile.com =====
TERABOX_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:'
    r'terabox|teraboxapp|1024tera|4funbox|teraboxshare|teraboxurl|1024terabox|'
    r'terafileshare|teraboxlink|terasharelink|terasharefile|terashare'
    r')\.(?:com|app|fun)'
    r'/(?:s/|share/|wap/share/filelist\?surl=|.+?s/)[^\s<>"]+',
    re.IGNORECASE
)

# Generic URL finder used by resolver
URL_PATTERN = re.compile(r'https?://[^\s<>"\']+')

async def resolve_canonical_terabox_url(message_text: str) -> Optional[str]:
    """
    Second-line defense: follow redirects and parse HTML to recover a canonical Terabox link.
    Returns a Terabox /s/... URL or None if nothing valid found.
    """
    # First try the direct matcher
    m = TERABOX_PATTERN.search(message_text)
    if m:
        return m.group(0)

    # Grab the first URL-looking token if any
    u = URL_PATTERN.search(message_text)
    if not u:
        return None
    raw_url = u.group(0)

    # Follow redirects and scan final HTML for a Terabox link
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Use GET to support sites that block HEAD; allow redirects
            async with session.get(raw_url, allow_redirects=True) as resp:
                final_url = str(resp.url)

                # If redirects already landed on a Terabox URL, extract it
                mm = TERABOX_PATTERN.search(final_url)
                if mm:
                    return mm.group(0)

                # If HTML page, scan body for an embedded Terabox link (meta-refresh, anchors, JS)
                ctype = resp.headers.get("Content-Type", "")
                if "text/html" in ctype:
                    body = await resp.text(errors="ignore")
                    mx = re.search(r'(https?://[^"\'><\s]*terabox[^"\'><\s]+)', body, re.IGNORECASE)
                    if mx:
                        m2 = TERABOX_PATTERN.search(mx.group(0))
                        if m2:
                            return m2.group(0)
    except Exception as e:
        logger.warning(f"resolver fallback failed: {e}")

    return None


async def process_terabox_download(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    terabox_url: str,
    user_id: int,
    status_msg
):
    """
    Background task for downloading and uploading
    This runs independently for each user.
    """
    user = update.effective_user
    file_path = None

    try:
        # Step 1: Extract file information
        logger.info(f"📋 [User {user_id}] Extracting file info from: {terabox_url}")
        await status_msg.edit_text("📋 **Fetching file information...**", parse_mode='Markdown')

        result = extract_terabox_data(terabox_url)

        # Expecting {"files": [...]} from terabox_api; pick first
        if not result or "files" not in result or not result["files"]:
            raise Exception("No files found in Terabox link")

        file_info = result["files"][0]
        filename = file_info.get('name', 'Unknown')
        size_readable = file_info.get('size', 'Unknown')
        download_url = file_info.get('download_url', '')

        # Try to parse size to bytes for validation (best-effort)
        file_size = 0
        try:
            if isinstance(size_readable, str):
                s = size_readable.strip().upper()
                if s.endswith('MB'):
                    file_size = int(float(s.replace('MB', '').strip()) * 1024 * 1024)
                elif s.endswith('GB'):
                    file_size = int(float(s.replace('GB', '').strip()) * 1024 * 1024 * 1024)
                elif s.endswith('KB'):
                    file_size = int(float(s.replace('KB', '').strip()) * 1024)
        except:
            pass

        # Count attempts now (so UI shows correct number even if user cancels later)
        increment_leech_attempts(user_id)
        user_data = get_user_data(user_id)
        used_attempts = user_data.get("leech_attempts", 0)
        is_verified = user_data.get("is_verified", False)

        logger.info(f"✅ [User {user_id}] File identified: {filename} - {size_readable}")

        if not download_url:
            await status_msg.edit_text("❌ **Failed to get download link.**", parse_mode='Markdown')
            return

        # Basic size limit (optional; align with your uploader limits)
        max_size = 2 * 1024 * 1024 * 1024  # 2 GB
        if file_size and file_size > max_size:
            await status_msg.edit_text(
                f"❌ **File too large!**\n\n"
                f"📊 **Size:** {size_readable}\n"
                f"📊 **Max:** 2GB",
                parse_mode='Markdown'
            )
            return

        # Show info
        await status_msg.edit_text(
            f"📁 **File Found!**\n\n"
            f"📝 `{filename}`\n"
            f"📊 {size_readable}\n"
            f"🔢 Attempt #{used_attempts}\n\n"
            f"⬇️ **Downloading...**",
            parse_mode='Markdown'
        )

        # Step 2: Download
        logger.info(f"⬇️ [User {user_id}] Starting download")
        file_path = await download_file(download_url, filename, status_msg, referer=terabox_url)
        logger.info(f"✅ [User {user_id}] Download complete -> {file_path}")

        # Step 3: Upload
        await status_msg.edit_text("📤 **Uploading to Telegram...**", parse_mode='Markdown')
        caption = f"📄 **{filename}**\n📊 {size_readable}\n🤖 @{context.bot.username}"
        sent_message = await upload_to_telegram(update, context, file_path, caption)
        logger.info(f"✅ [User {user_id}] Upload complete")

        # Step 4: Auto-forward if enabled
        if AUTO_FORWARD_ENABLED and sent_message:
            try:
                await forward_file_to_channel(context, user, sent_message)
                logger.info(f"✅ [User {user_id}] File forwarded to backup channel")
            except Exception as e:
                logger.error(f"⚠️ [User {user_id}] Forward failed: {e}")

        # Step 5: Cleanup
        cleanup_file(file_path)
        file_path = None
        try:
            await status_msg.delete()
        except:
            pass

        # Step 6: Completion / verification prompts
        try:
            if not is_verified and used_attempts < FREE_LEECH_LIMIT:
                remaining = FREE_LEECH_LIMIT - used_attempts
                await update.message.reply_text(
                    f"✅ **File uploaded!**\n\n"
                    f"⏳ **Remaining free leeches:** {remaining}/{FREE_LEECH_LIMIT}",
                    parse_mode='Markdown'
                )

            elif used_attempts >= FREE_LEECH_LIMIT and not is_verified:
                # Ask for leech verification after free limit
                token = generate_verify_token()
                set_verification_token(user_id, token)
                bot_username = context.bot.username
                verify_link = generate_monetized_verification_link(bot_username, token)

                message = (
                    "🎬 **Leech Verification Required**\n\n"
                    f"You've used **{used_attempts}\\{FREE_LEECH_LIMIT} free leeches!**\n\n"
                    "To continue leeching Terabox files:\n\n"
                    "🔹 Click \"✅ Verify for Leech\" below\n"
                    "🔹 Complete the verification\n"
                    "🔹 Return and send Terabox link\n\n"
                    "**After verification:**\n"
                    "♾️ Unlimited Terabox leeching\n\n"
                    "**Note:** This is separate from video verification."
                )

                keyboard = [
                    [InlineKeyboardButton("✅ VERIFY FOR LEECH", url=verify_link)],
                    [InlineKeyboardButton("📺 HOW TO VERIFY?", url="https://t.me/Sr_Movie_Links/52")],
                    [InlineKeyboardButton("💬 ANY HELP", url="https://t.me/Siva9789")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

            else:
                # Verified user
                await update.message.reply_text(
                    "✅ **File uploaded!**\n♾️ **Status:** Verified User",
                    parse_mode='Markdown'
                )

        except Exception as e:
            logger.error(f"❌ [User {user_id}] Error sending completion message: {e}")
            try:
                await update.message.reply_text("✅ **File uploaded!**", parse_mode='Markdown')
            except:
                pass

    except Exception as e:
        logger.error(f"❌ [User {user_id}] Error: {e}")
        if file_path:
            cleanup_file(file_path)
        try:
            await status_msg.edit_text(f"❌ **Error:**\n`{str(e)}`", parse_mode='Markdown')
        except:
            pass


async def handle_terabox_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main handler - Creates background task for each user.
    Return True if the message was a Terabox link handled here, else False
    (so the router can fall back to other flows).
    """
    user_id = update.effective_user.id
    message_text = update.message.text or ""

    # Log incoming text (first 150 chars) for debugging detections
    logger.info(f"📩 [User {user_id}] incoming text: {message_text[:150]}")

    # First try direct regex, then optional resolver fallback
    terabox_url = None
    m = TERABOX_PATTERN.search(message_text)
    if m:
        terabox_url = m.group(0)
    elif USE_TBX_RESOLVER:
        terabox_url = await resolve_canonical_terabox_url(message_text)

    logger.info(f"🔎 [User {user_id}] matched URL: {terabox_url or 'None'}")

    if not terabox_url:
        # Not a Terabox-related link; let router continue
        return False

    # Only block when user truly cannot leech (after free limit / not verified)
    if not can_user_leech(user_id):
        if needs_verification(user_id):
            user_data = get_user_data(user_id)
            used_attempts = user_data.get("leech_attempts", 0)

            token = generate_verify_token()
            set_verification_token(user_id, token)
            bot_username = context.bot.username
            verify_link = generate_monetized_verification_link(bot_username, token)

            message = (
                "🎬 **Leech Verification Required**\n\n"
                f"You've used **{used_attempts}\\{FREE_LEECH_LIMIT} free leeches!**\n\n"
                "To continue leeching Terabox files:\n\n"
                "🔹 Click \"✅ Verify for Leech\" below\n"
                "🔹 Complete the verification\n"
                "🔹 Return and send Terabox link\n\n"
                "**After verification:**\n"
                "♾️ Unlimited Terabox leeching\n\n"
                "**Note:** This is separate from video verification."
            )

            keyboard = [
                [InlineKeyboardButton("✅ VERIFY FOR LEECH", url=verify_link)],
                [InlineKeyboardButton("📺 HOW TO VERIFY?", url="https://t.me/Sr_Movie_Links/52")],
                [InlineKeyboardButton("💬 ANY HELP", url="https://t.me/Siva9789")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            return True
        else:
            await update.message.reply_text("❌ **Error checking account.**\nUse /start", parse_mode='Markdown')
            return True

    # Send initial status and spawn background task
    status_msg = await update.message.reply_text("🔍 **Processing...**", parse_mode='Markdown')

    asyncio.create_task(
        process_terabox_download(update, context, terabox_url, user_id, status_msg)
    )

    # Return immediately - do not block on long download
    return True
