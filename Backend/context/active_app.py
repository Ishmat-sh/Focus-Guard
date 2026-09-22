from __future__ import annotations

import platform

from backend.context.macos import get_active_application as get_macos_application
from backend.context.windows import get_active_application as get_windows_application


def get_active_application() -> str:
    if platform.system() == "Darwin":
        return get_macos_application()
    if platform.system() == "Windows":
        return get_windows_application()
    return "Unknown"