import random

HOOKS = [
    # Short & hot
    "🔥 Hot video inside",
    "🥵 Super sexy clip",
    "👀 Don’t miss this",
    "💥 New hot drop",
    "🫣 Only for adults",
    "😮 Must watch now",
    "✨ Rare video today",
    "🚀 Trending hot clip",

    # Extra hooks
    "🔥 So hot, watch now",
    "🥵 Spicy scene inside",
    "😉 For 18+ eyes only",
    "💋 Sexy & bold clip",
    "⚡ Quick watch, don’t blink",
    "🎯 Short and spicy",
    "📢 Watch before it’s gone",
    "💞 Hot moments inside",
    "🌶️ Extra spicy video",
    "🧲 Hot clip — tap to play",
    "💎 Rare and hot today",
    "📈 Viral hot video",
    "👄 Too hot to skip",
    "✨ Fresh drop, very hot",
    "🔥 Non‑stop hot vibes",
]

def pick_hook() -> str:
    return random.choice(HOOKS)
    
