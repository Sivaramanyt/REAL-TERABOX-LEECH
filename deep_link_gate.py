# deep_link_gate.py
"""
Deep-link gate for auto-post clicks:
- 3 free deliveries per user per day (configurable)
- On 4th+, require monetized verification
- On success, unlock unlimited deep-link deliveries (until expiry)
This file is self-contained and only uses public functions you already expose.
"""

import logging
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import (
    BACKUP_CHANNEL_ID,
    BOT_USERNAME,
    FREE_DEEPLINK_LIMIT,
    DEEP_LINK_VERIFY_TOKEN_TIMEOUT,
)

# Import only the DB helpers we need. We do not modify database.py.
from database import db, get_user_data

# Reuse existing verification helpers without touching verification.py
from verification import generate_verify_token, create_universal_shortlink

logger = logging.getLogger(__name__)

# --- Local collection shortcuts (no schema change to existing docs for other features)
users_collection = db["users"]

# Field names used for deep-link gating (kept separate from leech/video)
DL_ATTEMPTS = "deep_link_attempts"
DL_IS_VERIFIED = "is_deep_link_verified"
DL_VERIFY_TOKEN = "deep_link_verify_token"
DL_TOKEN_EXPIRY = "deep_link_token_expiry"
DL_VERIFY_EXPIRY = "deep_link_verify_expiry"
DL_LAST_RESET = "last_deep_link_reset"  # optional daily reset field

# --- Helpers

def _ensure_user_defaults(user_id: int):
    """Add deep-link fields to user doc if missing, without altering other logic."""
    now = datetime.utcnow()
    users_collection.update_one(
        {"user_id": user_id},
        {"$setOnInsert": {
            DL_ATTEMPTS: 0,
            DL_IS_VERIFIED: False,
            DL_VERIFY_TOKEN: None,
            DL_TOKEN_EXPIRY: None,
            DL_VERIFY_EXPIRY: None,
            DL_LAST_RESET: now
        }},
        upsert=True
    )

def _reset_if_new_day(user_id: int):
    """Simple UTC-day reset for the deep-link attempts, independent of your IST resets."""
    doc = users_collection.find_one({"user_id": user_id}, {DL_LAST_RESET: 1})
    now = datetime.utcnow()
    if not doc or not doc.get(DL_LAST_RESET):
        users_collection.update_one({"user_id": user_id}, {"$set": {DL_LAST_RESET: now}})
        return
    last = doc[DL_LAST_RESET]
    if last.date() != now.date():
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {DL_ATTEMPTS: 0, DL_LAST_RESET: now}}
        )

def can_user_get_deep_link(user_id: int) -> bool:
    _ensure_user_defaults(user_id)
    _reset_if_new_day(user_id)
    u = users_collection.find_one({"user_id": user_id}, {DL_IS_VERIFIED: 1, DL_ATTEMPTS: 1})
    if not u:
        return True
    if u.get(DL_IS_VERIFIED, False):
        return True
    return int(u.get(DL_ATTEMPTS, 0)) < FREE_DEEPLINK_LIMIT

def increment_deep_link_attempts(user_id: int):
    _ensure_user_defaults(user_id)
    _reset_if_new_day(user_id)
    users_collection.update_one({"user_id": user_id}, {"$inc": {DL_ATTEMPTS: 1}})

def needs_deep_link_verification(user_id: int) -> bool:
    _ensure_user_defaults(user_id)
    _reset_if_new_day(user_id)
    u = users_collection.find_one({"user_id": user_id}, {DL_IS_VERIFIED: 1, DL_ATTEMPTS: 1})
    if not u:
        return False
    return (not u.get(DL_IS_VERIFIED, False)) and (int(u.get(DL_ATTEMPTS, 0)) >= FREE_DEEPLINK_LIMIT)

def set_deep_link_verification_token(user_id: int, token: str, expiry_dt: datetime):
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {DL_VERIFY_TOKEN: token, DL_TOKEN_EXPIRY: expiry_dt}}
    )

def verify_deep_link_token(token: str) -> int | None:
    now = datetime.utcnow()
    u = users_collection.find_one(
        {DL_VERIFY_TOKEN: token, DL_TOKEN_EXPIRY: {"$gt": now}},
        {"_id": 1, "user_id": 1, DL_TOKEN_EXPIRY: 1}
    )
    if not u:
        return None
    users_collection.update_one(
        {"_id": u["_id"]},
        {"$set": {DL_IS_VERIFIED: True, DL_VERIFY_EXPIRY: u[DL_TOKEN_EXPIRY]},
         "$unset": {DL_VERIFY_TOKEN: "", DL_TOKEN_EXPIRY: ""}}
    )
    return int(u["user_id"])

def build_deep_link_for_message(message_id: int) -> str:
    return f"https://t.me/{BOT_USERNAME}?start=v_{message_id}"

def build_deep_link_verification_link(token: str) -> str:
    tg = f"https://t.me/{BOT_USERNAME}?start=dl_{token}"
    short = create_universal_shortlink(tg)
    return short or tg

# --- Entry points to use in handlers and auto-post

async def deliver_or_gate_deeplink(update, context, msg_id: int):
    """
    Called from start v_<msg_id> branch:
    - If under free limit or verified: copy original and increment attempts
    - Else: send monetized verification button
    """
    user_id = update.effective_user.id
    _ensure_user_defaults(user_id)

    if can_user_get_deep_link(user_id):
        try:
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=BACKUP_CHANNEL_ID,
                message_id=msg_id
            )
            increment_deep_link_attempts(user_id)
            u = get_user_data(user_id) or {}
            used = u.get("deep_link_attempts", 0)
            if not u.get("is_deep_link_verified", False) and used < FREE_DEEPLINK_LIMIT:
                remain = FREE_DEEPLINK_LIMIT - used
                await update.message.reply_text(
                    f"✅ Delivered via channel link.\n⏳ Free remaining: {remain}/{FREE_DEEPLINK_LIMIT}"
                )
        except Exception as e:
            logger.error(f"Deep-link copy error: {e}")
            await update.message.reply_text("❌ Could not deliver the file. Please try again.")
        return

    # Free limit exceeded -> send verification link
    tok = generate_verify_token()
    exp = datetime.utcnow().timestamp() + DEEP_LINK_VERIFY_TOKEN_TIMEOUT
    from datetime import timedelta
    expiry_dt = datetime.utcnow() + timedelta(seconds=DEEP_LINK_VERIFY_TOKEN_TIMEOUT)
    set_deep_link_verification_token(user_id, tok, expiry_dt)
    vlink = build_deep_link_verification_link(tok)
    await update.message.reply_text(
        "🔒 Free limit reached for channel links.\nComplete verification to continue:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Verify Now", url=vlink)]])
    )

async def complete_deeplink_verification(update, context, token: str):
    user_id = verify_deep_link_token(token)
    if user_id:
        await update.message.reply_text("✅ Verification successful! Unlimited channel-link downloads enabled.")
    else:
        await update.message.reply_text("❌ Verification failed or expired. Please try again.")
