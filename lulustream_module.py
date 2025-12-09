"""
🎥 Lulustream Auto Upload Module
Compatible with python-telegram-bot library
- Source Channel Monitoring
- Direct Link Only (No Embed)
- Auto-upload to Adult Channel
"""

import os
import asyncio
import aiohttp
from typing import Dict, Optional
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes, MessageHandler, filters

logger = logging.getLogger(__name__)


class LulustreamConfig:
    """Configuration for Lulustream module"""
    API_KEY = os.environ.get("LULUSTREAM_API_KEY", "")
    
    # Source channel where videos are posted
    SOURCE_CHANNEL_ID = int(os.environ.get("SOURCE_CHANNEL_ID", "0"))
    
    # Adult channel where Lulustream links will be posted
    ADULT_CHANNEL_ID = int(os.environ.get("ADULT_CHANNEL_ID", "0"))
    
    AUTO_UPLOAD = os.environ.get("AUTO_LULUSTREAM", "True").lower() == "true"
    DEFAULT_TAGS = os.environ.get("LULU_TAGS", "tamil,adult,movies,hd")
    UPLOAD_FOLDER_ID = os.environ.get("LULU_FOLDER_ID", "")


class LulustreamUploader:
    """Handles all Lulustream upload operations"""
    
    def __init__(self):
        self.api_key = LulustreamConfig.API_KEY
        self.base_url = "https://lulustream.com/api/upload/url"
        self.upload_timeout = 300
        
    async def upload_by_url(
        self,
        video_url: str,
        title: str = "Video",
        is_adult: bool = True,
        tags: str = None,
        folder_id: str = None,
        public: bool = True
    ) -> Dict:
        """Upload video to Lulustream using direct URL"""
        try:
            if not self.api_key:
                return {"success": False, "error": "API key not configured"}
            
            params = {"key": self.api_key}
            
            payload = {
                "url": video_url,
                "file_adult": 1 if is_adult else 0,
                "file_public": 1 if public else 0,
            }
            
            if tags:
                payload["tags"] = tags
            elif LulustreamConfig.DEFAULT_TAGS:
                payload["tags"] = LulustreamConfig.DEFAULT_TAGS
                
            if folder_id:
                payload["folder_id"] = folder_id
            elif LulustreamConfig.UPLOAD_FOLDER_ID:
                payload["folder_id"] = LulustreamConfig.UPLOAD_FOLDER_ID
            
            logger.info(f"🎬 Uploading to Lulustream: {title}")
            logger.info(f"📹 Video URL: {video_url[:50]}...")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    params=params,
                    data=payload,
                    timeout=aiohttp.ClientTimeout(total=self.upload_timeout)
                ) as response:
                    
                    response_text = await response.text()
                    logger.info(f"Response: {response_text[:200]}")
                    
                    if response.status == 200:
                        try:
                            result = await response.json()
                        except:
                            result = {"result": response_text}
                        
                        if result.get("msg") == "OK" or result.get("status") == 200:
                            file_code = result.get("filecode") or result.get("file_code")
                            
                            if file_code:
                                return {
                                    "success": True,
                                    "file_code": file_code,
                                    "watch_url": f"https://lulustream.com/{file_code}",
                                    "embed_url": f"https://lulustream.com/e/{file_code}",
                                    "download_url": f"https://lulustream.com/d/{file_code}",
                                    "title": title,
                                    "tags": payload.get("tags", "")
                                }
                        
                        return {
                            "success": False,
                            "error": result.get("result", "Upload failed - Unknown error")
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}: {response_text}"
                        }
                        
        except asyncio.TimeoutError:
            logger.error("⏱️ Upload timeout")
            return {"success": False, "error": "Upload timeout (5 min exceeded)"}
        except Exception as e:
            logger.error(f"❌ Upload exception: {e}")
            return {"success": False, "error": str(e)}
    
    
    async def get_video_info(self, file_code: str) -> Dict:
        """Get video information from Lulustream"""
        try:
            url = f"https://lulustream.com/api/file/info"
            params = {
                "key": self.api_key,
                "file_code": file_code
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
            return {}
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return {}


class LulustreamTelegramBot:
    """Telegram bot integration for Lulustream"""
    
    def __init__(self, bot):
        self.bot = bot
        self.uploader = LulustreamUploader()
        
    async def auto_upload_and_post(
        self,
        video_url: str,
        title: str,
        thumbnail: str = None,
        caption: str = None
    ) -> Dict:
        """Auto-upload video and post to adult channel"""
        try:
            if not LulustreamConfig.AUTO_UPLOAD:
                return {"success": False, "error": "Auto-upload disabled"}
            
            if not LulustreamConfig.API_KEY:
                return {"success": False, "error": "API key not configured"}
            
            logger.info(f"🚀 Auto-uploading: {title}")
            
            result = await self.uploader.upload_by_url(
                video_url=video_url,
                title=title,
                is_adult=True
            )
            
            if result["success"]:
                await self.post_to_adult_channel(
                    result=result,
                    thumbnail=thumbnail,
                    caption=caption,
                    download_url=video_url
                )
                
                logger.info(f"✅ Auto-upload success: {result['watch_url']}")
                return result
            else:
                logger.error(f"❌ Auto-upload failed: {result['error']}")
                return result
                
        except Exception as e:
            logger.error(f"Auto-upload exception: {e}")
            return {"success": False, "error": str(e)}
    
    
    async def post_to_adult_channel(
        self,
        result: Dict,
        thumbnail: str = None,
        caption: str = None,
        download_url: str = None
    ):
        """Post video to adult channel with DIRECT LINK ONLY"""
        try:
            if not LulustreamConfig.ADULT_CHANNEL_ID:
                logger.warning("⚠️ Adult channel ID not configured")
                return
            
            # Caption with DIRECT LINK ONLY (no embed)
            post_caption = f"""
🔞 **{result['title']}**

🎬 **Watch Here:** {result['watch_url']}
"""
            
            # Optional: Add download link
            if download_url:
                post_caption += f"\n📥 **Download:** {download_url}\n"
            
            # Optional: Add custom caption
            if caption and len(caption) > 0:
                # Extract relevant info from caption (skip URLs)
                caption_lines = [line for line in caption.split('\n') if not line.startswith('http')]
                if caption_lines:
                    post_caption += f"\n📝 {' '.join(caption_lines[:2])}\n"
            
            post_caption += f"""
⚠️ **Adults Only | 18+**
🏷️ {result.get('tags', 'N/A')}
            """
            
            # Single button with DIRECT LINK only
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("▶️ Watch Now", url=result['watch_url'])
                ]
            ])
            
            # Send to adult channel
            if thumbnail:
                await self.bot.send_photo(
                    chat_id=LulustreamConfig.ADULT_CHANNEL_ID,
                    photo=thumbnail,
                    caption=post_caption,
                    reply_markup=buttons,
                    parse_mode='Markdown'
                )
            else:
                await self.bot.send_message(
                    chat_id=LulustreamConfig.ADULT_CHANNEL_ID,
                    text=post_caption,
                    reply_markup=buttons,
                    parse_mode='Markdown'
                )
            
            logger.info(f"📢 Posted to adult channel with DIRECT link: {result['watch_url']}")
            
        except Exception as e:
            logger.error(f"Error posting to adult channel: {e}")


# ============= SOURCE CHANNEL MONITOR =============

async def monitor_source_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Monitor SOURCE channel for new videos and auto-upload to Lulustream
    This handler will be triggered when a video is posted in SOURCE_CHANNEL
    """
    try:
        message = update.channel_post
        if not message:
            return
        
        # Check if message is from SOURCE channel
        if message.chat.id != LulustreamConfig.SOURCE_CHANNEL_ID:
            return
        
        # Check if auto-upload is enabled
        if not LulustreamConfig.AUTO_UPLOAD:
            logger.info("⏸️ Auto-upload disabled, skipping...")
            return
        
        # Get video/document
        video = message.video or message.document
        if not video:
            return
        
        logger.info(f"📹 New video detected in source channel: {message.message_id}")
        
        # Extract details
        caption = message.caption or "Untitled Video"
        title = caption.split("\n")[0] if caption else "Untitled Video"  # First line as title
        
        # Clean title (remove emojis and extra characters)
        import re
        title = re.sub(r'[^\w\s\-\(\)]', '', title)[:100]  # Clean and limit to 100 chars
        
        # Get thumbnail
        thumbnail_file_id = None
        if video.thumbnail:
            thumbnail_file_id = video.thumbnail.file_id
        
        # Extract direct download link from caption
        direct_link = None
        if caption:
            lines = caption.split("\n")
            for line in lines:
                # Look for URLs in caption
                if "http" in line.lower():
                    # Extract URL from line
                    words = line.split()
                    for word in words:
                        if word.startswith("http"):
                            # Check if it's a video link
                            if any(ext in word.lower() for ext in ['.mp4', '.mkv', '.avi', '.mov', 'download', 'terabox', 'drive', 'stream']):
                                direct_link = word.strip()
                                break
                            # Or just any http link
                            elif not any(skip in word.lower() for skip in ['t.me', 'telegram', 'youtube.com/watch']):
                                direct_link = word.strip()
                                break
                if direct_link:
                    break
        
        if not direct_link:
            logger.warning("⚠️ No direct download link found in caption")
            logger.info("Caption content:")
            logger.info(caption)
            # Skip if no direct link
            return
        
        logger.info(f"🔗 Direct link found: {direct_link[:50]}...")
        
        # Upload to Lulustream
        lulu_bot = get_lulustream_uploader()
        if not lulu_bot:
            logger.error("❌ Lulustream bot not initialized")
            return
        
        result = await lulu_bot.auto_upload_and_post(
            video_url=direct_link,
            title=title,
            thumbnail=thumbnail_file_id,
            caption=caption
        )
        
        if result["success"]:
            logger.info(f"✅ Successfully processed: {result['watch_url']}")
        else:
            logger.error(f"❌ Upload failed: {result['error']}")
            
    except Exception as e:
        logger.error(f"❌ Error in source channel monitor: {e}")
        import traceback
        logger.error(traceback.format_exc())


# Global instance
_lulustream_bot = None


def init_lulustream_telegram(bot):
    """Initialize Lulustream module with Telegram bot"""
    global _lulustream_bot
    _lulustream_bot = LulustreamTelegramBot(bot)
    logger.info("🎬 Lulustream Telegram module initialized")
    logger.info(f"   📺 Source Channel: {LulustreamConfig.SOURCE_CHANNEL_ID}")
    logger.info(f"   🔞 Adult Channel: {LulustreamConfig.ADULT_CHANNEL_ID}")
    logger.info(f"   ⚙️ Auto-Upload: {'✅ Enabled' if LulustreamConfig.AUTO_UPLOAD else '❌ Disabled'}")
    return _lulustream_bot


def get_lulustream_uploader():
    """Get Lulustream uploader instance"""
    return _lulustream_bot


# ============= COMMAND HANDLERS =============

async def handle_lulu_upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /uploadlulu command"""
    try:
        if not update.message:
            return
            
        args = context.args
        
        if len(args) < 1:
            await update.message.reply_text(
                "**📤 Lulustream Manual Upload**\n\n"
                "**Usage:**\n"
                "`/uploadlulu <direct_url> [title]`\n\n"
                "**Example:**\n"
                "`/uploadlulu https://example.com/video.mp4 Tamil Movie`\n\n"
                "**Note:** URL must be direct video link",
                parse_mode='Markdown'
            )
            return
        
        video_url = args[0]
        title = " ".join(args[1:]) if len(args) > 1 else "Untitled Video"
        
        if not video_url.startswith(("http://", "https://")):
            await update.message.reply_text("❌ Invalid URL. Must start with http:// or https://")
            return
        
        status = await update.message.reply_text(
            f"⏳ **Uploading to Lulustream...**\n\n"
            f"📝 Title: `{title}`\n"
            f"🔗 URL: `{video_url[:50]}...`",
            parse_mode='Markdown'
        )
        
        uploader = LulustreamUploader()
        result = await uploader.upload_by_url(
            video_url=video_url,
            title=title,
            is_adult=True
        )
        
        if result["success"]:
            # Single button with DIRECT LINK only
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("▶️ Watch Now", url=result['watch_url'])
                ]
            ])
            
            await status.edit_text(
                f"✅ **Upload Successful!**\n\n"
                f"📝 **Title:** `{title}`\n"
                f"🆔 **File Code:** `{result['file_code']}`\n"
                f"🎬 **Direct Link:** `{result['watch_url']}`\n"
                f"🏷️ **Tags:** `{result.get('tags', 'N/A')}`",
                reply_markup=buttons,
                parse_mode='Markdown'
            )
        else:
            await status.edit_text(
                f"❌ **Upload Failed**\n\n"
                f"**Error:** `{result['error']}`\n\n"
                f"**Troubleshooting:**\n"
                f"• Check API key is correct\n"
                f"• Verify URL is accessible\n"
                f"• Ensure video format is supported",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Manual upload error: {e}")
        await update.message.reply_text(f"❌ Error: `{str(e)}`", parse_mode='Markdown')


async def handle_lulu_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /luluinfo command"""
    try:
        args = context.args
        if len(args) < 1:
            await update.message.reply_text(
                "**ℹ️ Get Video Info**\n\n"
                "**Usage:** `/luluinfo <file_code>`\n\n"
                "**Example:** `/luluinfo abc123xyz`",
                parse_mode='Markdown'
            )
            return
        
        file_code = args[0]
        status = await update.message.reply_text("⏳ Fetching video info...")
        
        uploader = LulustreamUploader()
        info = await uploader.get_video_info(file_code)
        
        if info and info.get("status") == 200:
            data = info.get("result", {})
            await status.edit_text(
                f"**📹 Video Information**\n\n"
                f"🆔 **File Code:** `{file_code}`\n"
                f"📝 **Title:** `{data.get('title', 'N/A')}`\n"
                f"👁️ **Views:** `{data.get('views', 0)}`\n"
                f"📊 **Status:** `{data.get('status', 'N/A')}`\n"
                f"📅 **Uploaded:** `{data.get('created', 'N/A')}`\n"
                f"🎬 **Direct Link:** `https://lulustream.com/{file_code}`",
                parse_mode='Markdown'
            )
        else:
            await status.edit_text(
                f"ℹ️ **File Code:** `{file_code}`\n"
                f"🎬 **Direct Link:** `https://lulustream.com/{file_code}`\n\n"
                f"_Detailed info not available_",
                parse_mode='Markdown'
            )
                
    except Exception as e:
        await update.message.reply_text(f"❌ Error: `{str(e)}`", parse_mode='Markdown')


async def handle_lulu_toggle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /togglelulu command"""
    try:
        LulustreamConfig.AUTO_UPLOAD = not LulustreamConfig.AUTO_UPLOAD
        status = "✅ Enabled" if LulustreamConfig.AUTO_UPLOAD else "❌ Disabled"
        
        await update.message.reply_text(
            f"**⚙️ Auto-Upload Settings**\n\n"
            f"**Status:** {status}\n\n"
            f"{'Videos will now automatically upload to Lulustream when posted in source channel.' if LulustreamConfig.AUTO_UPLOAD else 'Auto-upload is disabled. Use /uploadlulu for manual uploads.'}",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def handle_lulu_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /luluhelp command"""
    help_text = f"""
**🎬 Lulustream Module Help**

**📋 Available Commands:**

`/uploadlulu <url> [title]` - Manual video upload
`/luluinfo <file_code>` - Get video information  
`/togglelulu` - Toggle auto-upload
`/luluhelp` - Show this help

**⚙️ Configuration:**
• API Key: {'✅ Set' if LulustreamConfig.API_KEY else '❌ Not Set'}
• Source Channel: {'✅ Set (ID: ' + str(LulustreamConfig.SOURCE_CHANNEL_ID) + ')' if LulustreamConfig.SOURCE_CHANNEL_ID else '❌ Not Set'}
• Adult Channel: {'✅ Set (ID: ' + str(LulustreamConfig.ADULT_CHANNEL_ID) + ')' if LulustreamConfig.ADULT_CHANNEL_ID else '❌ Not Set'}
• Auto-Upload: {'✅ Enabled' if LulustreamConfig.AUTO_UPLOAD else '❌ Disabled'}

**🔄 How It Works:**
1. Post video with direct link in **Source Channel**
2. Bot detects and uploads to **Lulustream**
3. Direct link posted to **Adult Channel**
4. Users click and watch

**📝 Note:** 
- Only **direct links** are posted (no embed)
- Ensure video URLs are in caption
- Tags: `{LulustreamConfig.DEFAULT_TAGS}`

**💬 Support:** Contact bot owner
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')


def get_source_channel_handler():
    """Get the message handler for source channel monitoring"""
    if LulustreamConfig.SOURCE_CHANNEL_ID:
        return MessageHandler(
            filters.Chat(chat_id=LulustreamConfig.SOURCE_CHANNEL_ID) & 
            filters.ChatType.CHANNEL & 
            (filters.VIDEO | filters.Document.ALL),
            monitor_source_channel
        )
    else:
        logger.warning("⚠️ SOURCE_CHANNEL_ID not configured, channel monitoring disabled")
        return None
