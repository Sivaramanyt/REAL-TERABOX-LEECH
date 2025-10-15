"""
Database operations for user tracking and verification - WITH EXPIRY
"""

import pymongo
import logging
from datetime import datetime, timedelta
from config import MONGODB_URL, DATABASE_NAME, FREE_LEECH_LIMIT, VERIFY_TOKEN_TIMEOUT

logger = logging.getLogger(__name__)

# MongoDB connection
client = pymongo.MongoClient(MONGODB_URL)
db = client[DATABASE_NAME]
users_collection = db.users

# ✅ NEW: Add get_db() function for random_videos.py
def get_db():
    """Return database instance for use in other modules"""
    return db

def init_db():
    """Initialize database and create indexes safely"""
    try:
        existing_docs = users_collection.count_documents({})
        if existing_docs > 0:
            logger.info(f"Database already has {existing_docs} documents, skipping index creation")
            return True  # ✅ FIXED: Return True instead of nothing
        
        try:
            users_collection.drop_indexes()
            logger.info("Dropped existing indexes")
        except Exception:
            pass
        
        try:
            users_collection.create_index("user_id", unique=True, sparse=True)
            users_collection.create_index("verify_token", sparse=True)
            logger.info("Database indexes created successfully")
        except pymongo.errors.DuplicateKeyError:
            logger.info("Index already exists (duplicate key error)")
        
        logger.info("✅ Database initialized successfully")
        return True  # ✅ FIXED: Return True on success
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False  # ✅ FIXED: Return False on error

def get_user_data(user_id):
    """Get user data or create new user"""
    try:
        user = users_collection.find_one({"user_id": user_id})
        if not user:
            new_user = {
                "user_id": user_id,
                "leech_attempts": 0,
                "is_verified": False,
                "verify_token": None,
                "token_expiry": None,
                "video_attempts": 0,
                "is_video_verified": False,
                "video_verify_token": None,
                "video_token_expiry": None,
                "created_at": datetime.utcnow()
            }
            users_collection.insert_one(new_user)
            return new_user
        return user
    except Exception as e:
        logger.error(f"Error getting user data: {e}")
        return None

def increment_leech_attempts(user_id):
    """Increment leech attempts"""
    try:
        users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"leech_attempts": 1}}
        )
        return True
    except Exception as e:
        logger.error(f"Error incrementing leech attempts: {e}")
        return False

def increment_video_attempts(user_id):
    """Increment video attempts"""
    try:
        users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"video_attempts": 1}}
        )
        return True
    except Exception as e:
        logger.error(f"Error incrementing video attempts: {e}")
        return False

def can_user_leech(user_id):
    """Check if user can leech"""
    user = get_user_data(user_id)
    if not user:
        return False
    
    if user.get("is_verified", False):
        if user.get("token_expiry"):
            if datetime.utcnow() < user.get("token_expiry"):
                return True
            else:
                users_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {"is_verified": False, "verify_token": None, "token_expiry": None}}
                )
                return False
        return True
    
    return user.get("leech_attempts", 0) < FREE_LEECH_LIMIT

def can_user_watch_video(user_id):
    """Check if user can watch videos"""
    from config import FREE_VIDEO_LIMIT
    user = get_user_data(user_id)
    if not user:
        return False
    
    if user.get("is_video_verified", False):
        if user.get("video_token_expiry"):
            if datetime.utcnow() < user.get("video_token_expiry"):
                return True
            else:
                users_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {"is_video_verified": False, "video_verify_token": None, "video_token_expiry": None}}
                )
                return False
        return True
    
    return user.get("video_attempts", 0) < FREE_VIDEO_LIMIT

def needs_verification(user_id):
    """Check if user needs verification for leech"""
    user = get_user_data(user_id)
    if not user:
        return False
    return user.get("leech_attempts", 0) >= FREE_LEECH_LIMIT and not user.get("is_verified", False)

def needs_video_verification(user_id):
    """Check if user needs video verification"""
    from config import FREE_VIDEO_LIMIT
    user = get_user_data(user_id)
    if not user:
        return False
    return user.get("video_attempts", 0) >= FREE_VIDEO_LIMIT and not user.get("is_video_verified", False)

def set_verification_token(user_id, token):
    """Set verification token with expiry"""
    try:
        expiry = datetime.utcnow() + timedelta(seconds=VERIFY_TOKEN_TIMEOUT)
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"verify_token": token, "token_expiry": expiry}}
        )
        return True
    except Exception as e:
        logger.error(f"Error setting verification token: {e}")
        return False

def set_video_verification_token(user_id, token):
    """Set video verification token with expiry"""
    try:
        from config import VIDEO_VERIFY_TOKEN_TIMEOUT
        expiry = datetime.utcnow() + timedelta(seconds=VIDEO_VERIFY_TOKEN_TIMEOUT)
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"video_verify_token": token, "video_token_expiry": expiry}}
        )
        return True
    except Exception as e:
        logger.error(f"Error setting video verification token: {e}")
        return False

def verify_token(token):
    """Verify token and mark user as verified"""
    try:
        user = users_collection.find_one({"verify_token": token})
        if not user:
            return None
        
        if user.get("token_expiry") and datetime.utcnow() > user.get("token_expiry"):
            return None
        
        users_collection.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"is_verified": True}}
        )
        return user["user_id"]
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return None

def verify_video_token(token):
    """Verify video token and mark user as video verified"""
    try:
        user = users_collection.find_one({"video_verify_token": token})
        if not user:
            return None
        
        if user.get("video_token_expiry") and datetime.utcnow() > user.get("video_token_expiry"):
            return None
        
        users_collection.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"is_video_verified": True}}
        )
        return user["user_id"]
    except Exception as e:
        logger.error(f"Error verifying video token: {e}")
        return None

def reset_user_verification(user_id):
    """Reset user verification status"""
    try:
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "leech_attempts": 0,
                "is_verified": False,
                "verify_token": None,
                "token_expiry": None
            }}
        )
        return True
    except Exception as e:
        logger.error(f"Error resetting verification: {e}")
        return False

def reset_video_verification(user_id):
    """Reset user video verification status"""
    try:
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "video_attempts": 0,
                "is_video_verified": False,
                "video_verify_token": None,
                "video_token_expiry": None
            }}
        )
        return True
    except Exception as e:
        logger.error(f"Error resetting video verification: {e}")
        return False

def get_user_stats(user_id):
    """Get user statistics"""
    user = get_user_data(user_id)
    if not user:
        return None
    return {
        "leech_attempts": user.get("leech_attempts", 0),
        "is_verified": user.get("is_verified", False),
        "video_attempts": user.get("video_attempts", 0),
        "is_video_verified": user.get("is_video_verified", False)
}
    
