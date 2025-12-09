"""
🎥 Lulustream Auto Upload Module
- Direct URL based uploads (no raw file upload)
- Monitors source channel for posts with links
- Posts DIRECT Lulu link (no embed) to adult channel
"""

import os
import asyncio
import aiohttp
import logging
import re
from typing import Dict

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes, MessageHandler, filters

logger = logging.getLogger(__name__)


class LulustreamConfig:
    """Configuration for Lulustream module"""

    API_KEY = os.environ.get("LULUSTREAM_API_KEY", "")

    # Source channel where you upload posts (with links)
    SOURCE_CHANNEL_ID = int(os.environ.get("SOURCE_CHANNEL_ID", "0"))

    # Adult channel where Lulu links will be posted
    ADULT_CHANNEL_ID = int(os.environ.get("ADULT_CHANNEL_ID", "0"))

    AUTO_UPLOAD = os.environ.get("AUTO_LULUSTREAM", "True").lower() == "true"
    DEFAULT_TAGS = os.environ.get("LULU_TAGS", "tamil,adult,movies,hd")
    UPLOAD_FOLDER_ID = os.environ.get("LULU_FOLDER_ID", "")


class LulustreamUploader:
    """Handles all Lulustream upload operations via URL API"""

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
        public: bool = True,
    ) -> Dict:
        """Upload video to Lulustream using direct URL (remote upload)."""
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
            logger.info(f"📹 Video URL: {video_url[:80]}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    params=params,
                    data=payload,
                    timeout=aiohttp.ClientTimeout(total=self.upload_timeout),
                ) as response:
                    text = await response.text()
                    logger.info(f"Lulustream response: {text[:300]}")

                    if response.status != 200:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}: {text}",
                        }

                    try:
                        data = await response.json()
                    except Exception:
                        data = {"result": text}

                    if data.get("msg") == "OK" or data.get("status") == 200:
                        file_code = data.get("filecode") or data.get("file_code")
                        if file_code:
                            return {
                                "success": True,
                                "file_code": file_code,
                                "watch_url": f"https://lulustream.com/{file_code}",
                                "embed_url": f"https://lulustream.com/e/{file_code}",
                                "download_url": f"https://lulustream.com/d/{file_code}",
                                "title": title,
                                "tags": payload.get("tags", ""),
                            }

                    return {
                        "success": False,
                        "error": data.get("result", "Upload failed"),
                    }

        except asyncio.TimeoutError:
            return {"success": False, "error": "Upload timeout"}
        except Exception as e:
            logger.error(f"Lulustream upload exception: {e}")
            return {"success": False, "error": str(e)}

    async def get_video_info(self, file_code: str) -> Dict:
        """(Optional) Get video info – not heavily used."""
        try:
            url = "https://lulustream.com/api/file/info"
            params = {"key": self.api_key, "file_code": file_code}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
            return {}
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return {}


class LulustreamTelegramBot:
    """Telegram integration wrapper"""

    def __init__(self, bot):
        self.bot = bot
        self.uploader = LulustreamUploader()

    async def auto_upload_and_post(
        self,
        video_url: str,
        title: str,
        thumbnail: str = None,
        caption: str = None,
    ) -> Dict:
        """Auto-upload video via URL and post direct link to adult channel."""
        if not LulustreamConfig.AUTO_UPLOAD:
            return {"success": False, "error": "Auto-upload disabled"}

        if not LulustreamConfig.API_KEY:
            return {"success": False, "error": "API key not configured"}

        result = await self.uploader.upload_by_url(
            video_url=video_url, title=title, is_adult=True
        )

        if result["success"]:
            await self.post_to_adult_channel(
                result=result, thumbnail=thumbnail, caption=caption, download_url=video_url
            )

        return result

    async def post_to_adult_channel(
        self,
        result: Dict,
        thumbnail: str = None,
        caption: str = None,
        download_url: str = None,
    ):
        """Post DIRECT Lulu link to adult channel."""
        if not LulustreamConfig.ADULT_CHANNEL_ID:
            logger.warning("Adult channel ID not set")
            return

        text = f"🔞 **{result['title']}**\n\n🎬 **Watch Here:** {result['watch_url']}\n"

        if download_url:
            text += f"\n📥 **Source:** {download_url}\n"

        # Optional extra caption lines without extra links
        if caption:
            safe_lines = [
                line
                for line in caption.split("\n")
                if not line.strip().startswith("http")
            ]
            if safe_lines:
                text += "\n" + "\n".join(safe_lines[:3]) + "\n"

        text += "\n⚠️ **Adults Only | 18+**\n"
        text += f"🏷️ {result.get('tags', 'adult')}\n"

        buttons = InlineKeyboardMarkup(
            [[InlineKeyboardButton("▶️ Watch Now", url=result["watch_url"])]]
        )

        if thumbnail:
            await self.bot.send_photo(
                chat_id=LulustreamConfig.ADULT_CHANNEL_ID,
                photo=thumbnail,
                caption=text,
                reply_markup=buttons,
                parse_mode="Markdown",
            )
        else:
            await self.bot.send_message(
                chat_id=LulustreamConfig.ADULT_CHANNEL_ID,
                text=text,
                reply_markup=buttons,
                parse_mode="Markdown",
            )


# Global instance
_lulu_bot: LulustreamTelegramBot | None = None


def init_lulustream_telegram(bot):
    """Initialize global Lulu bot instance."""
    global _lulu_bot
    _lulu_bot = LulustreamTelegramBot(bot)
    logger.info("🎬 Lulustream Telegram module initialized")
    logger.info(f"   📺 Source Channel: {LulustreamConfig.SOURCE_CHANNEL_ID}")
    logger.info(f"   🔞 Adult Channel: {LulustreamConfig.ADULT_CHANNEL_ID}")
    logger.info(
        f"   ⚙️ Auto-Upload: {'✅ Enabled' if LulustreamConfig.AUTO_UPLOAD else '❌ Disabled'}"
    )
    return _lulu_bot


def get_lulustream_uploader():
    return _lulu_bot


# ============= SOURCE CHANNEL MONITOR =============


def _extract_url_from_caption(caption: str) -> str | None:
    """Find first reasonable URL in caption."""
    if not caption:
        return None

    for line in caption.split("\n"):
        if "http" not in line.lower():
            continue
        for word in line.split():
            if word.startswith("http"):
                url = word.strip()
                # Skip telegram / youtube links
                if any(bad in url.lower() for bad in ["t.me", "telegram", "youtube.com"]):
                    continue
                return url
    return None


async def monitor_source_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered on channel_post from SOURCE_CHANNEL_ID."""
    try:
        msg = update.channel_post
        if not msg:
            return

        if msg.chat.id != LulustreamConfig.SOURCE_CHANNEL_ID:
            return

        if not LulustreamConfig.AUTO_UPLOAD:
            return

        video = msg.video or msg.document
        if not video:
            return

        caption = msg.caption or "Untitled Video"
        title = caption.split("\n")[0] if caption else "Untitled Video"
        title = re.sub(r"[^\w\s\-()]", "", title)[:100]

        thumb_id = video.thumbnail.file_id if video.thumbnail else None

        direct_link = _extract_url_from_caption(caption)

        if not direct_link:
            logger.warning(
                "No usable URL found in caption. Skipping Lulustream upload."
            )
            return

        logger.info(f"Source post detected, URL: {direct_link[:80]}")

        lulu = get_lulustream_uploader()
        if not lulu:
            logger.error("Lulustream bot not initialized")
            return

        status_msg = await context.bot.send_message(
            chat_id=LulustreamConfig.SOURCE_CHANNEL_ID,
            text=f"⏳ Uploading to Lulustream: {title}",
            reply_to_message_id=msg.message_id,
        )

        result = await lulu.auto_upload_and_post(
            video_url=direct_link, title=title, thumbnail=thumb_id, caption=caption
        )

        if result.get("success"):
            await status_msg.edit_text(
                f"✅ Lulustream upload done!\n🎬 {result['watch_url']}"
            )
        else:
            await status_msg.edit_text(
                f"❌ Lulustream upload failed.\nError: {result.get('error')}"
            )

    except Exception as e:
        logger.error(f"Error in monitor_source_channel: {e}")


def get_source_channel_handler():
    """Return handler for channel monitor (or None if not configured)."""
    if not LulustreamConfig.SOURCE_CHANNEL_ID:
        logger.warning("SOURCE_CHANNEL_ID not set, monitor disabled")
        return None

    return MessageHandler(
        filters.Chat(LulustreamConfig.SOURCE_CHANNEL_ID)
        & filters.ChatType.CHANNEL
        & (filters.VIDEO | filters.Document.ALL),
        monitor_source_channel,
    )


# ============= COMMAND HANDLERS =============


async def handle_lulu_upload_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Manual: /uploadlulu <url> [title]"""
    if not update.message:
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "**Usage:** `/uploadlulu <direct_url> [title]`",
            parse_mode="Markdown",
        )
        return

    url = args[0]
    title = " ".join(args[1:]) if len(args) > 1 else "Untitled Video"

    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("❌ Invalid URL")
        return

    status = await update.message.reply_text(
        f"⏳ Uploading to Lulustream...\n`{title}`", parse_mode="Markdown"
    )

    uploader = LulustreamUploader()
    result = await uploader.upload_by_url(video_url=url, title=title, is_adult=True)

    if result.get("success"):
        buttons = InlineKeyboardMarkup(
            [[InlineKeyboardButton("▶️ Watch Now", url=result["watch_url"])]]
        )
        await status.edit_text(
            f"✅ **Upload Successful!**\n\n"
            f"📝 `{title}`\n"
            f"🎬 `{result['watch_url']}`",
            reply_markup=buttons,
            parse_mode="Markdown",
        )
    else:
        await status.edit_text(
            f"❌ Failed: `{result.get('error')}`", parse_mode="Markdown"
        )


async def handle_lulu_info_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "**Usage:** `/luluinfo <file_code>`", parse_mode="Markdown"
        )
        return

    code = args[0]
    await update.message.reply_text(
        f"🎬 `https://lulustream.com/{code}`", parse_mode="Markdown"
    )


async def handle_lulu_toggle_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return

    LulustreamConfig.AUTO_UPLOAD = not LulustreamConfig.AUTO_UPLOAD
    status = "✅ Enabled" if LulustreamConfig.AUTO_UPLOAD else "❌ Disabled"
    await update.message.reply_text(
        f"Auto Lulustream Upload: **{status}**", parse_mode="Markdown"
    )


async def handle_lulu_help_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return

    txt = f"""
**🎬 Lulustream Module (Direct Link Only)**

`/uploadlulu <url> [title]` – Manual upload  
`/luluinfo <file_code>` – Show Lulu link  
`/togglelulu` – Enable/Disable auto upload  
`/luluhelp` – This help  

Source channel: `{LulustreamConfig.SOURCE_CHANNEL_ID}`  
Adult channel: `{LulustreamConfig.ADULT_CHANNEL_ID}`  

Flow:
1. You post adult video post in **source channel** with download link.  
2. Bot uploads via Lulustream *remote URL API*.  
3. Direct Lulu link posts in **adult channel** with 18+ warning.
"""
    await update.message.reply_text(txt, parse_mode="Markdown")
        
