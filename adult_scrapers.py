"""
FREE scraper for Indian adult videos using xHamster category feed.

No paid APIs - only free libraries.
"""

import logging
from typing import List, Dict, Optional, Any

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# xVideos (temporary disabled, too unstable on server)
try:
    from xvideos import XVideos  # noqa: F401
    XVIDEOS_AVAILABLE = False  # force disabled for now
except ImportError:
    logger.warning("⚠️ xvideos-py not installed. xVideos scraper disabled.")
    XVIDEOS_AVAILABLE = False

# xHamster scraper using plain HTML
XHAMSTER_AVAILABLE = True

from adult_config import ILLEGAL_KEYWORDS  # keep only safety list


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


# -------------------- xHamster Indian category scraper --------------------


async def scrape_xhamster() -> List[Dict]:
    """
    Scrape xHamster Indian category page.

    Uses: https://xhamster.com/categories/indian/best
    No keyword, no view-based filtering; only blocks illegal keywords.
    """
    if not XHAMSTER_AVAILABLE:
        logger.warning("⚠️ xHamster scraper disabled")
        return []

    # Stable Indian category feed. [web:291][web:292]
    url = "https://xhamster.com/categories/indian/best"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }

    videos: List[Dict] = []
    blocked = 0

    try:
        logger.info("🔍 Scraping xHamster Indian category feed")
        timeout = aiohttp.ClientTimeout(total=20)

        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.error(f"❌ xHamster HTTP error: {resp.status}")
                    return []

                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")

        # Best-effort selectors for video cards; layout can change.
        # Try multiple patterns to reduce "no cards found" issues.
        cards = []

        cards.extend(soup.select("a.video-thumb"))
        cards.extend(soup.select("a.thumb-image"))
        cards.extend(soup.select("article video a"))
        cards.extend(soup.select("div.video-item a"))

        # Deduplicate while preserving order
        seen = set()
        unique_cards = []
        for c in cards:
            key = (c.get("href"), c.get("title"))
            if key in seen:
                continue
            seen.add(key)
            unique_cards.append(c)

        unique_cards = unique_cards[:30]

        if not unique_cards:
            logger.warning("⚠️ xHamster: no cards found on Indian category page")
            return []

        for card in unique_cards:
            try:
                title = (card.get("title") or card.get("aria-label") or "").strip()
                if not title:
                    title_el = card.select_one(".video-title, .thumb-title")
                    title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                href = card.get("href") or ""
                if not href.startswith("http"):
                    href = "https://xhamster.com" + href

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

                # Views only for caption display
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
                        # LuluStream remote upload can use the page URL directly
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
        # Limit to first 5 to avoid flooding; no sorting/filtering by views.
        return videos[:5]

    except Exception as e:
        logger.error(f"❌ xHamster scraping error: {e}")
        return []


# -------------------- Multi-site wrapper --------------------


async def scrape_all_sites(keyword: str = None) -> List[Dict]:
    """
    Scrape all available sites and return combined results.

    Currently only xHamster Indian category is used.
    Keyword is ignored (kept only for backward compatibility with callers).
    """
    logger.info("🔎 Multi-site scrape (xHamster Indian category only)")
    all_videos: List[Dict] = []

    if XHAMSTER_AVAILABLE:
        xh_videos = await scrape_xhamster()
        all_videos.extend(xh_videos)

    logger.info(f"📊 Total videos found: {len(all_videos)}")
    return all_videos


def format_views(views: int) -> str:
    """
    Format view count for captions: 1.2M, 500K, etc.
    adult_automation.py uses this when building the Telegram caption.
    """
    if views >= 1_000_000:
        return f"{views / 1_000_000:.1f}M"
    if views >= 1_000:
        return f"{views / 1_000:.0f}K"
    return str(views)
                  
