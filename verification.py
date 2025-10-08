"""
Shortlink verification system (adapted from FileStoreBot-Token)
"""

import string
import random
import requests
import logging
from config import SHORTLINK_API, SHORTLINK_URL

logger = logging.getLogger(__name__)

def generate_verify_token(length=16):
    """Generate random verification token"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def create_shortlink(url):
    """Create shortlink using API"""
    try:
        payload = {
            'api': SHORTLINK_API,
            'url': url
        }
        
        response = requests.get(SHORTLINK_URL, params=payload, timeout=10)
        data = response.json()
        
        if data.get('status') == 'success':
            return data.get('shortenedUrl')
        else:
            logger.error(f"Shortlink API error: {data}")
            return None
            
    except Exception as e:
        logger.error(f"Error creating shortlink: {e}")
        return None

def generate_verification_link(bot_username, token):
    """Generate verification link with shortlink"""
    try:
        # Create direct verification URL
        verify_url = f"https://t.me/{bot_username}?start=verify_{token}"
        
        # Create shortlink
        short_url = create_shortlink(verify_url)
        
        if short_url:
            return short_url
        else:
            # Fallback to direct URL if shortlink fails
            return verify_url
            
    except Exception as e:
        logger.error(f"Error generating verification link: {e}")
        return None

def extract_token_from_start(text):
    """Extract verification token from /start command"""
    try:
        if text.startswith("verify_"):
            return text.split("verify_")[1]
        return None
    except Exception as e:
        logger.error(f"Error extracting token: {e}")
        return None
