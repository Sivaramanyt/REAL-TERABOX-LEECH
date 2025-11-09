import random

HOOKS = [
    "🔥 Hot video inside",
    "🥵 Super sexy clip",
    "👀 Don’t miss this",
    "💥 New hot drop",
    "🫣 Only for adults",
    "😮 Must watch now",
    "✨ Rare video today",
    "🚀 Trending hot clip",
]

def pick_hook() -> str:
    return random.choice(HOOKS)
