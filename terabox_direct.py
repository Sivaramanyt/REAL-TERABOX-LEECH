"""
terabox_direct.py - Direct Terabox Leech WITHOUT Third-Party APIs
Works alongside your existing terabox_api.py (no conflicts)
Uses: terabox-downloader library (direct scraping)
Compatible: Koyeb free tier (streaming approach)
"""

import os
import time
import logging
import asyncio
import tempfile
import aiohttp
from typing import Optional, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest, TimedOut, NetworkError

# Import terabox-downloader library (NO API!)
try:
    from terabox import TeraboxDL
    TERABOX_DIRECT_AVAILABLE = True
except ImportError:
    TERABOX_DIRECT_AVAILABLE = False

logger = logging.getLogger(__name__)

# Koyeb free tier safe limits
MAX_FILE_SIZE_BYTES = 400 * 1024 * 1024  # 400MB safe for Koyeb free tier
TELEGRAM_MAX_SIZE = 2 * 1024 * 1024 * 1024  # 2GB Telegram limit
SMALL_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB - download to RAM
CHUNK_SIZE = 1024 * 1024  # 1MB chunks for streaming


class TeraboxDirectLeech:
    """Direct Terabox leecher - NO third-party APIs"""
    
    def __init__(self):
        if not TERABOX_DIRECT_AVAILABLE:
            raise ImportError("terabox-downloader not installed")
        self.terabox = TeraboxDL()
        self.active_downloads = {}  # Track active downloads for cancellation
    
    def format_size(self, bytes_size: int) -> str:
        """Format bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} TB"
    
    def format_time(self, seconds: float) -> str:
        """Format seconds to human readable"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"
    
    async def update_progress(self, message, current: int, total: int, 
                            start_time: float, status: str = "Downloading"):
        """Update progress message"""
        try:
            now = time.time()
            elapsed = now - start_time
            
            if elapsed < 2:  # Don't update too frequently
                return
            
            percentage = (current * 100) / total
            speed = current / elapsed if elapsed > 0 else 0
            eta = (total - current) / speed if speed > 0 else 0
            
            # Progress bar
            filled = int(percentage // 10)
            bar = '█' * filled + '░' * (10 - filled)
            
            text = (
                f"**{status}**\n\n"
                f"`{bar}` {percentage:.1f}%\n\n"
                f"📦 Size: {self.format_size(current)} / {self.format_size(total)}\n"
                f"⚡ Speed: {self.format_size(speed)}/s\n"
                f"⏱️ ETA: {self.format_time(eta)}"
            )
            
            await message.edit_text(text, parse_mode='Markdown')
            
        except (BadRequest, TimedOut):
            pass  # Ignore telegram errors during progress update
        except Exception as e:
            logger.debug(f"Progress update error: {e}")
    
    async def download_small_file(self, url: str, file_name: str, 
                                  file_size: int, message, context) -> Optional[str]:
        """Download small files (<100MB) directly to memory"""
        try:
            start_time = time.time()
            last_update = 0
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None
                    
                    # Download to memory
                    chunks = []
                    downloaded = 0
                    
                    async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                        chunks.append(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress every 2 seconds
                        if time.time() - last_update > 2:
                            await self.update_progress(
                                message, downloaded, file_size, start_time, "📥 Downloading"
                            )
                            last_update = time.time()
                    
                    # Combine chunks
                    file_data = b''.join(chunks)
                    logger.info(f"Downloaded {self.format_size(len(file_data))} to memory")
                    return file_data
                    
        except Exception as e:
            logger.error(f"Small file download error: {e}")
            return None
    
    async def download_large_file(self, url: str, file_name: str, 
                                  file_size: int, message, context) -> Optional[str]:
        """Download large files (100-400MB) to temp file"""
        temp_path = None
        try:
            start_time = time.time()
            last_update = 0
            
            # Create temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_name}") as tmp:
                temp_path = tmp.name
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            return None
                        
                        downloaded = 0
                        
                        async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                            tmp.write(chunk)
                            downloaded += len(chunk)
                            
                            # Update progress every 2 seconds
                            if time.time() - last_update > 2:
                                await self.update_progress(
                                    message, downloaded, file_size, start_time, "📥 Downloading"
                                )
                                last_update = time.time()
                
                logger.info(f"Downloaded {self.format_size(downloaded)} to {temp_path}")
                return temp_path
                
        except Exception as e:
            logger.error(f"Large file download error: {e}")
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            return None
    
    async def upload_to_telegram(self, chat_id: int, file_data, file_name: str, 
                                file_size: int, message, context) -> bool:
        """Upload file to Telegram"""
        try:
            await message.edit_text("📤 **Uploading to Telegram...**", parse_mode='Markdown')
            
            # Determine if video or document
            is_video = file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm'))
            
            # Upload
            if isinstance(file_data, bytes):
                # Small file from memory
                if is_video:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=file_data,
                        filename=file_name,
                        caption=f"✅ **Leeched from Terabox (Direct)**\n\n"
                                f"📁 {file_name}\n"
                                f"📦 Size: {self.format_size(file_size)}",
                        parse_mode='Markdown'
                    )
                else:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=file_data,
                        filename=file_name,
                        caption=f"✅ **Leeched from Terabox (Direct)**\n\n"
                                f"📁 {file_name}\n"
                                f"📦 Size: {self.format_size(file_size)}",
                        parse_mode='Markdown'
                    )
            else:
                # Large file from temp path
                with open(file_data, 'rb') as f:
                    if is_video:
                        await context.bot.send_video(
                            chat_id=chat_id,
                            video=f,
                            filename=file_name,
                            caption=f"✅ **Leeched from Terabox (Direct)**\n\n"
                                    f"📁 {file_name}\n"
                                    f"📦 Size: {self.format_size(file_size)}",
                            parse_mode='Markdown'
                        )
                    else:
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=f,
                            filename=file_name,
                            caption=f"✅ **Leeched from Terabox (Direct)**\n\n"
                                    f"📁 {file_name}\n"
                                    f"📦 Size: {self.format_size(file_size)}",
                            parse_mode='Markdown'
                        )
                
                # Clean up temp file
                if os.path.exists(file_data):
                    os.remove(file_data)
                    logger.info(f"Cleaned up temp file: {file_data}")
            
            return True
            
        except Exception as e:
            logger.error(f"Upload error: {e}")
            # Clean up on error
            if isinstance(file_data, str) and os.path.exists(file_data):
                os.remove(file_data)
            return False
    
    async def leech(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                   terabox_url: str) -> bool:
        """
        Main leech function - Direct download from Terabox
        Returns: True if successful, False if failed
        """
        message = update.message
        chat_id = message.chat_id
        user_id = message.from_user.id
        
        try:
            # Get file info
            status = await message.reply_text("🔍 **Getting file info...**", parse_mode='Markdown')
            
            file_info = self.terabox.get_file_info(terabox_url)
            
            if not file_info:
                await status.edit_text("❌ **Invalid Terabox link or file removed**", parse_mode='Markdown')
                return False
            
            # Extract details
            file_name = file_info.get('file_name', 'unknown')
            download_link = file_info.get('download_link')
            file_size = file_info.get('file_size', 0)
            
            if not download_link:
                await status.edit_text("❌ **Could not get download link**", parse_mode='Markdown')
                return False
            
            # Check size limits
            if file_size > TELEGRAM_MAX_SIZE:
                await status.edit_text(
                    f"❌ **File too large**\n\n"
                    f"Size: {self.format_size(file_size)}\n"
                    f"Telegram limit: 2 GB",
                    parse_mode='Markdown'
                )
                return False
            
            if file_size > MAX_FILE_SIZE_BYTES:
                await status.edit_text(
                    f"⚠️ **File too large for Koyeb free tier**\n\n"
                    f"Size: {self.format_size(file_size)}\n"
                    f"Free tier safe limit: 400 MB\n\n"
                    f"💡 Try smaller files or upgrade hosting",
                    parse_mode='Markdown'
                )
                return False
            
            # Show file info
            await status.edit_text(
                f"📁 **File Found**\n\n"
                f"Name: `{file_name}`\n"
                f"Size: {self.format_size(file_size)}\n\n"
                f"⏳ Starting download...",
                parse_mode='Markdown'
            )
            
            # Download based on size
            if file_size < SMALL_FILE_THRESHOLD:
                # Small file - download to RAM
                file_data = await self.download_small_file(
                    download_link, file_name, file_size, status, context
                )
            else:
                # Large file - use temp file
                file_data = await self.download_large_file(
                    download_link, file_name, file_size, status, context
                )
            
            if not file_data:
                await status.edit_text("❌ **Download failed**", parse_mode='Markdown')
                return False
            
            # Upload to Telegram
            success = await self.upload_to_telegram(
                chat_id, file_data, file_name, file_size, status, context
            )
            
            if success:
                await status.delete()
                logger.info(f"✅ Successfully leeched: {file_name}")
                return True
            else:
                await status.edit_text("❌ **Upload failed**", parse_mode='Markdown')
                return False
            
        except Exception as e:
            logger.error(f"Leech error: {e}")
            try:
                await message.reply_text(f"❌ **Error:** {str(e)}", parse_mode='Markdown')
            except:
                pass
            return False


# Singleton instance
_direct_leecher = None

def get_direct_leecher() -> TeraboxDirectLeech:
    """Get or create direct leecher instance"""
    global _direct_leecher
    if _direct_leecher is None:
        _direct_leecher = TeraboxDirectLeech()
    return _direct_leecher


# Convenience function for easy integration
async def leech_terabox_direct(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               terabox_url: str) -> bool:
    """
    Quick function to leech Terabox files directly (NO API)
    
    Usage:
        from terabox_direct import leech_terabox_direct
        
        success = await leech_terabox_direct(update, context, terabox_url)
    """
    leecher = get_direct_leecher()
    return await leecher.leech(update, context, terabox_url)
