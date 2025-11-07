"""
Terabox Handlers - WITH CONCURRENT PROCESSING + RESOLVER FALLBACK + RELAXED VERIFICATION
One-active-leech-per-user + Cancel button + /cancel + Global concurrency cap + Split > 300MB.
"""

import logging
import re
import os
import asyncio
from typing import Optional, Dict

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

URL_PATTERN = re.compile(r'https?://[^\s<>"\']+')

# ===== in-memory single-leech + cancel + global cap =====
ACTIVE_TASKS: Dict[int, asyncio.Task] = {}
CANCEL_FLAGS: Dict[int, asyncio.Event] = {}

MAX_CONCURRENT_LEECH = int(os.getenv("MAX_CONCURRENT_LEECH", "2"))
LEECH_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_LEECH)

async def resolve_canonical_terabox_url(message_text: str) -> Optional[str]:
    m = TERABOX_PATTERN.search(message_text)
    if m:
        return m.group(0)

    u = URL_PATTERN.search(message_text)
    if not u:
        return None
    raw_url = u.group(0)

    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(raw_url, allow_redirects=True) as resp:
                final_url = str(resp.url)
                mm = TERABOX_PATTERN.search(final_url)
                if mm:
                    return mm.group(0)

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
    status_msg,
    cancel_event: asyncio.Event
):
    await LEECH_SEMAPHORE.acquire()
    user = update.effective_user
    file_path = None

    try:
        logger.info(f"📋 [User {user_id}] Extracting file info from: {terabox_url}")
        await status_msg.edit_text(
            "📋 **Fetching file information...**\n\nUse /cancel to stop.",
            parse_mode='Markdown'
        )

        result = extract_terabox_data(terabox_url)
        if not result or "files" not in result or not result["files"]:
            raise Exception("No files found in Terabox link")

        file_info = result["files"][0]
        filename = file_info.get('name', 'Unknown')
        size_readable = file_info.get('size', 'Unknown')
        download_url = file_info.get('download_url', '')

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

        increment_leech_attempts(user_id)
        user_data = get_user_data(user_id)
        used_attempts = user_data.get("leech_attempts", 0)
        is_verified = user_data.get("is_verified", False)

        if not download_url:
            await status_msg.edit_text("❌ **Failed to get download link.**", parse_mode='Markdown')
            return

        max_size = 2 * 1024 * 1024 * 1024
        if file_size and file_size > max_size:
            await status_msg.edit_text(
                f"❌ **File too large!**\n\n📊 **Size:** {size_readable}\n📊 **Max:** 2GB",
                parse_mode='Markdown'
            )
            return

        await status_msg.edit_text(
            f"📁 **File Found!**\n\n"
            f"📝 `{filename}`\n"
            f"📊 {size_readable}\n"
            f"🔢 Attempt #{used_attempts}\n\n"
            f"⬇️ **Downloading...**\n\nUse /cancel to stop.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🛑 Cancel Leech", callback_data=f"cancel_leech:{user_id}")]]
            ),
            parse_mode='Markdown'
        )

        SPLIT_THRESHOLD_BYTES = 300 * 1024 * 1024
        split_enabled = bool(file_size and file_size >= SPLIT_THRESHOLD_BYTES)
        SPLIT_PART_MB_DEFAULT = 200

        file_result = await download_file(
            download_url,
            filename,
            status_msg,
            referer=terabox_url,
            cancel_event=cancel_event,
            split_enabled=split_enabled,
            split_part_mb=SPLIT_PART_MB_DEFAULT
        )

        if isinstance(file_result, list):
            total_parts = len(file_result)
            await status_msg.edit_text(
                f"📤 **Uploading {total_parts} parts to Telegram...**",
                parse_mode='Markdown'
            )
            part_no = 1
            last_sent = None
            for part_path in file_result:
                part_caption = (
                    f"📄 **{filename}**\n"
                    f"🧩 Part {part_no}/{total_parts}\n"
                    f"🤖 @{context.bot.username}"
                )
                last_sent = await upload_to_telegram(update, context, part_path, part_caption)
                cleanup_file(part_path)
                part_no += 1
            sent_message = last_sent
        else:
            file_path = file_result
            caption = f"📄 **{filename}**\n📊 {size_readable}\n🤖 @{context.bot.username}"
            sent_message = await upload_to_telegram(update, context, file_path, caption)
            cleanup_file(file_path)

        if AUTO_FORWARD_ENABLED and sent_message:
            try:
                await forward_file_to_channel(context, user, sent_message)
                logger.info(f"✅ [User {user_id}] File forwarded to backup channel")
            except Exception as e:
                logger.error(f"⚠️ [User {user_id}] Forward failed: {e}")

        try:
            await status_msg.delete()
        except:
            pass

        if not is_verified and used_attempts < FREE_LEECH_LIMIT:
            remaining = FREE_LEECH_LIMIT - used_attempts
            await update.message.reply_text(
                f"✅ **File uploaded!**\n\n⏳ **Remaining free leeches:** {remaining}/{FREE_LEECH_LIMIT}",
                parse_mode='Markdown'
            )
        elif used_attempts >= FREE_LEECH_LIMIT and not is_verified:
            token = generate_verify_token()
            set_verification_token(user_id, token)
            verify_link = generate_monetized_verification_link(context.bot.username, token)
            keyboard = [
                [InlineKeyboardButton("✅ VERIFY FOR LEECH", url=verify_link)],
                [InlineKeyboardButton("📺 HOW TO VERIFY?", url="https://t.me/Sr_Movie_Links/52")],
                [InlineKeyboardButton("💬 ANY HELP", url="https://t.me/Siva9789")]
            ]
            await update.message.reply_text(
                "🎬 **Leech Verification Required**\n\n"
                f"You've used **{used_attempts}\\{FREE_LEECH_LIMIT} free leeches!**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("✅ **File uploaded!**\n♾️ **Status:** Verified User", parse_mode='Markdown')

    except Exception as e:
        logger.error(f"❌ [User {user_id}] Error: {e}")
        if file_path:
            cleanup_file(file_path)
        try:
            await status_msg.edit_text(f"❌ **Error:**\n`{str(e)}`", parse_mode='Markdown')
        except:
            pass
    finally:
        ACTIVE_TASKS.pop(user_id, None)
        ev = CANCEL_FLAGS.pop(user_id, None)
        if ev:
            ev.clear()
        try:
            LEECH_SEMAPHORE.release()
        except:
            pass

async def cancel_leech_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        _, uid_str = q.data.split(":")
        target_uid = int(uid_str)
    except:
        await q.edit_message_text("❌ Invalid cancel request")
        return

    user_id = q.from_user.id
    if user_id != target_uid:
        await q.edit_message_text("❌ You can cancel only your own leech")
        return

    ev = CANCEL_FLAGS.get(user_id)
    if not ev:
        await q.edit_message_text("ℹ️ No active leech to cancel")
        return

    ev.set()
    await q.edit_message_text("🛑 Leech cancelled. You can start a new leech now.")

async def cancel_current_leech(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ev = CANCEL_FLAGS.get(user_id)
    if not ev:
        await update.message.reply_text("ℹ️ No active leech to cancel.")
        return
    ev.set()
    await update.message.reply_text("🛑 Leech cancelled. You can start a new leech now.")

async def handle_terabox_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text or ""

    logger.info(f"📩 [User {user_id}] incoming text: {message_text[:150]}")

    terabox_url = None
    m = TERABOX_PATTERN.search(message_text)
    if m:
        terabox_url = m.group(0)
    elif USE_TBX_RESOLVER:
        terabox_url = await resolve_canonical_terabox_url(message_text)

    logger.info(f"🔎 [User {user_id}] matched URL: {terabox_url or 'None'}")
    if not terabox_url:
        return False

    if user_id in ACTIVE_TASKS and not ACTIVE_TASKS[user_id].done():
        kb = [[InlineKeyboardButton("🛑 Cancel Leech", callback_data=f"cancel_leech:{user_id}")]]
        await update.message.reply_text(
            "⚠️ You already have one leech in progress.\nFinish or cancel it before starting another.",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return True

    if not can_user_leech(user_id):
        if needs_verification(user_id):
            user_data = get_user_data(user_id)
            used_attempts = user_data.get("leech_attempts", 0)
            token = generate_verify_token()
            set_verification_token(user_id, token)
            verify_link = generate_monetized_verification_link(context.bot.username, token)
            keyboard = [
                [InlineKeyboardButton("✅ VERIFY FOR LEECH", url=verify_link)],
                [InlineKeyboardButton("📺 HOW TO VERIFY?", url="https://t.me/Sr_Movie_Links/52")],
                [InlineKeyboardButton("💬 ANY HELP", url="https://t.me/Siva9789")]
            ]
            await update.message.reply_text(
                "🎬 **Leech Verification Required**\n\n"
                f"You've used **{used_attempts}\\{FREE_LEECH_LIMIT} free leeches!**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return True
        else:
            await update.message.reply_text("❌ **Error checking account.**\nUse /start", parse_mode='Markdown')
            return True

    status_msg = await update.message.reply_text(
        "🔍 **Processing...**\n\nUse /cancel to stop.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🛑 Cancel Leech", callback_data=f"cancel_leech:{user_id}")]]
        ),
        parse_mode='Markdown'
    )

    cancel_event = asyncio.Event()
    CANCEL_FLAGS[user_id] = cancel_event

    task = asyncio.create_task(
        process_terabox_download(update, context, terabox_url, user_id, status_msg, cancel_event)
    )
    ACTIVE_TASKS[user_id] = task
    return True
    
