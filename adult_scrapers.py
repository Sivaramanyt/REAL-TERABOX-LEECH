"""
FREE scrapers for xVideos and XNXX

No paid APIs - only free libraries
"""

import logging
import random
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Try to import free scrapers
try:
    from xvideos import XVideos
    XVIDEOS_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ xvideos-py not installed. Install: pip install xvideos-py")
    XVIDEOS_AVAILABLE = False

try:
    # Note: This might need to be installed separately
    # pip install xnxx-scraper (check GitHub for actual package name)
    from xnxx_scraper import XNXX
    XNXX_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ xnxx-scraper not available")
    XNXX_AVAILABLE = False

from adult_config import ILLEGAL_KEYWORDS, INDIAN_KEYWORDS, MIN_VIEWS


def is_illegal_content(title: str, tags: List[str] = []) -> bool:
    """
    Check if content contains illegal keywords.
    Returns True if ILLEGAL (should be blocked).
    """
    text = f"{title} {' '.join(tags)}".lower()
    for keyword in ILLEGAL_KEYWORDS:
        if keyword in text:
            logger.warning(f"🚫 Blocked illegal keyword '{keyword}' in: {title[:60]}")
            return True
    return False


def is_indian_content(title: str, tags: List[str] = []) -> bool:
    """Check if content is Indian-related."""
    text = f"{title} {' '.join(tags)}".lower()
    indian_markers = [
        "indian", "desi", "hindi", "tamil", "telugu",
        "malayalam", "punjabi", "mumbai", "delhi",
        "bangalore", "mms", "leaked",
    ]
    return any(marker in text for marker in indian_markers)


async def scrape_xvideos(keyword: str, min_views: int = MIN_VIEWS) -> List[Dict]:
    """
    Scrape xVideos for Indian content (FREE).

    Allows all quality: HD, SD, recorded, amateur.
    """
    if not XVIDEOS_AVAILABLE:
        logger.error("❌ xVideos scraper not available")
        return []

    try:
        logger.info(f"🔍 Scraping xVideos for: {keyword}")
        xv = XVideos()

        # IMPORTANT: use correct parameter names for xvideos-py
        # Older code used query= which caused:
        # XVideos.search() got an unexpected keyword argument 'query'
        results = xv.search(k=keyword, sort="views")  # fixed call [web:260][file:253]

        videos: List[Dict] = []
        blocked = 0

        # xvideos-py typically returns a dict with 'videos' key
        for video in results.get("videos", [])[:20]:
            # Safety check FIRST
            if is_illegal_content(video["title"], video.get("tags", [])):
                blocked += 1
                continue

            # Views filter
            if video.get("views", 0) < min_views:
                continue

            # Must be Indian content
            if not is_indian_content(video["title"], video.get("tags", [])):
                continue

            try:
                # Try to get full video details
                try:
                    video_info = xv.details(video["url"])
                except AttributeError:
                    # Fallback if library exposes get_video()
                    video_info = xv.get_video(video["url"])

                # Final safety check
                if is_illegal_content(
                    video_info.get("title", video["title"]),
                    video_info.get("tags", []),
                ):
                    blocked += 1
                    continue

                # Extract a usable download URL
                download_url: Optional[str] = video_info.get("download_url")

                if not download_url:
                    files = video_info.get("files", {}) or {}
                    if isinstance(files, dict) and files:
                        # Prefer higher quality if available
                        download_url = (
                            files.get("high")
                            or files.get("hd")
                            or files.get("low")
                            or next(iter(files.values()), "")
                        )

                if not download_url:
                    # Skip entries without a direct file URL
                    logger.debug(
                        f"⚠️ Skipped (no download URL): {video_info.get('title', '')[:60]}"
                    )
                    continue

                videos.append(
                    {
                        "source": "xVideos",
                        "title": video_info.get("title", video["title"]),
                        "url": video["url"],
                        "download_url": download_url,
                        "thumbnail": video_info.get(
                            "thumbnail", video_info.get("image", "")
                        ),
                        "duration": video_info.get("duration", "0:00"),
                        "views": video.get("views", 0),
                        "tags": video_info.get("tags", []),
                    }
                )
            except Exception as e:
                logger.debug(f"⚠️ Skipped video: {e}")
                continue

        logger.info(
            f"✅ xVideos: Found {len(videos)} safe videos, blocked {blocked}"
        )
        return videos[:5]  # Return top 5

    except Exception as e:
        logger.error(f"❌ xVideos scraping error: {e}")
        return []


async def scrape_xnxx(keyword: str, min_views: int = MIN_VIEWS) -> List[Dict]:
    """
    Scrape XNXX for Indian content (FREE).
    """
    if not XNXX_AVAILABLE:
        logger.warning("⚠️ XNXX scraper not available")
        return []

    try:
        logger.info(f"🔍 Scraping XNXX for: {keyword}")
        xnxx = XNXX()

        results = xnxx.search(keyword, sort="views")
        videos: List[Dict] = []
        blocked = 0

        for video in results[:20]:
            # Safety check
            if is_illegal_content(video["title"], video.get("tags", [])):
                blocked += 1
                continue

            # Views filter
            if video.get("views", 0) < min_views:
                continue

            # Indian content check
            if not is_indian_content(video["title"], video.get("tags", [])):
                continue

            try:
                video_info = xnxx.get_video(video["url"])

                if is_illegal_content(
                    video_info.get("title", video["title"]),
                    video_info.get("tags", []),
                ):
                    blocked += 1
                    continue

                videos.append(
                    {
                        "source": "XNXX",
                        "title": video_info.get("title", video["title"]),
                        "url": video["url"],
                        "download_url": video_info.get("download_url", ""),
                        "thumbnail": video_info.get("thumbnail", ""),
                        "duration": video_info.get("duration", "0:00"),
                        "views": video.get("views", 0),
                        "tags": video_info.get("tags", []),
                    }
                )
            except Exception:
                continue

        logger.info(
            f"✅ XNXX: Found {len(videos)} safe videos, blocked {blocked}"
        )
        return videos[:5]

    except Exception as e:
        logger.error(f"❌ XNXX scraping error: {e}")
        return []


async def scrape_all_sites(keyword: str = None) -> List[Dict]:
    """
    Scrape all available sites and return combined results.
    """
    if not keyword:
        keyword = random.choice(INDIAN_KEYWORDS)

    logger.info(f"🔎 Multi-site scrape with keyword: {keyword}")

    all_videos: List[Dict] = []

    # Scrape xVideos
    if XVIDEOS_AVAILABLE:
        xv_videos = await scrape_xvideos(keyword)
        all_videos.extend(xv_videos)

    # Scrape XNXX
    if XNXX_AVAILABLE:
        xnxx_videos = await scrape_xnxx(keyword)
        all_videos.extend(xnxx_videos)

    # Sort by views (highest first)
    all_videos.sort(key=lambda x: x.get("views", 0), reverse=True)

    logger.info(f"📊 Total videos found: {len(all_videos)}")
    return all_videos


def format_views(views: int) -> str:
    """Format view count: 1.2M, 500K, etc."""
    if views >= 1_000_000:
        return f"{views / 1_000_000:.1f}M"
    if views >= 1_000:
        return f"{views / 1_000:.0f}K"
    return str(views)
            
