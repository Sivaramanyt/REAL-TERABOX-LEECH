"""
Adult Content Automation Engine
Runs alongside existing Terabox bot without interference
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional
import requests

from telegram import Bot
from telegram.error import TelegramError

from adult_config import *
from adult_scrapers import scrape_all_sites, format_views, is_illegal_content
from database import db  # Use existing database

logger = logging.getLogger(__name__)

# Database collections
adult_videos_collection = db['adult_posted_videos']


def already_posted(video_url: str) -> bool:
    """Check if video already posted"""
    return adult_videos_collection.find_one({'url': video_url}) is not None


def save_posted_video(video_data: dict):
    """Save posted video to database"""
    adult_videos_collection.insert_one({
        'url': video_data['url'],
        'title': video_data['title'],
        'source': video_data['source'],
        'lulustream_link': video_data.get('lulustream_link'),
        'posted_at': datetime.now(),
        'views': video_data.get('views', 0)
    })


async def upload_to_lulustream(download_url: str, title: str) -> Optional[str]:
    """
    Upload video to LuluStream via Remote URL (FREE method)
    Returns embed link if successful
    """
    
    if not LULUSTREAM_API_KEY:
        logger.error("❌ LuluStream API key not configured")
        return None
    
    try:
        logger.info(f"⬆️ Uploading to LuluStream: {title[:60]}...")
        
        response = requests.post(
            "https://api.lulustream.com/upload/url",
            headers={"Authorization": f"Bearer {LULUSTREAM_API_KEY}"},
            json={
                "url": download_url,
                "title": title
            },
            timeout=600  # 10 mins timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            embed_link = data.get('embed_url') or data.get('url')
            logger.info(f"✅ Uploaded successfully")
            return embed_link
        else:
            logger.error(f"❌ LuluStream upload failed: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Upload error: {e}")
        return None


async def post_to_channel(bot: Bot, video_data: dict, lulustream_link: str):
    """Post video to Telegram channel"""
    
    if not ADULT_CHANNEL_ID:
        logger.error("❌ Adult channel ID not configured")
        return False
    
    try:
        caption = f"""
🔥 {video_data['title'][:150]}

📊 {format_views(video_data['views'])} Views | ⏱ {video_data['duration']}
▶️ Watch: {lulustream_link}

🇮🇳 #Indian #Desi #Adult
📱 Source: {video_data['source']}

⚠️ 18+ Only
"""
        
        # Send photo with caption
        await bot.send_photo(
            chat_id=ADULT_CHANNEL_ID,
            photo=video_data['thumbnail'],
            caption=caption,
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ Posted to channel: {video_data['title'][:60]}")
        return True
        
    except TelegramError as e:
        logger.error(f"❌ Telegram post error: {e}")
        return False


async def auto_scrape_and_post(bot: Bot):
    """
    Main automation function
    Called by scheduler
    """
    
    logger.info(f"\n{'='*50}")
    logger.info(f"🤖 Starting adult content automation...")
    logger.info(f"⏰ Time: {datetime.now()}")
    logger.info(f"{'='*50}\n")
    
    try:
        # Step 1: Scrape videos
        all_videos = await scrape_all_sites()
        
        if not all_videos:
            logger.warning("⚠️ No videos found in this run")
            return
        
        # Step 2: Process and post videos
        posted_count = 0
        
        for video in all_videos[:10]:  # Check top 10
            
            # Skip if already posted
            if already_posted(video['url']):
                logger.debug(f"⏭ Skipping duplicate: {video['title'][:60]}")
                continue
            
            # Final safety check
            if is_illegal_content(video['title'], video.get('tags', [])):
                logger.warning(f"🚫 Final block: {video['title'][:60]}")
                continue
            
            try:
                # Upload to LuluStream
                lulustream_link = await upload_to_lulustream(
                    video['download_url'],
                    video['title']
                )
                
                if not lulustream_link:
                    logger.warning(f"⚠️ Upload failed, skipping: {video['title'][:60]}")
                    continue
                
                # Post to channel
                success = await post_to_channel(bot, video, lulustream_link)
                
                if success:
                    # Save to database
                    video['lulustream_link'] = lulustream_link
                    save_posted_video(video)
                    
                    posted_count += 1
                    logger.info(f"✅ Posted {posted_count}/{POSTS_PER_RUN}")
                    
                    # Wait between posts
                    if posted_count < POSTS_PER_RUN:
                        logger.info(f"⏳ Waiting {POST_INTERVAL}s before next post...")
                        await asyncio.sleep(POST_INTERVAL)
                    
                    # Stop if reached limit
                    if posted_count >= POSTS_PER_RUN:
                        break
                
            except Exception as e:
                logger.error(f"❌ Processing error: {e}")
                continue
        
        logger.info(f"\n{'='*50}")
        logger.info(f"✅ Automation complete! Posted {posted_count} videos")
        logger.info(f"{'='*50}\n")
        
    except Exception as e:
        logger.error(f"❌ Automation error: {e}")


async def get_automation_stats() -> dict:
    """Get automation statistics"""
    
    total_posted = adult_videos_collection.count_documents({})
    
    today_posted = adult_videos_collection.count_documents({
        'posted_at': {'$gte': datetime.now().replace(hour=0, minute=0, second=0)}
    })
    
    return {
        'total_posted': total_posted,
        'today_posted': today_posted,
        'min_views': MIN_VIEWS,
        'posts_per_run': POSTS_PER_RUN,
        'schedule': ', '.join(SCRAPE_HOURS),
        'channel_id': ADULT_CHANNEL_ID,
        'blocked_count': len(ILLEGAL_KEYWORDS)
    }
