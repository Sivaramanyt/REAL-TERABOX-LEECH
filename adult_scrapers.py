"""
FREE scrapers for xVideos and XNXX

No paid APIs - only free libraries
"""

import logging
import random
from typing import List, Dict, Optional, Any
import aiohttp
from bs4 import BeautifulSoup

XHAMSTER_AVAILABLE = True  # simple HTML scraper, no extra package

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


def parse_views(raw: Any) -> int:
    """
    Convert views from library format to plain int.

    Handles:
    - int
    - "12,345"
    - "1.2M", "500K"
    """
    if isinstance(raw, int):
        return raw
    if raw is None:
        return 0

    s = str(raw).replace(",", "").strip().lower()
    if not s:
        return 0

    try:
        if s.endswith("m"):
            return int(float(s[:-1]) * 1_000_000)
        if s.endswith("k"):
            return int(float(s[:-1]) * 1_000)
        return int(float(s))
    except Exception:
        logger.debug(f"⚠️ Could not parse views '{raw}', defaulting to 0")
        return 0


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
        "indian",
        "desi",
        "hindi",
        "tamil",
        "telugu",
        "malayalam",
        "punjabi",
        "mumbai",
        "delhi",
        "bangalore",
        "mms",
        "leaked",
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

        # Correct parameter names for xvideos-py
        results = xv.search(k=keyword, sort="views")  # [web:260]

        videos: List[Dict] = []
        blocked = 0

        for video in results.get("videos", [])[:20]:
            raw_views = video.get("views", 0)
            views_int = parse_views(raw_views)

            # Safety check FIRST
            if is_illegal_content(video["title"], video.get("tags", [])):
                blocked += 1
                continue

            # Views filter (now int vs int ➜ no '<' TypeError)
            if views_int < min_views:
                continue

            # Must be Indian content
            if not is_indian_content(video["title"], video.get("tags", [])):
                continue

            try:
                # Try to get full video details
                try:
                    video_info = xv.details(video["url"])
                except AttributeError:
                    video_info = xv.get_video(video["url"])

                final_title = video_info.get("title", video["title"])
                final_tags = video_info.get("tags", [])

                # Final safety check
                if is_illegal_content(final_title, final_tags):
                    blocked += 1
                    continue

                # Extract a usable download URL
                download_url: Optional[str] = video_info.get("download_url")

                if not download_url:
                    files = video_info.get("files", {}) or {}
                    if isinstance(files, dict) and files:
                        download_url = (
                            files.get("high")
                            or files.get("hd")
                            or files.get("low")
                            or next(iter(files.values()), "")
                        )

                if not download_url:
                    logger.debug(
                        f"⚠️ Skipped (no download URL): {final_title[:60]}"
                    )
                    continue

                videos.append(
                    {
                        "source": "xVideos",
                        "title": final_title,
                        "url": video["url"],
                        "download_url": download_url,
                        "thumbnail": video_info.get(
                            "thumbnail", video_info.get("image", "")
                        ),
                        "duration": video_info.get("duration", "0:00"),
                        "views": views_int,
                        "tags": final_tags,
                    }
                )
            except Exception as e:
                logger.debug(f"⚠️ Skipped video: {e}")
                continue

        logger.info(
            f"✅ xVideos: Found {len(videos)} safe videos, blocked {blocked}"
        )
        return videos[:5]

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
            raw_views = video.get("views", 0)
            views_int = parse_views(raw_views)

            # Safety check
            if is_illegal_content(video["title"], video.get("tags", [])):
                blocked += 1
                continue

            # Views filter
            if views_int < min_views:
                continue

            # Indian content check
            if not is_indian_content(video["title"], video.get("tags", [])):
                continue

            try:
                video_info = xnxx.get_video(video["url"])
                final_title = video_info.get("title", video["title"])
                final_tags = video_info.get("tags", [])

                if is_illegal_content(final_title, final_tags):
                    blocked += 1
                    continue

                videos.append(
                    {
                        "source": "XNXX",
                        "title": final_title,
                        "url": video["url"],
                        "download_url": video_info.get("download_url", ""),
                        "thumbnail": video_info.get("thumbnail", ""),
                        "duration": video_info.get("duration", "0:00"),
                        "views": views_int,
                        "tags": final_tags,
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

async def scrape_xhamster(keyword: str, min_views: int = MIN_VIEWS) -> List[Dict]:
    """
    Scrape xHamster search results (HTML) for Indian content.

    This uses a simple HTML scraper, no official API.
    It looks at the public search page and extracts:
    - title
    - URL
    - thumbnail
    - duration
    - rough view count
    """
    if not XHAMSTER_AVAILABLE:
        logger.warning("⚠️ xHamster scraper disabled")
        return []

    search_query = keyword.replace(" ", "+")
    url = f"https://xhamster.desi/search/{search_query}"  # .desi mirror tends to be lighter

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }

    videos: List[Dict] = []
    blocked = 0

    try:
        logger.info(f"🔍 Scraping xHamster for: {keyword}")
        timeout = aiohttp.ClientTimeout(total=20)

        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.error(f"❌ xHamster HTTP error: {resp.status}")
                    return []

                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")

        # xHamster layout can change; this targets generic video cards
        cards = soup.select("a.video-thumb, a.thumb-image, div.video-item a")[:30]
        if not cards:
            logger.warning("⚠️ xHamster: no cards found on page")
            return []

        for card in cards:
            try:
                title = (card.get("title") or card.get("aria-label") or "").strip()
                if not title:
                    # Try child element
                    title_el = card.select_one(".video-title, .thumb-title")
                    title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                href = card.get("href") or ""
                if not href.startswith("http"):
                    href = "https://xhamster.desi" + href

                # Thumbnail
                thumb = (
                    card.get("data-src")
                    or card.get("data-thumb")
                    or card.get("src")
                    or ""
                )

                # Duration and views – very heuristic
                duration = "0:00"
                duration_el = card.select_one(
                    ".video-thumb__duration, .thumb-duration, .time"
                )
                if duration_el:
                    duration = duration_el.get_text(strip=True)

                views_int = 0
                views_el = card.select_one(
                    ".video-thumb__views, .thumb-views, .views"
                )
                if views_el:
                    views_int = parse_views(views_el.get_text(strip=True))

                # Safety + filters
                if is_illegal_content(title, []):
                    blocked += 1
                    continue
                if views_int < min_views:
                    continue
                if not is_indian_content(title, []):
                    continue

                videos.append(
                    {
                        "source": "xHamster",
                        "title": title,
                        "url": href,
                        # For LuluStream remote upload we just need a playable URL.
                        # xHamster pages contain the video; LuluStream will handle it.
                        "download_url": href,
                        "thumbnail": thumb,
                        "duration": duration,
                        "views": views_int,
                        "tags": [],
                    }
                )

            except Exception as e:
                logger.debug(f"⚠️ xHamster: skipped card due to error: {e}")
                continue

        logger.info(
            f"✅ xHamster: Found {len(videos)} safe videos, blocked {blocked}"
        )
        return videos[:5]

    except Exception as e:
        logger.error(f"❌ xHamster scraping error: {e}")
        return []
            
async def scrape_all_sites(keyword: str = None) -> List[Dict]:
    """
    Scrape all available sites and return combined results.
    """
    if not keyword:
        keyword = random.choice(INDIAN_KEYWORDS)

    logger.info(f"🔎 Multi-site scrape with keyword: {keyword}")

    all_videos: List[Dict] = []

    if XVIDEOS_AVAILABLE:
        xv_videos = await scrape_xvideos(keyword)
        all_videos.extend(xv_videos)

    if XNXX_AVAILABLE:
        xnxx_videos = await scrape_xnxx(keyword)
        all_videos.extend(xnxx_videos)

    # Sort by numeric views (we already store ints)
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
                
