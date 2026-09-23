from __future__ import annotations

from enum import Enum


class AppCategory(str, Enum):
    PRODUCTIVE = "productive"
    NEUTRAL = "neutral"
    DISTRACTING = "distracting"
    UNKNOWN = "unknown"


DEFAULT_RULES = {
    AppCategory.PRODUCTIVE: ("Code", "Visual Studio Code", "Terminal", "iTerm", "PyCharm", "Xcode", "Notion"),
    AppCategory.DISTRACTING: ("YouTube", "Netflix", "TikTok", "Instagram", "Reddit", "Twitch", "Discord"),
    AppCategory.NEUTRAL: ("Finder", "System Settings", "Calendar", "Mail", "Slack", "Safari", "Chrome"),
}


def categorize_application(name: str) -> AppCategory:
    lowered = name.casefold()
    for category, names in DEFAULT_RULES.items():
        if any(candidate.casefold() in lowered for candidate in names):
            return category
    return AppCategory.UNKNOWN