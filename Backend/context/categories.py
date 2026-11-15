from __future__ import annotations

from enum import Enum
import re


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

_BROWSER_NAMES = (
    "Google Chrome",
    "Microsoft Edge",
    "Chromium",
    "Firefox",
    "Safari",
    "Brave",
    "Opera",
    "Vivaldi",
    "Edge",
    "Chrome",
)


def categorize_application(name: str) -> AppCategory:
    lowered = name.casefold()
    for category, names in DEFAULT_RULES.items():
        if any(candidate.casefold() in lowered for candidate in names):
            return category
    return AppCategory.UNKNOWN


def sanitize_application_name(name: str) -> str:
    normalized = " ".join(name.split())
    if not normalized:
        return "Unknown"
    for browser_name in _BROWSER_NAMES:
        if re.search(rf"\b{re.escape(browser_name)}\b", normalized, re.IGNORECASE):
            return browser_name
    return normalized