"""
Terabox Handlers - WITH CONCURRENT PROCESSING + RESOLVER FALLBACK + RELAXED VERIFICATION + DIRECT LEECH + LULUSTREAM
One-active-leech-per-user + Cancel button + /cancel + Global concurrency cap + Split > 300MB + Direct fallback + LuluStream upload.
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

# 🆕 NEW: Import direct leech fallback
from terabox_direct import leech_terabox_direct, TERABOX_DIRECT_AVAILABLE

# 🆕 NEW: Import LuluStream integration
try:
    from adult_config import LULUSTREAM_API_KEY, ADULT_CHANNEL_ID
    from adult_automation import upload_to_lulustream
    LULUSTREAM_AVAILABLE = True
    logger.info("✅ LuluStream integration available")
except ImportError:
    LULUSTREAM_AVAILABLE = False
    LULUSTREAM_API_KEY = None
    ADULT_CHANNEL_ID = None
    logger.warning("⚠️ LuluStream integration not available")

# Async HTTP client for resolver fallback
import aiohttp

logger = logging.getLogger(__name__)

# ===== Broadened pattern to include mirrors like terasharefile.com =====
TERABOX_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:'
    r'terabox|teraboxapp|1024tera|4funbox|teraboxshare|teraboxurl|1024terabox|'
    r'terafileshare|teraboxlink|terasharelink|terasharefile|terashare|'
    r'freeterabox|momerybox'  # ADDED
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
    """Resolve redirects and extract canonical Terabox URL"""
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
                
                # Normalize mirror domains
                final_url = final_url.replace("://freeterabox.com/", "://www.terabox.com/")
                final_url = final_url.replace("://www.freeterabox.com/", "://www.terabox.com/")
                final_url = final_url.replace("://momerybox.com/", "://www.terabox.com/")
                final_url = final_url.replace("://www.momerybox.com/", "://www.terabox.com/")
                
                m = TERABOX_PATTERN.search(final_url)
                if m:
                    return m.group(0)
                
                # Check HTML body for embedded links
                ctype = resp.headers.get("Content-Type", "")
                if "text/html" in ctype:
                    body = await resp.text(errors="ignore")
                    mx = re.search(r'(https?://[^"\'><\s]*terabox[^"\'><\s]+)', body, re.IGNORECASE)
                    if mx:
                        m2 = TERABOX_PATTERN.search(mx.group(0))
                        if m2:
                            url_norm = m2.group(0)
                            # Normalize mirrors in fallback body path
                            url_norm = url_norm.replace("://freeterabox.com/", "://www.terabox.com/").replace("://www.freeterabox.com/", "://www.terabox.com/")
                            url_norm = url_norm.replace("://momerybox.com/", "://www.terabox.com/").replace("://www.momerybox.com/", "://www.terabox.com/")
                            return url_norm
    except Exception as e:
        logger.warning(f"resolver fallback failed: {e}")
    
    return None


# 🆕 NEW: Upload local file to LuluStream
async def upload_file_to_lulustream(file_path: str, title: str) -> Optional[str]:
    """
    Upload local video file to LuluStream
    Returns embed link if successful
    """
    
    if not LULUSTREAM_API_KEY:
        logger.warning("⚠️ LuluStream API key not configured")
        return None
    
    try:
        import requests
        
        logger.info(f"⬆️ Uploading to LuluStream: {title[:60]}...")
        
        # Upload file directly
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'video/mp4')}
            headers = {'Authorization': f'Bearer {LULUSTREAM_API_KEY}'}
            
            response = requests.post(
                'https://api.lulustream.com/upload',
                files=files,
                headers=headers,
                data={'title': title},
                timeout=1800  # 30 mins for large files
            )
        
        if response.status_code == 200:
            data = response.json()
            embed_link = data.get('embed_url') or data.get('url') or data.get('watch_url')
            logger.info(f"✅ LuluStream upload successful")
            return embed_link
        else:
            logger.error(f"❌ LuluStream upload failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ LuluStream upload error: {e}")
        return None


async def process_terabox_download(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    terabox_url: str,
    user_id: int,
    status_msg,
    cancel_event: asyncio.Event
):
    """Process Terabox download with API, fallback to direct method if API fails, then upload to LuluStream"""
    
    await LEECH_SEMAPHORE.acquire()
    user = update.effective_user
    file_path = None
    lulustream_link = None
    
    try:
        logger.info(f"📋 [User {user_id}] Extracting file info from: {terabox_url}")
        await status_msg.edit_text(
            "📋 **Fetching file information...**\n\nUse /cancel to stop.",
            parse_mode='Markdown'
        )
        
        # Try API extraction first
        result = extract_terabox_data(terabox_url)
        
        # 🆕 NEW: If API fails, try direct method
        if not result or "files" not in result or not result["files"]:
            logger.warning(f"⚠️ [User {user_id}] API extraction failed, trying direct method...")
            
            if TERABOX_DIRECT_AVAILABLE:
                await status_msg.edit_text(
                    "⚠️ **API failed, trying direct method...**\n\nThis may take a moment.",
                    parse_mode='Markdown'
                )
                
                # Use direct leech method
                success = await leech_terabox_direct(update, context, terabox_url)
                
                if success:
                    # Increment attempts for direct method too
                    increment_leech_attempts(user_id)
                    
                    # Handle auto-forward if needed
                    # Note: direct method already uploads, so we just handle verification messages
                    user_data = get_user_data(user_id)
                    used_attempts = user_data.get("leech_attempts", 0)
                    is_verified = user_data.get("is_verified", False)
                    
                    if not is_verified and used_attempts < FREE_LEECH_LIMIT:
                        remaining = FREE_LEECH_LIMIT - used_attempts
                        await update.message.reply_text(
                            f"✅ **File uploaded via direct method!**\n\n"
                            f"⏳ **Remaining free leeches:** {remaining}/{FREE_LEECH_LIMIT}",
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
                    
                    return  # Success via direct method
            
            # Both methods failed
            raise Exception("No files found in Terabox link (API and direct method failed)")
        
        # API succeeded, continue with normal flow
        file_info = result["files"][0]
        filename = file_info.get('name', 'Unknown')
        size_readable = file_info.get('size', 'Unknown')
        download_url = file_info.get('download_url', '')
        
        # Parse file size
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
        
        # Increment attempts
        increment_leech_attempts(user_id)
        user_data = get_user_data(user_id)
        used_attempts = user_data.get("leech_attempts", 0)
        is_verified = user_data.get("is_verified", False)
        
        if not download_url:
            await status_msg.edit_text("❌ **Failed to get download link.**", parse_mode='Markdown')
            return
        
        # Check file size limit
        max_size = 2 * 1024 * 1024 * 1024  # 2GB
        if file_size and file_size > max_size:
            await status_msg.edit_text(
                f"❌ **File too large!**\n\n📊 **Size:** {size_readable}\n📊 **Max:** 2GB",
                parse_mode='Markdown'
            )
            return
        
        # Show file info
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
        
        # Download file
        SPLIT_THRESHOLD_BYTES = 300 * 1024 * 1024  # 300MB
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
        
        # 🆕 NEW: Upload to LuluStream (for single files only, not split)
        if LULUSTREAM_AVAILABLE and not isinstance(file_result, list):
            await status_msg.edit_text(
                "⬆️ **Uploading to LuluStream...**\n\nThis may take a few minutes.",
                parse_mode='Markdown'
            )
            
            try:
                lulustream_link = await upload_file_to_lulustream(file_result, filename)
                
                if lulustream_link:
                    logger.info(f"✅ [User {user_id}] LuluStream upload successful")
                else:
                    logger.warning(f"⚠️ [User {user_id}] LuluStream upload failed")
            except Exception as e:
                logger.error(f"❌ [User {user_id}] LuluStream error: {e}")
        
        # Upload to Telegram
        if isinstance(file_result, list):
            # Split upload
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
            # Single file upload
            file_path = file_result
            caption = f"📄 **{filename}**\n📊 {size_readable}\n🤖 @{context.bot.username}"
            sent_message = await upload_to_telegram(update, context, file_path, caption)
            cleanup_file(file_path)
        
        # 🆕 NEW: Auto-forward to backup channel (storage)
        if AUTO_FORWARD_ENABLED and sent_message:
            try:
                await forward_file_to_channel(context, user, sent_message)
                logger.info(f"✅ [User {user_id}] File forwarded to backup channel")
            except Exception as e:
                logger.error(f"⚠️ [User {user_id}] Forward failed: {e}")
        
        # 🆕 NEW: Post to adult channel with LuluStream link
        if ADULT_CHANNEL_ID and sent_message:
            try:
                # Get thumbnail from sent message
                thumbnail_file_id = None
                if sent_message.video:
                    thumbnail_file_id = sent_message.video.thumbnail.file_id if sent_message.video.thumbnail else None
                elif sent_message.document:
                    thumbnail_file_id = sent_message.document.thumbnail.file_id if sent_message.document.thumbnail else None
                
                # Create caption with LuluStream link or bot link
                if lulustream_link:
                    # Use LuluStream link
                    post_caption = f"""
🔥 **{filename}**

📊 Size: {size_readable}

▶️ **Watch Online:** {lulustream_link}

💡 Click link to stream
🇮🇳 #Indian #Terabox #Adult
"""
                else:
                    # Fallback to bot deep link
                    bot_link = f"https://t.me/{BOT_USERNAME}?start=file_{sent_message.message_id}"
                    post_caption = f"""
🔥 **{filename}**

📊 Size: {size_readable}

▶️ **Watch Now:** {bot_link}

💡 Click to watch via bot
🇮🇳 #Indian #Terabox
"""
                
                # Post to adult channel
                if thumbnail_file_id:
                    await context.bot.send_photo(
                        chat_id=ADULT_CHANNEL_ID,
                        photo=thumbnail_file_id,
                        caption=post_caption,
                        parse_mode='Markdown'
                    )
                else:
                    await context.bot.send_message(
                        chat_id=ADULT_CHANNEL_ID,
                        text=post_caption,
                        parse_mode='Markdown'
                    )
                
                logger.info(f"✅ [User {user_id}] Posted to adult channel")
                
            except Exception as e:
                logger.error(f"⚠️ [User {user_id}] Adult channel post failed: {e}")
        
        # Delete status message
        try:
            await status_msg.delete()
        except:
            pass
        
        # Send completion message based on verification status
        completion_msg = "✅ **File uploaded"
        if lulustream_link:
            completion_msg += " & posted to channel with streaming link"
        completion_msg += "!**\n\n"
        
        if not is_verified and used_attempts < FREE_LEECH_LIMIT:
            remaining = FREE_LEECH_LIMIT - used_attempts
            await update.message.reply_text(
                completion_msg + f"⏳ **Remaining free leeches:** {remaining}/{FREE_LEECH_LIMIT}",
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
            await update.message.reply_text(
                completion_msg + "♾️ **Status:** Verified User",
                parse_mode='Markdown'
            )
        
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
    """Handle cancel button callback"""
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
    """Handle /cancel command"""
    user_id = update.effective_user.id
    ev = CANCEL_FLAGS.get(user_id)
    
    if not ev:
        await update.message.reply_text("ℹ️ No active leech to cancel.")
        return
    
    ev.set()
    await update.message.reply_text("🛑 Leech cancelled. You can start a new leech now.")


async def handle_terabox_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main handler for Terabox links"""
    user_id = update.effective_user.id
    message_text = update.message.text or ""
    
    logger.info(f"📩 [User {user_id}] incoming text: {message_text[:150]}")
    
    # Extract Terabox URL
    terabox_url = None
    m = TERABOX_PATTERN.search(message_text)
    
    if m:
        terabox_url = m.group(0)
    elif USE_TBX_RESOLVER:
        terabox_url = await resolve_canonical_terabox_url(message_text)
    
    logger.info(f"🔎 [User {user_id}] matched URL: {terabox_url or 'None'}")
    
    if not terabox_url:
        return False
    
    # Check if user already has active leech
    if user_id in ACTIVE_TASKS and not ACTIVE_TASKS[user_id].done():
        kb = [[InlineKeyboardButton("🛑 Cancel Leech", callback_data=f"cancel_leech:{user_id}")]]
        await update.message.reply_text(
            "⚠️ You already have one leech in progress.\nFinish or cancel it before starting another.",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        return True
    
    # Check user permissions
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
            await update.message.reply_text(
                "❌ **Error checking account.**\nUse /start",
                parse_mode='Markdown'
            )
            return True
    
    # Start processing
    status_msg = await update.message.reply_text(
        "🔍 **Processing...**\n\nUse /cancel to stop.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🛑 Cancel Leech", callback_data=f"cancel_leech:{user_id}")]]
        ),
        parse_mode='Markdown'
    )
    
    # Create cancel event
    cancel_event = asyncio.Event()
    CANCEL_FLAGS[user_id] = cancel_event
    
    # Create and track task
    task = asyncio.create_task(
        process_terabox_download(update, context, terabox_url, user_id, status_msg, cancel_event)
    )
    
    ACTIVE_TASKS[user_id] = task
    return True
 
