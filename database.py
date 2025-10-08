"""
Database operations for user tracking and verification - FIXED
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
    """Initialize database and create indexes safely"""
    try:
        # Check if collection exists and has data
        existing_docs = users_collection.count_documents({})
        
        if existing_docs > 0:
            logger.info(f"Database already has {existing_docs} documents, skipping index creation")
            return
        
        # Drop existing indexes to avoid conflicts
        try:
            users_collection.drop_indexes()
            logger.info("Dropped existing indexes")
        except Exception:
            pass
        
        # Create fresh indexes
        try:
            users_collection.create_index("user_id", unique=True, sparse=True)
            users_collection.create_index("verify_token", sparse=True)
            logger.info("Database indexes created successfully")
        except pymongo.errors.DuplicateKeyError:
            logger.info("Indexes already exist, continuing...")
        
    except Exception as e:
        logger.warning(f"Database initialization warning: {e}")
        # Continue anyway - the bot can work without perfect indexes

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
            },
            upsert=True  # Create if doesn't exist
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
            },
            upsert=True  # Create if doesn't exist
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
        
        # Safe aggregation for total attempts
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
        
