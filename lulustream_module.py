"""
🎬 Lulustream Auto Upload Module
Standalone module - No modification to existing bot code needed
Author: Your Name
"""

import os
import asyncio
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LulustreamConfig:
    """Configuration for Lulustream module"""
    API_KEY = os.environ.get("LULUSTREAM_API_KEY", "")
    ADULT_CHANNEL_ID = int(os.environ.get("ADULT_CHANNEL_ID", "0"))
    AUTO_UPLOAD = os.environ.get("AUTO_LULUSTREAM", "True").lower() == "true"
    DEFAULT_TAGS = os.environ.get("LULU_TAGS", "tamil,adult,movies,hd")
    UPLOAD_FOLDER_ID = os.environ.get("LULU_FOLDER_ID", "")  # Optional
    

class LulustreamUploader:
    """Handles all Lulustream upload operations"""
    
    def __init__(self):
        self.api_key = LulustreamConfig.API_KEY
        self.base_url = "https://lulustream.com/api/upload/url"
        self.upload_timeout = 300  # 5 minutes
        
    async def upload_by_url(
        self,
        video_url: str,
        title: str = "Video",
        is_adult: bool = True,
        tags: str = None,
        folder_id: str = None,
        public: bool = True
    ) -> Dict:
        """
        Upload video to Lulustream using direct URL
        
        Args:
            video_url: Direct download link
            title: Video title
            is_adult: Adult content flag (1 or 0)
            tags: Comma-separated tags
            folder_id: Folder ID (optional)
            public: Make video public
            
        Returns:
            Dict with success status and video details
        """
        try:
            if not self.api_key:
                return {"success": False, "error": "API key not configured"}
            
            # Prepare parameters
            params = {"key": self.api_key}
            
            payload = {
                "url": video_url,
                "file_adult": 1 if is_adult else 0,
                "file_public": 1 if public else 0,
            }
            
            # Add optional parameters
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
                    logger.info(f"Response: {response_text}")
                    
                    if response.status == 200:
                        try:
                            result = await response.json()
                        except:
                            result = {"result": response_text}
                        
                        # Check if upload was successful
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


class LulustreamBot:
    """Main bot class for Lulustream functionality"""
    
    def __init__(self, app: Client):
        self.app = app
        self.uploader = LulustreamUploader()
        self.upload_queue = asyncio.Queue()
        self.is_processing = False
        
    def register_handlers(self):
        """Register all command handlers"""
        
        # Manual upload command
        @self.app.on_message(filters.command("uploadlulu") & filters.private)
        async def cmd_upload_lulu(client, message: Message):
            await self.handle_manual_upload(message)
        
        # Video info command
        @self.app.on_message(filters.command("luluinfo") & filters.private)
        async def cmd_lulu_info(client, message: Message):
            await self.handle_video_info(message)
        
        # Toggle auto-upload
        @self.app.on_message(filters.command("togglelulu") & filters.private)
        async def cmd_toggle_lulu(client, message: Message):
            await self.handle_toggle_auto_upload(message)
        
        # Help command
        @self.app.on_message(filters.command("luluhelp") & filters.private)
        async def cmd_lulu_help(client, message: Message):
            await self.show_help(message)
        
        logger.info("✅ Lulustream handlers registered")
    
    
    async def handle_manual_upload(self, message: Message):
        """Handle manual upload command"""
        try:
            parts = message.text.split(maxsplit=2)
            
            if len(parts) < 2:
                await message.reply_text(
                    "**📤 Lulustream Manual Upload**\n\n"
                    "**Usage:**\n"
                    "`/uploadlulu <direct_url> [title]`\n\n"
                    "**Example:**\n"
                    "`/uploadlulu https://example.com/video.mp4 Tamil Movie`\n\n"
                    "**Note:** URL must be direct video link"
                )
                return
            
            video_url = parts[1]
            title = parts[2] if len(parts) > 2 else "Untitled Video"
            
            # Validate URL
            if not video_url.startswith(("http://", "https://")):
                await message.reply_text("❌ Invalid URL. Must start with http:// or https://")
                return
            
            status = await message.reply_text(
                f"⏳ **Uploading to Lulustream...**\n\n"
                f"📝 Title: `{title}`\n"
                f"🔗 URL: `{video_url[:50]}...`"
            )
            
            # Upload
            result = await self.uploader.upload_by_url(
                video_url=video_url,
                title=title,
                is_adult=True
            )
            
            if result["success"]:
                # Create inline buttons
                buttons = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("▶️ Watch", url=result['watch_url']),
                        InlineKeyboardButton("📺 Embed", url=result['embed_url'])
                    ],
                    [
                        InlineKeyboardButton("📥 Download", url=result['download_url'])
                    ]
                ])
                
                await status.edit_text(
                    f"✅ **Upload Successful!**\n\n"
                    f"📝 **Title:** `{title}`\n"
                    f"🆔 **File Code:** `{result['file_code']}`\n"
                    f"🔗 **Watch URL:** `{result['watch_url']}`\n"
                    f"📺 **Embed URL:** `{result['embed_url']}`\n"
                    f"🏷️ **Tags:** `{result.get('tags', 'N/A')}`",
                    reply_markup=buttons
                )
            else:
                await status.edit_text(
                    f"❌ **Upload Failed**\n\n"
                    f"**Error:** `{result['error']}`\n\n"
                    f"Check:\n"
                    f"• API key is correct\n"
                    f"• URL is accessible\n"
                    f"• Video format is supported"
                )
                
        except Exception as e:
            await message.reply_text(f"❌ Error: `{str(e)}`")
            logger.error(f"Manual upload error: {e}")
    
    
    async def handle_video_info(self, message: Message):
        """Get video information"""
        try:
            parts = message.text.split()
            if len(parts) < 2:
                await message.reply_text(
                    "**ℹ️ Get Video Info**\n\n"
                    "**Usage:**\n"
                    "`/luluinfo <file_code>`\n\n"
                    "**Example:**\n"
                    "`/luluinfo abc123xyz`"
                )
                return
            
            file_code = parts[1]
            status = await message.reply_text("⏳ Fetching video info...")
            
            info = await self.uploader.get_video_info(file_code)
            
            if info and info.get("status") == 200:
                data = info.get("result", {})
                await status.edit_text(
                    f"**📹 Video Information**\n\n"
                    f"🆔 **File Code:** `{file_code}`\n"
                    f"📝 **Title:** `{data.get('title', 'N/A')}`\n"
                    f"👁️ **Views:** `{data.get('views', 0)}`\n"
                    f"📊 **Status:** `{data.get('status', 'N/A')}`\n"
                    f"📅 **Uploaded:** `{data.get('created', 'N/A')}`\n"
                    f"🔗 **URL:** `https://lulustream.com/{file_code}`"
                )
            else:
                await status.edit_text("❌ Could not fetch video info. Check file code.")
                
        except Exception as e:
            await message.reply_text(f"❌ Error: `{str(e)}`")
    
    
    async def handle_toggle_auto_upload(self, message: Message):
        """Toggle auto-upload feature"""
        try:
            current = LulustreamConfig.AUTO_UPLOAD
            LulustreamConfig.AUTO_UPLOAD = not current
            
            status = "✅ Enabled" if LulustreamConfig.AUTO_UPLOAD else "❌ Disabled"
            await message.reply_text(
                f"**⚙️ Auto-Upload Settings**\n\n"
                f"Status: **{status}**\n\n"
                f"{'Videos will now automatically upload to Lulustream' if LulustreamConfig.AUTO_UPLOAD else 'Auto-upload is disabled'}"
            )
        except Exception as e:
            await message.reply_text(f"❌ Error: `{str(e)}`")
    
    
    async def show_help(self, message: Message):
        """Show help message"""
        help_text = """
**🎬 Lulustream Module Help**

**Available Commands:**

`/uploadlulu <url> [title]` - Manual video upload
`/luluinfo <file_code>` - Get video information
`/togglelulu` - Toggle auto-upload
`/luluhelp` - Show this help

**Auto-Upload:**
When enabled, videos will automatically upload to Lulustream and post to adult channel.

**Configuration:**
• API Key: {'✅ Set' if LulustreamConfig.API_KEY else '❌ Not Set'}
• Adult Channel: {'✅ Set' if LulustreamConfig.ADULT_CHANNEL_ID else '❌ Not Set'}
• Auto-Upload: {'✅ Enabled' if LulustreamConfig.AUTO_UPLOAD else '❌ Disabled'}

**Support:** @YourSupportChannel
        """
        await message.reply_text(help_text)
    
    
    async def auto_upload_and_post(
        self,
        video_url: str,
        title: str,
        thumbnail: str = None,
        caption: str = None
    ) -> Dict:
        """
        Auto-upload video and post to adult channel
        Call this function from your existing handlers
        
        Args:
            video_url: Direct video download link
            title: Video title
            thumbnail: Thumbnail URL or file path
            caption: Additional caption text
            
        Returns:
            Dict with upload result
        """
        try:
            if not LulustreamConfig.AUTO_UPLOAD:
                return {"success": False, "error": "Auto-upload disabled"}
            
            if not LulustreamConfig.API_KEY:
                return {"success": False, "error": "API key not configured"}
            
            logger.info(f"🚀 Auto-uploading: {title}")
            
            # Upload to Lulustream
            result = await self.uploader.upload_by_url(
                video_url=video_url,
                title=title,
                is_adult=True
            )
            
            if result["success"]:
                # Post to adult channel
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
                logger.warning("Adult channel ID not configured")
                return
            
            # Create caption
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
            
            # Create buttons
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("▶️ Watch Now", url=result['watch_url']),
                    InlineKeyboardButton("📺 Embed", url=result['embed_url'])
                ]
            ])
            
            # Send to channel
            if thumbnail:
                await self.app.send_photo(
                    chat_id=LulustreamConfig.ADULT_CHANNEL_ID,
                    photo=thumbnail,
                    caption=post_caption,
                    reply_markup=buttons
                )
            else:
                await self.app.send_message(
                    chat_id=LulustreamConfig.ADULT_CHANNEL_ID,
                    text=post_caption,
                    reply_markup=buttons
                )
            
            logger.info(f"📢 Posted to adult channel: {result['file_code']}")
            
        except Exception as e:
            logger.error(f"Error posting to adult channel: {e}")


# Global instance (will be initialized in main.py)
lulustream_bot = None


def init_lulustream(app: Client) -> LulustreamBot:
    """
    Initialize Lulustream module
    Call this from main.py
    """
    global lulustream_bot
    lulustream_bot = LulustreamBot(app)
    lulustream_bot.register_handlers()
    logger.info("🎬 Lulustream module initialized")
    return lulustream_bot


# Helper function for easy access
def get_lulustream_bot() -> LulustreamBot:
    """Get Lulustream bot instance"""
    return lulustream_bot
