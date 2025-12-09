"""
🎥 Lulustream Auto Upload Module
Compatible with python-telegram-bot library
"""

import os
import asyncio
import aiohttp
from typing import Dict, Optional
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class LulustreamConfig:
    """Configuration for Lulustream module"""
    API_KEY = os.environ.get("LULUSTREAM_API_KEY", "")
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
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    params=params,
                    data=payload,
                    timeout=aiohttp.ClientTimeout(total=self.upload_timeout)
                ) as response:
                    
                    response_text = await response.text()
                    
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
                            "error": result.get("result", "Upload failed")
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}: {response_text}"
                        }
                        
        except asyncio.TimeoutError:
            return {"success": False, "error": "Upload timeout"}
        except Exception as e:
            logger.error(f"Upload exception: {e}")
            return {"success": False, "error": str(e)}


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
        """Post video to adult channel"""
        try:
            if not LulustreamConfig.ADULT_CHANNEL_ID:
                return
            
            post_caption = f"""
🔞 **{result['title']}**

▶️ **Watch Online:** {result['watch_url']}
📺 **Embed Player:** {result['embed_url']}
"""
            
            if download_url:
                post_caption += f"📥 **Direct Download:** {download_url}\n"
            
            if caption:
                post_caption += f"\n{caption}\n"
            
            post_caption += f"""
⚠️ **Adults Only | 18+**
🏷️ Tags: {result.get('tags', 'N/A')}
            """
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("▶️ Watch Now", url=result['watch_url']),
                    InlineKeyboardButton("📺 Embed", url=result['embed_url'])
                ]
            ])
            
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
            
            logger.info(f"📢 Posted to adult channel: {result['file_code']}")
            
        except Exception as e:
            logger.error(f"Error posting to adult channel: {e}")


# Global instance
_lulustream_bot = None


def init_lulustream_telegram(bot):
    """Initialize Lulustream module with Telegram bot"""
    global _lulustream_bot
    _lulustream_bot = LulustreamTelegramBot(bot)
    logger.info("🎬 Lulustream Telegram module initialized")
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
                "`/uploadlulu https://example.com/video.mp4 Tamil Movie`",
                parse_mode='Markdown'
            )
            return
        
        video_url = args[0]
        title = " ".join(args[1:]) if len(args) > 1 else "Untitled Video"
        
        if not video_url.startswith(("http://", "https://")):
            await update.message.reply_text("❌ Invalid URL")
            return
        
        status = await update.message.reply_text(
            f"⏳ **Uploading to Lulustream...**\n\n"
            f"📝 Title: `{title}`",
            parse_mode='Markdown'
        )
        
        uploader = LulustreamUploader()
        result = await uploader.upload_by_url(
            video_url=video_url,
            title=title,
            is_adult=True
        )
        
        if result["success"]:
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("▶️ Watch", url=result['watch_url']),
                    InlineKeyboardButton("📺 Embed", url=result['embed_url'])
                ]
            ])
            
            await status.edit_text(
                f"✅ **Upload Successful!**\n\n"
                f"📝 **Title:** `{title}`\n"
                f"🆔 **File Code:** `{result['file_code']}`\n"
                f"🔗 **Watch URL:** `{result['watch_url']}`\n"
                f"📺 **Embed URL:** `{result['embed_url']}`",
                reply_markup=buttons,
                parse_mode='Markdown'
            )
        else:
            await status.edit_text(
                f"❌ **Upload Failed**\n\n`{result['error']}`",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: `{str(e)}`", parse_mode='Markdown')


async def handle_lulu_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /luluinfo command"""
    try:
        args = context.args
        if len(args) < 1:
            await update.message.reply_text(
                "**Usage:** `/luluinfo <file_code>`",
                parse_mode='Markdown'
            )
            return
        
        await update.message.reply_text(
            f"ℹ️ File Code: `{args[0]}`\n"
            f"🔗 URL: `https://lulustream.com/{args[0]}`",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def handle_lulu_toggle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /togglelulu command"""
    try:
        LulustreamConfig.AUTO_UPLOAD = not LulustreamConfig.AUTO_UPLOAD
        status = "✅ Enabled" if LulustreamConfig.AUTO_UPLOAD else "❌ Disabled"
        
        await update.message.reply_text(
            f"**⚙️ Auto-Upload Settings**\n\n"
            f"Status: **{status}**",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def handle_lulu_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /luluhelp command"""
    help_text = f"""
**🎬 Lulustream Module Help**

**Available Commands:**

`/uploadlulu <url> [title]` - Manual video upload
`/luluinfo <file_code>` - Get video information  
`/togglelulu` - Toggle auto-upload
`/luluhelp` - Show this help

**Configuration:**
• API Key: {'✅ Set' if LulustreamConfig.API_KEY else '❌ Not Set'}
• Adult Channel: {'✅ Set' if LulustreamConfig.ADULT_CHANNEL_ID else '❌ Not Set'}
• Auto-Upload: {'✅ Enabled' if LulustreamConfig.AUTO_UPLOAD else '❌ Disabled'}

**Support:** Contact bot owner
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')
