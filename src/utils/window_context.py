"""Best-effort foreground window context for Windows.

Used to enrich the GPT cleanup prompt with which app the user is dictating into,
so output tone can be adjusted (Slack vs. Outlook vs. code editor, etc.).

Designed to be a no-op on any platform other than Windows and to fail silently
on any error (this is purely a quality-of-life enhancement; never block on it).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional

from .logger import get_logger

logger = get_logger("window_context")


@dataclass
class WindowContext:
    """Lightweight info about the foreground window."""
    process_name: str  # e.g. "slack.exe"
    title: str        # e.g. "general - Acme - Slack"

    @property
    def app_label(self) -> str:
        """Friendly app name derived from the process name."""
        name = self.process_name.lower()
        if name.endswith(".exe"):
            name = name[:-4]
        # Common normalizations
        aliases = {
            "msedge": "Microsoft Edge",
            "chrome": "Google Chrome",
            "firefox": "Firefox",
            "outlook": "Outlook",
            "olk": "Outlook",
            "slack": "Slack",
            "discord": "Discord",
            "teams": "Microsoft Teams",
            "ms-teams": "Microsoft Teams",
            "code": "VS Code",
            "cursor": "Cursor",
            "notepad": "Notepad",
            "winword": "Word",
            "powerpnt": "PowerPoint",
            "excel": "Excel",
            "whatsapp": "WhatsApp",
            "telegram": "Telegram",
            "explorer": "File Explorer",
        }
        return aliases.get(name, name.title() if name else "")


def get_foreground_context() -> Optional[WindowContext]:
    """Return info about the foreground window, or None if unavailable.

    Best-effort: returns None on non-Windows platforms or any error.
    """
    if sys.platform != "win32":
        return None

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # 1. Find the foreground window handle
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        # 2. Read its title (best-effort, may be empty)
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or ""

        # 3. Resolve the owning process name
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        process_name = ""
        if pid.value:
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h_proc = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
            )
            if h_proc:
                try:
                    name_buf = ctypes.create_unicode_buffer(512)
                    size = wintypes.DWORD(512)
                    # QueryFullProcessImageNameW
                    if kernel32.QueryFullProcessImageNameW(
                        h_proc, 0, name_buf, ctypes.byref(size)
                    ):
                        full_path = name_buf.value
                        process_name = os.path.basename(full_path) if full_path else ""
                finally:
                    kernel32.CloseHandle(h_proc)

        if not process_name and not title:
            return None

        return WindowContext(process_name=process_name, title=title)

    except Exception as e:
        logger.debug(f"Foreground context lookup failed: {e}")
        return None
