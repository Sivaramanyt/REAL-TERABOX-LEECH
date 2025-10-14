"""
Simple Random Videos - NO DATABASE NEEDED
Uses hardcoded file_ids with verification system
"""
import logging
import random as rand
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import users_collection, get_user_data
from verification import generate_verify_token, generate_monetized_verification_link
from config import BOT_USERNAME, VERIFY_TOKEN_TIMEOUT

logger = logging.getLogger(__name__)

# Settings
FREE_VIDEO_LIMIT = 3

# 🎬 YOUR VIDEO FILE IDs (NO DATABASE NEEDED!)
RANDOM_VIDEOS = [
    'BAACAgUAAxkBAAIBEmcNDdQTt8sF4MvFKqkjnU8Pnh-cAAKHEgAC0rgoVXJC8bPAREqWNgQ',
    'BAACAgUAAxkBAAIBE2cNDdiR4hW7gPHFkROYCXAAAQpM3AACVRQAAv3nIFUXK-oNPHxg7jYE',
    'BAACAgUAAxkBAAIBFGcNDeF1r8nnJrCZLGBdSJYBJYT8AALqFAAC5OkoVQSIl3k8vG0zNgQ'
]

DIVINE_VIDEOS = [
    'BAACAgUAAxkBAAIBFWcNDeq9tUjbKNRVr0xY5mnqSDbEAAIFFwACXhkhVaDKP1YvKJ-BNgQ',
    'BAACAgUAAxkBAAIBFmcNDfIjugHkFfNn4aUz3L_6mhcpAAI0FQACMIkoVenE8m9W_sNtNgQ',
    'BAACAgUAAxkBAAIBF2cNDfmGYzSuAAFQQpqW0cR55J7_RAACvhMAAv-qKFWPivJgQqQWdTYE'
]

HORROR_VIDEOS = [
    'BAACAgUAAxkBAAIBGGcNDgX0slRhCX7KQZAo6BqU7NiRAALLEwAC9ukoVZWbEqPvB2bENgQ',
    'BAACAgUAAxkBAAIBGWcNDhBTl-mfTdxn7NljLVOgOe9yAAJ-FQACMIkoVcww78ySjQbPNgQ',
    'BAACAgUAAxkBAAIBGmcNDhmqmJqwUZHdlMFjp14AAebblgAC-hIAAr_eIFWQdBDi3pKdljYE'
]

async def handle_videos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /videos command"""
    user_id = update.effective_user.id
    
    # Get user data
    user_data = get_user_data(user_id)
    if not user_data:
        await update.message.reply_text("❌ Error. Try /start first.")
        return
    
    video_attempts = user_data.get("video_attempts", 0)
    video_verified = user_data.get("video_verified", False)
    
    # Check verification
    if not video_verified and video_attempts >= FREE_VIDEO_LIMIT:
        await send_video_verification_message(update, context)
        return
    
    # Send video
    await send_random_video(update, context, video_attempts, video_verified)

async def send_random_video(update: Update, context: ContextTypes.DEFAULT_TYPE, video_attempts, video_verified):
    """Send random video"""
    user_id = update.effective_user.id
    
    # Choose category
    category = rand.choice(['random', 'divine', 'horror'])
    
    if category == 'random':
        video_file_id = rand.choice(RANDOM_VIDEOS)
        caption = "🎬 Random Video"
    elif category == 'divine':
        video_file_id = rand.choice(DIVINE_VIDEOS)
        caption = "🙏 Divine Video"
    else:
        video_file_id = rand.choice(HORROR_VIDEOS)
        caption = "👻 Horror Video"
    
    try:
        # Send video
        await update.message.reply_video(
            video=video_file_id,
            caption=caption
        )
        
        # Increment attempts if not verified
        if not video_verified:
            users_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"video_attempts": 1}}
            )
            video_attempts += 1
        
        # Show status
        if video_verified:
            status = "♾️ **Status:** Unlimited videos"
        else:
            remaining = FREE_VIDEO_LIMIT - video_attempts
            status = f"⏳ **Remaining:** {remaining}/{FREE_VIDEO_LIMIT} free videos"
            if remaining == 0:
                status += "\n\n🔒 **Next video requires verification!**"
        
        await update.message.reply_text(status, parse_mode='Markdown')
        
        logger.info(f"✅ Sent {category} video to {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        await update.message.reply_text("❌ Error sending video. Try again.")

async def send_video_verification_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send verification message"""
    user_id = update.effective_user.id
    token = generate_verify_token()
    
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"video_verify_token": token}}
    )
    
    verify_link = generate_monetized_verification_link(BOT_USERNAME, token)
    
    if not verify_link:
        await update.message.reply_text("❌ Error generating link")
        return
    
    validity_hours = VERIFY_TOKEN_TIMEOUT / 3600
    if validity_hours >= 24:
        validity_str = f"{int(validity_hours / 24)} days"
    elif validity_hours >= 1:
        validity_str = f"{int(validity_hours)} hours"
    else:
        validity_str = f"{int(VERIFY_TOKEN_TIMEOUT / 60)} minutes"
    
    message = (
        "🎬 **Video Verification Required!**\n\n"
        f"You've used {FREE_VIDEO_LIMIT} free videos!\n\n"
        "Click below to verify:\n\n"
        f"🔗 {verify_link}\n\n"
        f"✨ **Unlimited videos for {validity_str} after verification!**\n\n"
        "**Note:** This is separate from Terabox leech verification."
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Verify for Videos", url=verify_link)],
        [InlineKeyboardButton("📺 How to Verify?", url="https://t.me/Sr_Movie_Links/52")],
        [InlineKeyboardButton("💬 ANY HELP", url="https://t.me/Siva9789")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
