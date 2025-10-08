"""
Database operations for user tracking and verification
"""

import pymongo
import logging
from datetime import datetime, timedelta
from config import MONGODB_URL, DATABASE_NAME, FREE_LEECH_LIMIT

logger = logging.getLogger(__name__)

# MongoDB connection
client = pymongo.MongoClient(MONGODB_URL)
db = client[DATABASE_NAME]
users_collection = db.users

def init_db():
    """Initialize database and create indexes"""
    try:
        # Create indexes
        users_collection.create_index("user_id", unique=True)
        users_collection.create_index("verify_token")
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

def get_user_data(user_id):
    """Get user data from database"""
    try:
        user = users_collection.find_one({"user_id": user_id})
        if not user:
            # Create new user
            user_data = {
                "user_id": user_id,
                "leech_attempts": 0,
                "is_verified": False,
                "verify_token": None,
                "token_expiry": None,
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
            }
        )
        return True
    except Exception as e:
        logger.error(f"Error incrementing leech attempts: {e}")
        return False

def set_verification_token(user_id, token):
    """Set verification token for user"""
    try:
        expiry = datetime.now() + timedelta(hours=1)
        users_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "verify_token": token,
                    "token_expiry": expiry,
                    "last_activity": datetime.now()
                }
            }
        )
        return True
    except Exception as e:
        logger.error(f"Error setting verification token: {e}")
        return False

def verify_user(token):
    """Verify user by token"""
    try:
        user = users_collection.find_one({
            "verify_token": token,
            "token_expiry": {"$gt": datetime.now()}
        })
        
        if user:
            # Mark user as verified
            users_collection.update_one(
                {"user_id": user["user_id"]},
                {
                    "$set": {
                        "is_verified": True,
                        "verify_token": None,
                        "token_expiry": None,
                        "last_activity": datetime.now()
                    }
                }
            )
            return user["user_id"]
        return None
    except Exception as e:
        logger.error(f"Error verifying user: {e}")
        return None

def get_bot_stats():
    """Get bot statistics"""
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

def can_user_leech(user_id):
    """Check if user can make leech attempt"""
    user = get_user_data(user_id)
    if not user:
        return False
    
    # Verified users have unlimited access
    if user.get("is_verified", False):
        return True
    
    # Check if user has remaining attempts
    return user.get("leech_attempts", 0) < FREE_LEECH_LIMIT

def needs_verification(user_id):
    """Check if user needs verification"""
    user = get_user_data(user_id)
    if not user:
        return False
    
    return (not user.get("is_verified", False) and 
            user.get("leech_attempts", 0) >= FREE_LEECH_LIMIT)
