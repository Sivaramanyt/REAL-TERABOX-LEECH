"""
Database - WITH DAILY RESET SYSTEM (Resets at 12:00 AM IST)
Uses MONGODB_URL to match your config.py
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from typing import Optional, Dict

# Setup logging
logger = logging.getLogger(__name__)

# MongoDB setup - Using MONGODB_URL to match config.py
MONGODB_URL = os.getenv("MONGODB_URL")
if not MONGODB_URL:
    logger.error("❌ MONGODB_URL not found in environment variables!")
    raise ValueError("MONGODB_URL is required")

client = MongoClient(MONGODB_URL)
db = client["terabox_bot"]
users_collection = db["users"]

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# Import config values at module level
try:
    from config import (
        FREE_VIDEO_LIMIT,
        FREE_LEECH_LIMIT,
        VERIFY_TOKEN_TIMEOUT,
        VIDEO_VERIFY_TOKEN_TIMEOUT
    )
except ImportError as e:
    logger.error(f"❌ Config import error: {e}")
    FREE_VIDEO_LIMIT = 3
    FREE_LEECH_LIMIT = 3
    VERIFY_TOKEN_TIMEOUT = 604800
    VIDEO_VERIFY_TOKEN_TIMEOUT = 604800

# Create indexes
try:
    existing_indexes = users_collection.list_indexes()
    index_names = [index['name'] for index in existing_indexes]
    
    if 'user_id_1' not in index_names:
        users_collection.create_index("user_id", unique=True)
        logger.info("✅ Created index on user_id")
except Exception as e:
    logger.warning(f"⚠️ Index creation skipped: {e}")

def get_today_start() -> datetime:
    """Get today's 12:00 AM IST"""
    now_ist = datetime.now(IST)
    return now_ist.replace(hour=0, minute=0, second=0, microsecond=0)

def should_reset_daily_limit(user_data: Dict, field_name: str) -> bool:
    """Check if daily limit should be reset"""
    last_reset = user_data.get(field_name)
    if not last_reset:
        return True
    if last_reset.tzinfo is None:
        last_reset = last_reset.replace(tzinfo=IST)
    return last_reset < get_today_start()

def reset_daily_attempts_if_needed(user_id: int) -> None:
    """Reset daily attempts if new day"""
    user_data = get_user_data(user_id)
    if not user_data:
        return
    
    updates = {}
    now_ist = datetime.now(IST)
    
    if should_reset_daily_limit(user_data, 'last_video_reset'):
        updates['video_attempts'] = 0
        updates['last_video_reset'] = now_ist
        logger.info(f"🔄 Reset video attempts for user {user_id}")
    
    if should_reset_daily_limit(user_data, 'last_leech_reset'):
        updates['leech_attempts'] = 0
        updates['last_leech_reset'] = now_ist
        logger.info(f"🔄 Reset leech attempts for user {user_id}")
    
    if updates:
        users_collection.update_one({"user_id": user_id}, {"$set": updates})

def get_user_data(user_id: int) -> Optional[Dict]:
    """Get user data, create if doesn't exist"""
    user = users_collection.find_one({"user_id": user_id})
    
    if not user:
        now_ist = datetime.now(IST)
        new_user = {
            "user_id": user_id,
            "joined_date": now_ist,
            "leech_attempts": 0,
            "is_verified": False,
            "verify_token": None,
            "token_expiry": None,
            "verify_expiry": None,
            "last_leech_reset": now_ist,
            "video_attempts": 0,
            "is_video_verified": False,
            "video_verify_token": None,
            "video_token_expiry": None,
            "video_verify_expiry": None,
            "last_video_reset": now_ist
        }
        users_collection.insert_one(new_user)
        logger.info(f"✅ Created new user: {user_id}")
        return new_user
    return user

def can_user_watch_video(user_id: int) -> bool:
    """Check if user can watch videos"""
    reset_daily_attempts_if_needed(user_id)
    user_data = get_user_data(user_id)
    if not user_data:
        return False
    
    if user_data.get("is_video_verified"):
        video_verify_expiry = user_data.get("video_verify_expiry")
        if video_verify_expiry:
            now_ist = datetime.now(IST)
            if video_verify_expiry.tzinfo is None:
                video_verify_expiry = video_verify_expiry.replace(tzinfo=IST)
            if now_ist < video_verify_expiry:
                return True
            else:
                users_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {"is_video_verified": False, "video_verify_expiry": None}}
                )
    
    return user_data.get("video_attempts", 0) < FREE_VIDEO_LIMIT

def can_user_leech(user_id: int) -> bool:
    """Check if user can leech files"""
    reset_daily_attempts_if_needed(user_id)
    user_data = get_user_data(user_id)
    if not user_data:
        return False
    
    if user_data.get("is_verified"):
        verify_expiry = user_data.get("verify_expiry")
        if verify_expiry:
            now_ist = datetime.now(IST)
            if verify_expiry.tzinfo is None:
                verify_expiry = verify_expiry.replace(tzinfo=IST)
            if now_ist < verify_expiry:
                return True
            else:
                users_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {"is_verified": False, "verify_expiry": None}}
                )
    
    return user_data.get("leech_attempts", 0) < FREE_LEECH_LIMIT

def increment_video_attempts(user_id: int) -> bool:
    """Increment video attempts"""
    try:
        reset_daily_attempts_if_needed(user_id)
        result = users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"video_attempts": 1}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

def increment_leech_attempts(user_id: int) -> bool:
    """Increment leech attempts"""
    try:
        reset_daily_attempts_if_needed(user_id)
        result = users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"leech_attempts": 1}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

def needs_video_verification(user_id: int) -> bool:
    """Check if needs video verification"""
    reset_daily_attempts_if_needed(user_id)
    user_data = get_user_data(user_id)
    if not user_data:
        return False
    
    if user_data.get("is_video_verified"):
        video_verify_expiry = user_data.get("video_verify_expiry")
        if video_verify_expiry:
            now_ist = datetime.now(IST)
            if video_verify_expiry.tzinfo is None:
                video_verify_expiry = video_verify_expiry.replace(tzinfo=IST)
            if now_ist < video_verify_expiry:
                return False
    
    return user_data.get("video_attempts", 0) >= FREE_VIDEO_LIMIT

def needs_verification(user_id: int) -> bool:
    """Check if needs leech verification"""
    reset_daily_attempts_if_needed(user_id)
    user_data = get_user_data(user_id)
    if not user_data:
        return False
    
    if user_data.get("is_verified"):
        verify_expiry = user_data.get("verify_expiry")
        if verify_expiry:
            now_ist = datetime.now(IST)
            if verify_expiry.tzinfo is None:
                verify_expiry = verify_expiry.replace(tzinfo=IST)
            if now_ist < verify_expiry:
                return False
    
    return user_data.get("leech_attempts", 0) >= FREE_LEECH_LIMIT

def set_verification_token(user_id: int, token: str) -> bool:
    """Set verification token"""
    try:
        now_ist = datetime.now(IST)
        expiry = now_ist + timedelta(seconds=VERIFY_TOKEN_TIMEOUT)
        result = users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"verify_token": token, "token_expiry": expiry}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

def verify_token(token: str) -> Optional[int]:
    """Verify leech token"""
    try:
        now_ist = datetime.now(IST)
        user = users_collection.find_one({
            "verify_token": token,
            "token_expiry": {"$gt": now_ist}
        })
        if user:
            verify_expiry = now_ist + timedelta(seconds=VERIFY_TOKEN_TIMEOUT)
            users_collection.update_one(
                {"user_id": user["user_id"]},
                {"$set": {
                    "is_verified": True,
                    "verify_expiry": verify_expiry,
                    "verify_token": None,
                    "token_expiry": None
                }}
            )
            return user["user_id"]
        return None
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return None

def set_video_verification_token(user_id: int, token: str) -> bool:
    """Set video verification token"""
    try:
        now_ist = datetime.now(IST)
        expiry = now_ist + timedelta(seconds=VIDEO_VERIFY_TOKEN_TIMEOUT)
        result = users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"video_verify_token": token, "video_token_expiry": expiry}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

def verify_video_token(token: str) -> Optional[int]:
    """Verify video token"""
    try:
        now_ist = datetime.now(IST)
        user = users_collection.find_one({
            "video_verify_token": token,
            "video_token_expiry": {"$gt": now_ist}
        })
        if user:
            verify_expiry = now_ist + timedelta(seconds=VIDEO_VERIFY_TOKEN_TIMEOUT)
            users_collection.update_one(
                {"user_id": user["user_id"]},
                {"$set": {
                    "is_video_verified": True,
                    "video_verify_expiry": verify_expiry,
                    "video_verify_token": None,
                    "video_token_expiry": None
                }}
            )
            return user["user_id"]
        return None
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return None

def get_user_stats(user_id: int) -> Dict:
    """Get user statistics"""
    reset_daily_attempts_if_needed(user_id)
    user_data = get_user_data(user_id)
    if not user_data:
        return {}
    return {
        "leech_attempts": user_data.get("leech_attempts", 0),
        "video_attempts": user_data.get("video_attempts", 0),
        "is_verified": user_data.get("is_verified", False),
        "is_video_verified": user_data.get("is_video_verified", False),
        "joined_date": user_data.get("joined_date"),
        "last_leech_reset": user_data.get("last_leech_reset"),
        "last_video_reset": user_data.get("last_video_reset")
    }
    
