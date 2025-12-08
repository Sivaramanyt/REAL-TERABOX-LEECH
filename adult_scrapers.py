"""
FREE scrapers for xVideos and xHamster

No paid APIs - only free libraries.
"""

import logging
import random
from typing import List, Dict, Optional, Any

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# xVideos library (installed via xvideos-py)
try:
    from xvideos import XVideos
    XVIDEOS_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ xvideos-py not installed. Install: pip install xvideos-py")
    XVIDEOS_AVAILABLE = False

# xHamster uses plain HTML scraping
XHAMSTER_AVAILABLE = True

from adult_config import ILLEGAL_KEYWORDS, INDIAN_KEYWORDS  # MIN_VIEWS no longer used


def parse_views(raw: Any) -> int:
    """
    Convert various view formats to an int for display only.
    NOT used for filtering or sorting.
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
    Check if content contains ILLEGAL keywords.

    This is the ONLY filter applied (no view / region filters).
    """
    text = f"{title} {' '.join(tags)}".lower()
    for keyword in ILLEGAL_KEYWORDS:
        if keyword in text:
            logger.warning(f"🚫 Blocked illegal keyword '{keyword}' in: {title[:60]}")
            return True
    return False


# -------------------- xVideos scraper --------------------


async def scrape_xvideos(keyword: str) -> List[Dict]:
    """
    Scrape xVideos for content (FREE).

    No view-based filtering; only blocks illegal keywords.
    """
    if not XVIDEOS_AVAILABLE:
        logger.error("❌ xVideos scraper not available")
        return []

    try:
        logger.info(f"🔍 Scraping xVideos for: {keyword}")
        xv = XVideos()

        # Correct arguments for xvideos-py
        results = xv.search(k=keyword, sort="views")

        videos: List[Dict] = []
        blocked = 0

        for video in results.get("videos", [])[:20]:
            # Basic fields from search result
            base_title = video.get("title", "").strip()
            base_tags = video.get("tags", [])

            if not base_title:
                continue

            # First safety check
            if is_illegal_content(base_title, base_tags):
                blocked += 1
                continue

            try:
                # Try to get full video details
                try:
                    video_info = xv.details(video["url"])
                except AttributeError:
                    video_info = xv.get_video(video["url"])

                final_title = video_info.get("title", base_title)
                final_tags = video_info.get("tags", base_tags)

                # Final safety check
                if is_illegal_content(final_title, final_tags):
                    blocked += 1
                    continue

                # Download URL (for LuluStream remote upload)
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
                        f"⚠️ xVideos: Skipped (no download URL): {final_title[:60]}"
                    )
                    continue

                views_int = parse_views(video.get("views", 0))

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
                logger.debug(f"⚠️ xVideos: skipped video due to error: {e}")
                continue

        logger.info(
            f"✅ xVideos: Found {len(videos)} safe videos, blocked {blocked}"
        )
        # Limit to first 5 to avoid spamming; no view-based sorting/filtering.
        return videos[:5]

    except Exception as e:
        logger.error(f"❌ xVideos scraping error: {e}")
        return []


# -------------------- xHamster scraper --------------------


async def scrape_xhamster(keyword: str) -> List[Dict]:
    """
    Scrape xHamster search results (HTML).

    No view-based filtering; only blocks illegal keywords.
    """
    if not XHAMSTER_AVAILABLE:
        logger.warning("⚠️ xHamster scraper disabled")
        return []

    search_query = keyword.replace(" ", "+")
    url = f"https://xhamster.desi/search/{search_query}"

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

        # Generic selectors – layout can change; this is best-effort
        cards = soup.select("a.video-thumb, a.thumb-image, div.video-item a")[:30]
        if not cards:
            logger.warning("⚠️ xHamster: no cards found on page")
            return []

        for card in cards:
            try:
                title = (card.get("title") or card.get("aria-label") or "").strip()
                if not title:
                    title_el = card.select_one(".video-title, .thumb-title")
                    title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                href = card.get("href") or ""
                if not href.startswith("http"):
                    href = "https://xhamster.desi" + href

                thumb = (
                    card.get("data-src")
                    or card.get("data-thumb")
                    or card.get("src")
                    or ""
                )

                duration = "0:00"
                duration_el = card.select_one(
                    ".video-thumb__duration, .thumb-duration, .time"
                )
                if duration_el:
                    duration = duration_el.get_text(strip=True)

                # Views only for display; not for filtering
                views_int = 0
                views_el = card.select_one(
                    ".video-thumb__views, .thumb-views, .views"
                )
                if views_el:
                    views_int = parse_views(views_el.get_text(strip=True))

                # Only illegal filter
                if is_illegal_content(title, []):
                    blocked += 1
                    continue

                videos.append(
                    {
                        "source": "xHamster",
                        "title": title,
                        "url": href,
                        # LuluStream remote upload can use the page URL
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


# -------------------- Multi-site helper --------------------


async def scrape_all_sites(keyword: str = None) -> List[Dict]:
    """
    Scrape all available sites and return combined results.

    - If keyword is None, chooses randomly from INDIAN_KEYWORDS defined in adult_config:
      e.g. ["indian", "india", "desi", "tamil sex video", "desi sex video"]. [file:247]
    - No view-based filtering or sorting.
    """
    if not keyword:
        keyword = random.choice(INDIAN_KEYWORDS)

    logger.info(f"🔎 Multi-site scrape with keyword: {keyword}")

    all_videos: List[Dict] = []

    if XVIDEOS_AVAILABLE:
        xv_videos = await scrape_xvideos(keyword)
        all_videos.extend(xv_videos)

    if XHAMSTER_AVAILABLE:
        xh_videos = await scrape_xhamster(keyword)
        all_videos.extend(xh_videos)

    logger.info(f"📊 Total videos found: {len(all_videos)}")
    return all_videos


def format_views(views: int) -> str:
    """
    Format view count for captions: 1.2M, 500K, etc.

    adult_automation.py uses this when building the Telegram caption. [file:248]
    """
    if views >= 1_000_000:
        return f"{views / 1_000_000:.1f}M"
    if views >= 1_000:
        return f"{views / 1_000:.0f}K"
    return str(views)
