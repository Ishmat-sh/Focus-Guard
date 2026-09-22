from __future__ import annotations

import subprocess


def get_active_application() -> str:
    script = 'tell application "System Events" to get name of first application process whose frontmost is true'
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=1)
        return result.stdout.strip() or "Unknown"
    except (OSError, subprocess.SubprocessError):
        return "Unknown"