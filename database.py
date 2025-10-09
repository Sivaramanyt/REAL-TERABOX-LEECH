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
            logger.info("Indexes already exist, continuing...")
        except Exception as e:
            logger.warning(f"Database initialization warning: {e}")
    except Exception as e:
        logger.error(f"Database init error: {e}")

def get_user_data(user_id):
    """Get user data from database"""
    try:
        user = users_collection.find_one({"user_id": user_id})
        if not user:
            user_data = {
                "user_id": user_id,
                "leech_attempts": 0,
                "is_verified": False,
                "verify_token": None,
                "token_expiry": None,
                "verify_expiry": None,  # NEW: Track when verification expires
                "joined_date": datetime.now(),
                "last_activity": datetime.now()
            }
            users_collection.insert_one(user_data)
            return user_data
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
                "$set": {"last_activity": datetime.now()}
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error incrementing leech attempts: {e}")
        return False

def set_verification_token(user_id, token):
    """Set verification token for user with expiry"""
    try:
        expiry = datetime.now() + timedelta(seconds=VERIFY_TOKEN_TIMEOUT)
        logger.info(f"Setting token for user {user_id}, expires at: {expiry}")
        users_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "verify_token": token,
                    "token_expiry": expiry,
                    "last_activity": datetime.now()
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
        current_time = datetime.now()
        logger.info(f"Attempting verification with token: {token[:10]}... at {current_time}")
        
        user = users_collection.find_one({
            "verify_token": token,
            "token_expiry": {"$gt": current_time}
        })
        
        if user:
            logger.info(f"Token valid for user {user['user_id']}, marking as verified")
            
            # NEW: Set verification expiry to 1 hour from now
            verify_expiry = datetime.now() + timedelta(seconds=VERIFY_TOKEN_TIMEOUT)
            
            users_collection.update_one(
                {"user_id": user["user_id"]},
                {
                    "$set": {
                        "is_verified": True,
                        "verify_token": None,
                        "token_expiry": None,
                        "verify_expiry": verify_expiry,  # NEW: Verification expires after 1 hour
                        "last_activity": datetime.now()
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
    """Get bot statistics"""
    try:
        total_users = users_collection.count_documents({})
        verified_users = users_collection.count_documents({"is_verified": True})
        
        try:
            total_attempts_cursor = users_collection.aggregate([
                {"$group": {"_id": None, "total": {"$sum": "$leech_attempts"}}}
            ])
            total_attempts_list = list(total_attempts_cursor)
            total_attempts = total_attempts_list[0]["total"] if total_attempts_list else 0
        except:
            total_attempts = 0
        
        return {
            "total_users": total_users,
            "verified_users": verified_users,
            "total_attempts": total_attempts
        }
    except Exception as e:
        logger.error(f"Error getting bot stats: {e}")
        return {"total_users": 0, "verified_users": 0, "total_attempts": 0}

def can_user_leech(user_id):
    """
    Check if user can make leech attempt
    FIXED: Now checks if verification has expired
    """
    user = get_user_data(user_id)
    if not user:
        return False
    
    # Check if user is verified
    if user.get("is_verified", False):
        # NEW: Check if verification has expired
        verify_expiry = user.get("verify_expiry")
        if verify_expiry:
            current_time = datetime.now()
            if current_time > verify_expiry:
                # Verification expired - reset user status
                logger.info(f"Verification expired for user {user_id}")
                users_collection.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "is_verified": False,
                            "verify_expiry": None,
                            "leech_attempts": FREE_LEECH_LIMIT  # Reset to limit so they need to verify again
                        }
                    }
                )
                return False  # Need to verify again
            else:
                return True  # Still verified
        else:
            # Old users without expiry - keep them verified
            return True
    
    # Check if user has remaining attempts
    return user.get("leech_attempts", 0) < FREE_LEECH_LIMIT

def needs_verification(user_id):
    """Check if user needs verification"""
    user = get_user_data(user_id)
    if not user:
        return False
    
    # Check if verification expired
    if user.get("is_verified", False):
        verify_expiry = user.get("verify_expiry")
        if verify_expiry and datetime.now() > verify_expiry:
            return True  # Verification expired, needs to verify again
        return False  # Still verified
    
    return (not user.get("is_verified", False) and
            user.get("leech_attempts", 0) >= FREE_LEECH_LIMIT)

def clean_expired_tokens():
    """Clean up expired verification tokens"""
    try:
        current_time = datetime.now()
        result = users_collection.update_many(
            {"token_expiry": {"$lt": current_time}},
            {"$set": {"verify_token": None, "token_expiry": None}}
        )
        logger.info(f"Cleaned {result.modified_count} expired tokens")
        return result.modified_count
    except Exception as e:
        logger.error(f"Error cleaning expired tokens: {e}")
        return 0

def clean_expired_verifications():
    """Clean up expired verifications - NEW FUNCTION"""
    try:
        current_time = datetime.now()
        result = users_collection.update_many(
            {
                "is_verified": True,
                "verify_expiry": {"$lt": current_time}
            },
            {
                "$set": {
                    "is_verified": False,
                    "verify_expiry": None,
                    "leech_attempts": FREE_LEECH_LIMIT
                }
            }
        )
        logger.info(f"Cleaned {result.modified_count} expired verifications")
        return result.modified_count
    except Exception as e:
        logger.error(f"Error cleaning expired verifications: {e}")
        return 0
    
