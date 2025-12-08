"""
Adult Content Automation Configuration
Separate from main Terabox bot config
"""

import os
from dotenv import load_dotenv

load_dotenv()

# =====================================================
# ADULT BOT CONFIGURATION (NEW)
# =====================================================

# LuluStream API
LULUSTREAM_API_KEY = os.getenv("LULUSTREAM_API_KEY", "")

# Telegram Configuration
ADULT_CHANNEL_ID = int(os.getenv("ADULT_CHANNEL_ID", "0"))  # Your adult content channel
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",")]  # Admin user IDs

# Scraping Configuration
MIN_VIEWS = int(os.getenv("MIN_VIEWS", "20000"))  # Minimum views for videos
POSTS_PER_RUN = int(os.getenv("POSTS_PER_RUN", "3"))  # Videos per automation run
POST_INTERVAL = int(os.getenv("POST_INTERVAL", "600"))  # Seconds between posts (10 mins)

# Schedule (when to auto-scrape)
SCRAPE_HOURS = os.getenv("SCRAPE_HOURS", "6,12,18,0").split(",")  # 4 times daily

# Indian content keywords (recorded/amateur allowed)
INDIAN_KEYWORDS = [
    "indian mms",
    "desi leaked",
    "indian bhabhi",
    "desi couple homemade",
    "indian girlfriend",
    "desi wife secret",
    "mumbai scandal",
    "delhi mms",
    "bangalore couple",
    "tamil sex video",
    "telugu aunty",
    "malayalam couple",
    "punjabi girl"
]

# =====================================================
# SAFETY FILTERS (STRICT BLOCKING)
# =====================================================

# ILLEGAL keywords - These will be BLOCKED
ILLEGAL_KEYWORDS = [
    # Child-related
    'child', 'kid', 'minor', 'underage', 'loli', 'preteen',
    'school girl', 'daughter', 'jailbait', 
    
    # Animal
    'animal', 'dog', 'horse', 'beast', 'zoo',
    
    # Violence/rape
    'rape', 'forced', 'abuse', 'torture', 'drugged', 'unconscious'
]

# Messages - FIXED VERSION
AUTOMATION_STATUS_MSG = """
🤖 **Adult Content Automation Status**

📊 **Configuration:**
• Min Views: {min_views:,}
• Posts per run: {posts_per_run}
• Schedule: {schedule}
• Channel: {channel_id}

🛡️ **Safety:**
• Blocked keywords: {blocked_count}
• Indian content focus: ✅
• Quality filter: Allows all (HD/SD/recorded)

⚙️ **LuluStream:**
• API: {lulu_status}
• Monetization: Active

🔄 **Status:** {overall_status}

📈 **Statistics:**
• Total Posted: {total_posted}
• Today: {today_posted}
"""

# Validation
if LULUSTREAM_API_KEY and ADULT_CHANNEL_ID:
    print("✅ Adult automation configured")
else:
    print("⚠️ Adult automation not configured (need LULUSTREAM_API_KEY and ADULT_CHANNEL_ID)")
