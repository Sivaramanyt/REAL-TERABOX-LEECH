"""
Telegram command handlers for adult automation
Admin-only controls
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from adult_config import ADMIN_IDS, AUTOMATION_STATUS_MSG
from adult_automation import auto_scrape_and_post, get_automation_stats
from adult_scrapers import scrape_all_sites

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMIN_IDS


async def adult_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /adultstatus - Check automation status (admin only)
    """
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command")
        return
    
    try:
        stats = await get_automation_stats()
        
        message = AUTOMATION_STATUS_MSG.format(**stats)
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Status error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def adult_manual_scrape(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /adultscrape - Manually trigger scraping (admin only)
    """
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command")
        return
    
    try:
        await update.message.reply_text("🔄 Starting manual scraping...")
        
        # Run automation
        await auto_scrape_and_post(context.bot)
        
        await update.message.reply_text("✅ Manual scrape complete! Check channel.")
        
    except Exception as e:
        logger.error(f"Manual scrape error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def adult_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /adultsearch <keyword> - Search for specific content (admin only)
    """
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /adultsearch <keyword>")
        return
    
    keyword = ' '.join(context.args)
    
    try:
        await update.message.reply_text(f"🔍 Searching: {keyword}...")
        
        results = await scrape_all_sites(keyword)
        
        if results:
            msg = f"Found {len(results)} videos:\n\n"
            for i, v in enumerate(results[:5], 1):
                msg += f"{i}. {v['title'][:60]}\n"
                msg += f"   {v['source']} | {v['views']:,} views\n\n"
            
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("No videos found")
            
    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
