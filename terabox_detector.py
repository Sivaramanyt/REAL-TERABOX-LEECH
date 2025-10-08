"""
Terabox Link Detector - Automatically detects Terabox links in messages
"""
import re

TERABOX_PATTERNS = [
    r'https?://(?:www\.)?terabox\.com/s/[A-Za-z0-9_-]+',
    r'https?://(?:www\.)?1024tera\.com/s/[A-Za-z0-9_-]+',
    r'https?://(?:www\.)?4funbox\.com/s/[A-Za-z0-9_-]+',
    r'https?://(?:www\.)?teraboxapp\.com/s/[A-Za-z0-9_-]+',
    r'https?://(?:www\.)?terabox\.app/s/[A-Za-z0-9_-]+',
]

def is_terabox_link(text):
    """Check if text contains Terabox link"""
    if not text:
        return False
    for pattern in TERABOX_PATTERNS:
        if re.search(pattern, text):
            return True
    return False

def extract_terabox_links(text):
    """Extract all Terabox links from text"""
    links = []
    if not text:
        return links
    for pattern in TERABOX_PATTERNS:
        matches = re.findall(pattern, text)
        links.extend(matches)
    return list(set(links))  # Remove duplicates

def clean_terabox_link(link):
    """Clean and normalize Terabox link"""
    # Remove unnecessary parameters
    link = link.split('?')[0]  # Remove query parameters
    link = link.split('#')[0]  # Remove fragments
    return link.strip()
