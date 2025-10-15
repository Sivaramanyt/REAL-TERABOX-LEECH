"""
Database - WITH DAILY RESET SYSTEM (Resets at 12:00 AM IST)
Users get 3 free videos + 3 free leeches EVERY DAY
"""

import os
import logging
from datetime import datetime, timedelta
from pymongo import MongoClient
from typing import Optional, Dict
import pytz

# Setup logging
logger = logging.getLogger(__name__)

# MongoDB setup
MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise ValueError("❌ MONGODB_URI not found in environment variables!")

client = MongoClient(MONGODB_URI)
db = client["terabox_bot"]
users_collection = db["users"]

# Timezone setup for IST
IST = pytz.timezone('Asia/Kolkata')

# Create indexes for better performance
try:
    existing_indexes = users_collection.list_indexes()
    index_names = [index['name'] for index in existing_indexes]
    
    if 'user_id_1' not in index_names:
        users_collection.create_index("user_id", unique=True)
        logger.info("✅ Created index on user_id")
    else:
        logger.info("ℹ️ Database already has 4 documents, skipping index creation")
except Exception as e:
    logger.warning(f"⚠️ Index creation skipped or failed: {e}")

def get_today_start() -> datetime:
    """Get today's 12:00 AM IST as datetime object"""
    now_ist = datetime.now(IST)
    today_start = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start

def should_reset_daily_limit(user_data: Dict, field_name: str) -> bool:
    """
    Check if daily limit should be reset
    Args:
        user_data: User document from database
        field_name: Either 'last_video_reset' or 'last_leech_reset'
    Returns:
        True if needs reset (new day), False otherwise
    """
    last_reset = user_data.get(field_name)
    
    # If never reset before, need to reset
    if not last_reset:
        return True
    
    # Convert to IST timezone aware datetime
    if not last_reset.tzinfo:
        last_reset = IST.localize(last_reset)
    
    today_start = get_today_start()
    
    # If last reset was before today, need to reset
    return last_reset < today_start

def reset_daily_attempts_if_needed(user_id: int) -> None:
    """
    Check and reset daily attempts (videos + leeches) if it's a new day
    Automatically called before checking limits
    """
    user_data = get_user_data(user_id)
    if not user_data:
        return
    
    updates = {}
    now_ist = datetime.now(IST)
    
    # Check video attempts reset
    if should_reset_daily_limit(user_data, 'last_video_reset'):
        updates['video_attempts'] = 0
        updates['last_video_reset'] = now_ist
        logger.info(f"🔄 Reset video attempts for user {user_id}")
    
    # Check leech attempts reset
    if should_reset_daily_limit(user_data, 'last_leech_reset'):
        updates['leech_attempts'] = 0
        updates['last_leech_reset'] = now_ist
        logger.info(f"🔄 Reset leech attempts for user {user_id}")
    
    # Apply updates if any
    if updates:
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": updates}
        )

def get_user_data(user_id: int) -> Optional[Dict]:
    """Get user data, create if doesn't exist"""
    user = users_collection.find_one({"user_id": user_id})
    
    if not user:
        now_ist = datetime.now(IST)
        new_user = {
            "user_id": user_id,
            "joined_date": now_ist,
            # Leech system
            "leech_attempts": 0,
            "is_verified": False,
            "verify_token": None,
            "token_expiry": None,
            "verify_expiry": None,
            "last_leech_reset": now_ist,  # ✅ NEW: Track last leech reset
            # Video system
            "video_attempts": 0,
            "is_video_verified": False,
            "video_verify_token": None,
            "video_token_expiry": None,
            "video_verify_expiry": None,
            "last_video_reset": now_ist  # ✅ NEW: Track last video reset
        }
        users_collection.insert_one(new_user)
        logger.info(f"✅ Created new user: {user_id}")
        return new_user
    
    return user

def can_user_watch_video(user_id: int) -> bool:
    """
    Check if user can watch videos (with daily reset)
    Returns True if: verified OR within daily limit
    """
    # ✅ FIRST: Reset attempts if it's a new day
    reset_daily_attempts_if_needed(user_id)
    
    user_data = get_user_data(user_id)
    if not user_data:
        return False
    
    # Check verification status and expiry
    if user_data.get("is_video_verified"):
        video_verify_expiry = user_data.get("video_verify_expiry")
        if video_verify_expiry:
            now_ist = datetime.now(IST)
            if not video_verify_expiry.tzinfo:
                video_verify_expiry = IST.localize(video_verify_expiry)
            
            if now_ist < video_verify_expiry:
                return True
            else:
                # Verification expired, reset status
                users_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {"is_video_verified": False, "video_verify_expiry": None}}
                )
                logger.info(f"⏰ Video verification expired for user {user_id}")
    
    # Check daily free limit (3 videos per day)
    from config import FREE_VIDEO_LIMIT
    video_attempts = user_data.get("video_attempts", 0)
    
    return video_attempts < FREE_VIDEO_LIMIT

def can_user_leech(user_id: int) -> bool:
    """
    Check if user can leech files (with daily reset)
    Returns True if: verified OR within daily limit
    """
    # ✅ FIRST: Reset attempts if it's a new day
    reset_daily_attempts_if_needed(user_id)
    
    user_data = get_user_data(user_id)
    if not user_data:
        return False
    
    # Check verification status and expiry
    if user_data.get("is_verified"):
        verify_expiry = user_data.get("verify_expiry")
        if verify_expiry:
            now_ist = datetime.now(IST)
            if not verify_expiry.tzinfo:
                verify_expiry = IST.localize(verify_expiry)
            
            if now_ist < verify_expiry:
                return True
            else:
                # Verification expired, reset status
                users_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {"is_verified": False, "verify_expiry": None}}
                )
                logger.info(f"⏰ Leech verification expired for user {user_id}")
    
    # Check daily free limit (3 leeches per day)
    from config import FREE_LEECH_LIMIT
    leech_attempts = user_data.get("leech_attempts", 0)
    
    return leech_attempts < FREE_LEECH_LIMIT

def increment_video_attempts(user_id: int) -> bool:
    """Increment video watch attempts"""
    try:
        # Reset if needed before incrementing
        reset_daily_attempts_if_needed(user_id)
        
        result = users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"video_attempts": 1}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"❌ Error incrementing video attempts: {e}")
        return False

def increment_leech_attempts(user_id: int) -> bool:
    """Increment leech attempts"""
    try:
        # Reset if needed before incrementing
        reset_daily_attempts_if_needed(user_id)
        
        result = users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"leech_attempts": 1}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"❌ Error incrementing leech attempts: {e}")
        return False

def needs_video_verification(user_id: int) -> bool:
    """Check if user needs video verification (exceeded daily limit)"""
    # Reset if needed
    reset_daily_attempts_if_needed(user_id)
    
    user_data = get_user_data(user_id)
    if not user_data:
        return False
    
    # Check if verified and not expired
    if user_data.get("is_video_verified"):
        video_verify_expiry = user_data.get("video_verify_expiry")
        if video_verify_expiry:
            now_ist = datetime.now(IST)
            if not video_verify_expiry.tzinfo:
                video_verify_expiry = IST.localize(video_verify_expiry)
            if now_ist < video_verify_expiry:
                return False
    
    # Check if exceeded daily limit
    from config import FREE_VIDEO_LIMIT
    video_attempts = user_data.get("video_attempts", 0)
    return video_attempts >= FREE_VIDEO_LIMIT

def needs_verification(user_id: int) -> bool:
    """Check if user needs leech verification (exceeded daily limit)"""
    # Reset if needed
    reset_daily_attempts_if_needed(user_id)
    
    user_data = get_user_data(user_id)
    if not user_data:
        return False
    
    # Check if verified and not expired
    if user_data.get("is_verified"):
        verify_expiry = user_data.get("verify_expiry")
        if verify_expiry:
            now_ist = datetime.now(IST)
            if not verify_expiry.tzinfo:
                verify_expiry = IST.localize(verify_expiry)
            if now_ist < verify_expiry:
                return False
    
    # Check if exceeded daily limit
    from config import FREE_LEECH_LIMIT
    leech_attempts = user_data.get("leech_attempts", 0)
    return leech_attempts >= FREE_LEECH_LIMIT

# ===== REST OF THE FUNCTIONS STAY THE SAME =====
# (set_verification_token, verify_token, set_video_verification_token, verify_video_token, get_user_stats)

def set_verification_token(user_id: int, token: str) -> bool:
    """Set verification token for leech access"""
    try:
        from config import VERIFY_TOKEN_TIMEOUT
        now_ist = datetime.now(IST)
        expiry = now_ist + timedelta(seconds=VERIFY_TOKEN_TIMEOUT)
        
        result = users_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "verify_token": token,
                "token_expiry": expiry
            }}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"❌ Error setting verification token: {e}")
        return False

def verify_token(token: str) -> Optional[int]:
    """Verify leech token and grant access"""
    try:
        from config import VERIFY_TOKEN_TIMEOUT
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
            logger.info(f"✅ User {user['user_id']} verified for leeching (valid for 7 days)")
            return user["user_id"]
        
        return None
    except Exception as e:
        logger.error(f"❌ Error verifying token: {e}")
        return None

def set_video_verification_token(user_id: int, token: str) -> bool:
    """Set verification token for video access"""
    try:
        from config import VIDEO_VERIFY_TOKEN_TIMEOUT
        now_ist = datetime.now(IST)
        expiry = now_ist + timedelta(seconds=VIDEO_VERIFY_TOKEN_TIMEOUT)
        
        result = users_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "video_verify_token": token,
                "video_token_expiry": expiry
            }}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"❌ Error setting video verification token: {e}")
        return False

def verify_video_token(token: str) -> Optional[int]:
    """Verify video token and grant access"""
    try:
        from config import VIDEO_VERIFY_TOKEN_TIMEOUT
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
            logger.info(f"✅ User {user['user_id']} verified for videos (valid for 7 days)")
            return user["user_id"]
        
        return None
    except Exception as e:
        logger.error(f"❌ Error verifying video token: {e}")
        return None

def get_user_stats(user_id: int) -> Dict:
    """Get user statistics"""
    user_data = get_user_data(user_id)
    
    # Reset if needed before showing stats
    reset_daily_attempts_if_needed(user_id)
    
    # Refresh data after potential reset
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
    
