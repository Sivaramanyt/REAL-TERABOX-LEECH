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

def init_db():
    """Initialize database and create indexes safely"""
    try:
        existing_docs = users_collection.count_documents({})
        if existing_docs > 0:
            logger.info(f"Database already has {existing_docs} documents, skipping index creation")
            return
        
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
            logger.info("Indexes already exist, skipping creation")
        
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

def get_user_data(user_id):
    """Get or create user data"""
    try:
        user = users_collection.find_one({"user_id": user_id})
        if not user:
            user = {
                "user_id": user_id,
                "leech_attempts": 0,
                "is_verified": False,
                "verify_token": None,
                "token_expiry": None,
                "verify_expiry": None,
                "joined_date": datetime.utcnow(),  # ✅ FIXED: Use UTC
                "last_activity": datetime.utcnow(),  # ✅ FIXED: Use UTC
                "video_attempts": 0,
                "is_video_verified": False,
                "video_verify_token": None,
                "video_token_expiry": None,
                "video_verify_expiry": None
            }
            users_collection.insert_one(user)
            logger.info(f"New user created: {user_id}")
        return user
    except Exception as e:
        logger.error(f"Error getting user data: {e}")
        return None

def increment_leech_attempts(user_id):
    """Increment user's leech attempts"""
    try:
        users_collection.update_one(
            {"user_id": user_id},
            {
                "$inc": {"leech_attempts": 1},
                "$set": {"last_activity": datetime.utcnow()}  # ✅ FIXED: Use UTC
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error incrementing attempts: {e}")
        return False

def can_user_leech(user_id):
    """Check if user can still leech (EXPIRY-AWARE)"""
    user = get_user_data(user_id)
    if not user:
        return False
    
    current_time = datetime.utcnow()  # ✅ FIXED: Use UTC
    
    # Check if user has valid verification
    if user.get("is_verified", False):
        verify_expiry = user.get("verify_expiry")
        if verify_expiry and verify_expiry > current_time:
            return True
        elif verify_expiry and verify_expiry <= current_time:
            # Verification expired, reset
            users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"is_verified": False, "verify_expiry": None}}
            )
            logger.info(f"User {user_id} verification expired")
            return user.get("leech_attempts", 0) < FREE_LEECH_LIMIT
    
    return user.get("leech_attempts", 0) < FREE_LEECH_LIMIT

def needs_verification(user_id):
    """Check if user needs verification"""
    user = get_user_data(user_id)
    if not user:
        return False
    
    current_time = datetime.utcnow()  # ✅ FIXED: Use UTC
    
    # Check if verification is expired
    if user.get("is_verified", False):
        verify_expiry = user.get("verify_expiry")
        if verify_expiry and verify_expiry <= current_time:
            return True
    
    return user.get("leech_attempts", 0) >= FREE_LEECH_LIMIT and not user.get("is_verified", False)

def set_verification_token(user_id, token):
    """Set verification token for user with expiry"""
    try:
        expiry = datetime.utcnow() + timedelta(seconds=VERIFY_TOKEN_TIMEOUT)  # ✅ FIXED: Use UTC
        logger.info(f"Token set for user {user_id}, expires at: {expiry}")
        users_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "verify_token": token,
                    "token_expiry": expiry,
                    "last_activity": datetime.utcnow()  # ✅ FIXED: Use UTC
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error setting verification token: {e}")
        return False

def verify_user(token):
    """Verify user by token and set verification expiry"""
    try:
        current_time = datetime.utcnow()  # ✅ FIXED: Use UTC
        logger.info(f"Attempting verification with token: {token[:10]}... at {current_time}")
        
        user = users_collection.find_one({
            "verify_token": token,
            "token_expiry": {"$gt": current_time}
        })
        
        if user:
            logger.info(f"Token valid for user {user['user_id']}, marking as verified")
            verify_expiry = datetime.utcnow() + timedelta(seconds=VERIFY_TOKEN_TIMEOUT)  # ✅ FIXED: Use UTC
            
            users_collection.update_one(
                {"user_id": user["user_id"]},
                {
                    "$set": {
                        "is_verified": True,
                        "verify_token": None,
                        "token_expiry": None,
                        "verify_expiry": verify_expiry,
                        "last_activity": datetime.utcnow()  # ✅ FIXED: Use UTC
                    }
                }
            )
            return user["user_id"]
        else:
            logger.warning(f"Token verification failed - token expired or invalid")
            return None
    except Exception as e:
        logger.error(f"Error verifying user: {e}")
        return None

def get_bot_stats():
    """Get overall bot statistics"""
    try:
        total_users = users_collection.count_documents({})
        verified_users = users_collection.count_documents({"is_verified": True})
        total_attempts = users_collection.aggregate([
            {"$group": {"_id": None, "total": {"$sum": "$leech_attempts"}}}
        ])
        total_attempts = list(total_attempts)
        total_attempts = total_attempts[0]["total"] if total_attempts else 0
        
        return {
            "total_users": total_users,
            "verified_users": verified_users,
            "total_attempts": total_attempts
        }
    except Exception as e:
        logger.error(f"Error getting bot stats: {e}")
        return {"total_users": 0, "verified_users": 0, "total_attempts": 0}

# ========== VIDEO VERIFICATION FUNCTIONS (SEPARATE FROM LEECH) ==========

def increment_video_attempts(user_id):
    """Increment user's video attempts (separate from leech)"""
    try:
        users_collection.update_one(
            {"user_id": user_id},
            {
                "$inc": {"video_attempts": 1},
                "$set": {"last_activity": datetime.utcnow()}  # ✅ FIXED: Use UTC
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error incrementing video attempts: {e}")
        return False

def can_user_watch_video(user_id):
    """Check if user can watch videos (SEPARATE from leech verification)"""
    user = get_user_data(user_id)
    if not user:
        return False
    
    current_time = datetime.utcnow()  # ✅ FIXED: Use UTC
    
    # Check if user has valid VIDEO verification (SEPARATE from leech)
    if user.get("is_video_verified", False):
        video_verify_expiry = user.get("video_verify_expiry")
        if video_verify_expiry and video_verify_expiry > current_time:
            return True
        elif video_verify_expiry and video_verify_expiry <= current_time:
            # Video verification expired, reset
            users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"is_video_verified": False, "video_verify_expiry": None}}
            )
            logger.info(f"User {user_id} video verification expired")
            # Fall through to check free limit
    
    # Check free video limit (SEPARATE from leech limit)
    from config import FREE_VIDEO_LIMIT
    return user.get("video_attempts", 0) < FREE_VIDEO_LIMIT

def needs_video_verification(user_id):
    """Check if user needs VIDEO verification (SEPARATE from leech)"""
    user = get_user_data(user_id)
    if not user:
        return False
    
    current_time = datetime.utcnow()  # ✅ FIXED: Use UTC
    
    # Check if video verification is expired
    if user.get("is_video_verified", False):
        video_verify_expiry = user.get("video_verify_expiry")
        if video_verify_expiry and video_verify_expiry <= current_time:
            return True
    
    from config import FREE_VIDEO_LIMIT
    return user.get("video_attempts", 0) >= FREE_VIDEO_LIMIT and not user.get("is_video_verified", False)

def set_video_verification_token(user_id, token):
    """Set VIDEO verification token (SEPARATE from leech token)"""
    try:
        from config import VIDEO_VERIFY_TOKEN_TIMEOUT
        expiry = datetime.utcnow() + timedelta(seconds=VIDEO_VERIFY_TOKEN_TIMEOUT)  # ✅ FIXED: Use UTC
        logger.info(f"Video token set for user {user_id}, expires at: {expiry}")
        users_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "video_verify_token": token,
                    "video_token_expiry": expiry,
                    "last_activity": datetime.utcnow()  # ✅ FIXED: Use UTC
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error setting video verification token: {e}")
        return False

def verify_video_user(user_id: int, token: str) -> bool:
    """Verify user for videos (SEPARATE verification from leech)"""
    try:
        current_time = datetime.utcnow()  # ✅ FIXED: Use UTC
        logger.info(f"Attempting VIDEO verification for user {user_id} with token: {token[:10]}... at {current_time}")
        
        user = users_collection.find_one({
            "user_id": user_id,
            "video_verify_token": token,
            "video_token_expiry": {"$gt": current_time}
        })
        
        if user:
            logger.info(f"Video token valid for user {user_id}, marking as video verified")
            from config import VIDEO_VERIFY_TOKEN_TIMEOUT
            video_verify_expiry = datetime.utcnow() + timedelta(seconds=VIDEO_VERIFY_TOKEN_TIMEOUT)  # ✅ FIXED: Use UTC
            
            users_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "is_video_verified": True,
                        "video_verify_token": None,
                        "video_token_expiry": None,
                        "video_verify_expiry": video_verify_expiry,
                        "last_activity": datetime.utcnow()  # ✅ FIXED: Use UTC
                    }
                }
            )
            logger.info(f"✅ User {user_id} successfully verified for videos until {video_verify_expiry}")
            return True
        else:
            # Check if token exists but expired
            user_with_token = users_collection.find_one({
                "user_id": user_id,
                "video_verify_token": token
            })
            if user_with_token:
                logger.warning(f"Invalid video verification token for user {user_id}")
            else:
                logger.warning(f"Video token for user {user_id} expired or doesn't match")
            return False
    except Exception as e:
        logger.error(f"Error verifying video user: {e}")
        return False
    
