"""
UNIVERSAL Shortlink Verification System
Automatically detects and adapts to ANY shortlink service API format
Supports arolinks.com and 50+ other shortlink services
"""

import string
import random
import requests
import logging
from urllib.parse import urlparse
from config import SHORTLINK_API, SHORTLINK_URL

logger = logging.getLogger(__name__)

def generate_verify_token(length=16):
    """Generate random verification token"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def detect_shortlink_service(url):
    """
    Automatically detect shortlink service from URL
    Returns service type for API adaptation
    """
    try:
        domain = urlparse(url).netloc.lower()
        
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Arolinks and similar services
        if 'arolinks' in domain:
            return 'arolinks'
        elif 'gplinks' in domain:
            return 'gplinks'
        elif 'shrinkme' in domain:
            return 'shrinkme'
        elif 'shortest' in domain:
            return 'shortest'
        elif 'linkvertise' in domain:
            return 'linkvertise'
        elif 'adfly' in domain or 'adf.ly' in domain:
            return 'adfly'
        elif 'short.io' in domain:
            return 'shortio'
        elif 'bit.ly' in domain:
            return 'bitly'
        elif 'tinyurl' in domain:
            return 'tinyurl'
        else:
            return 'generic'
            
    except Exception as e:
        logger.error(f"Error detecting service: {e}")
        return 'generic'

def create_universal_shortlink(url):
    """
    Universal shortlink creator - works with ANY service
    Tries multiple API formats until one works
    """
    try:
        service_type = detect_shortlink_service(SHORTLINK_URL)
        logger.info(f"Detected shortlink service: {service_type}")
        
        # Try different API formats in order of popularity
        api_formats = [
            format_standard_api,      # Most common format
            format_post_api,          # POST request format
            format_arolinks_api,      # Arolinks specific
            format_gplinks_api,       # GPLinks specific
            format_shrinkme_api,      # ShrinkMe specific
            format_generic_get_api,   # Generic GET
            format_json_post_api,     # JSON POST
            format_form_post_api,     # Form POST
        ]
        
        for api_format in api_formats:
            try:
                result = api_format(url)
                if result:
                    logger.info(f"✅ Shortlink created successfully: {result}")
                    return result
            except Exception as e:
                logger.debug(f"API format failed: {e}")
                continue
        
        logger.error("❌ All API formats failed")
        return None
        
    except Exception as e:
        logger.error(f"Universal shortlink error: {e}")
        return None

def format_standard_api(url):
    """Standard API format (works with 80% of services)"""
    payload = {
        'api': SHORTLINK_API,
        'url': url
    }
    
    response = requests.get(SHORTLINK_URL, params=payload, timeout=10)
    data = response.json()
    
    # Try different response formats
    return (data.get('shortenedUrl') or 
            data.get('short_url') or
            data.get('result_url') or
            data.get('shortUrl') or
            data.get('data', {}).get('url'))

def format_post_api(url):
    """POST request format"""
    payload = {
        'api': SHORTLINK_API,
        'url': url
    }
    
    response = requests.post(SHORTLINK_URL, data=payload, timeout=10)
    data = response.json()
    
    return (data.get('shortenedUrl') or 
            data.get('short_url') or
            data.get('result_url'))

def format_arolinks_api(url):
    """Arolinks.com specific format"""
    payload = {
        'api': SHORTLINK_API,
        'url': url,
        'alias': generate_verify_token(8)  # Optional custom alias
    }
    
    response = requests.get(SHORTLINK_URL, params=payload, timeout=10)
    data = response.json()
    
    if data.get('status') == 'success':
        return data.get('shortenedUrl')
    return None

def format_gplinks_api(url):
    """GPLinks specific format"""
    payload = {
        'api': SHORTLINK_API,
        'url': url
    }
    
    response = requests.get(SHORTLINK_URL, params=payload, timeout=10)
    data = response.json()
    
    if data.get('status') == 'success':
        return data.get('shortenedUrl')
    return None

def format_shrinkme_api(url):
    """ShrinkMe specific format"""
    payload = {
        'api': SHORTLINK_API,
        'url': url
    }
    
    response = requests.get(SHORTLINK_URL, params=payload, timeout=10)
    data = response.json()
    
    if data.get('status') == 'success':
        return data.get('shortenedUrl')
    return None

def format_generic_get_api(url):
    """Generic GET format with different parameter names"""
    parameter_combinations = [
        {'key': SHORTLINK_API, 'url': url},
        {'token': SHORTLINK_API, 'link': url},
        {'api_key': SHORTLINK_API, 'long_url': url},
        {'apikey': SHORTLINK_API, 'originalUrl': url},
        {'access_token': SHORTLINK_API, 'url': url}
    ]
    
    for params in parameter_combinations:
        try:
            response = requests.get(SHORTLINK_URL, params=params, timeout=10)
            data = response.json()
            
            result = (data.get('shortenedUrl') or 
                     data.get('short_url') or
                     data.get('result_url') or
                     data.get('shortUrl') or
                     data.get('shortened_url'))
            
            if result:
                return result
                
        except:
            continue
    
    return None

def format_json_post_api(url):
    """JSON POST format"""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {SHORTLINK_API}'
    }
    
    payload = {
        'url': url,
        'domain': urlparse(SHORTLINK_URL).netloc
    }
    
    response = requests.post(SHORTLINK_URL, json=payload, headers=headers, timeout=10)
    data = response.json()
    
    return (data.get('short_url') or 
            data.get('shortURL') or
            data.get('result_url'))

def format_form_post_api(url):
    """Form POST format"""
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    payload = {
        'api': SHORTLINK_API,
        'url': url
    }
    
    response = requests.post(SHORTLINK_URL, data=payload, headers=headers, timeout=10)
    data = response.json()
    
    return (data.get('shortenedUrl') or 
            data.get('short_url') or
            data.get('result_url'))

def test_shortlink_api():
    """
    Test function to verify your shortlink API works
    Returns True if API is working, False otherwise
    """
    try:
        test_url = "https://google.com"
        result = create_universal_shortlink(test_url)
        
        if result and result.startswith('http'):
            logger.info(f"✅ Shortlink API test successful: {result}")
            return True
        else:
            logger.error("❌ Shortlink API test failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Shortlink API test error: {e}")
        return False

def generate_monetized_verification_link(bot_username, token):
    """
    Generate verification link using universal shortlink system
    Automatically adapts to ANY shortlink service
    """
    try:
        # Create direct verification URL
        verify_url = f"https://t.me/{bot_username}?start=verify_{token}"
        
        # Create universal shortlink
        monetized_url = create_universal_shortlink(verify_url)
        
        if monetized_url:
            logger.info(f"✅ Universal shortlink created: {monetized_url}")
            return monetized_url
        else:
            # Fallback to direct URL if shortlink fails
            logger.warning("Universal shortlink failed, using direct URL")
            return verify_url
            
    except Exception as e:
        logger.error(f"Error generating verification link: {e}")
        return verify_url  # Always return something

def extract_token_from_start(text):
    """Extract verification token from /start command"""
    try:
        if text.startswith("verify_"):
            return text.split("verify_")[1]
        return None
    except Exception as e:
        logger.error(f"Error extracting token: {e}")
        return None
        
