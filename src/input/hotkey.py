"""Global hotkey listener for Ditado."""

import threading
import time
from typing import Callable, Optional, List
from pynput import keyboard


# Separator for key combinations
COMBINATION_SEPARATOR = "+"

# Map of common key names to pynput keys
KEY_MAP = {
    "caps_lock": keyboard.Key.caps_lock,
    "scroll_lock": keyboard.Key.scroll_lock,
    "pause": keyboard.Key.pause,
    "insert": keyboard.Key.insert,
    "home": keyboard.Key.home,
    "end": keyboard.Key.end,
    "page_up": keyboard.Key.page_up,
    "page_down": keyboard.Key.page_down,
    "f1": keyboard.Key.f1,
    "f2": keyboard.Key.f2,
    "f3": keyboard.Key.f3,
    "f4": keyboard.Key.f4,
    "f5": keyboard.Key.f5,
    "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7,
    "f8": keyboard.Key.f8,
    "f9": keyboard.Key.f9,
    "f10": keyboard.Key.f10,
    "f11": keyboard.Key.f11,
    "f12": keyboard.Key.f12,
    "ctrl": keyboard.Key.ctrl,
    "ctrl_r": keyboard.Key.ctrl_r,
    "ctrl_l": keyboard.Key.ctrl_l,
    "alt": keyboard.Key.alt,
    "alt_r": keyboard.Key.alt_r,
    "alt_l": keyboard.Key.alt_l,
    "shift": keyboard.Key.shift,
    "shift_r": keyboard.Key.shift_r,
    "shift_l": keyboard.Key.shift_l,
    "space": keyboard.Key.space,
    "tab": keyboard.Key.tab,
    "enter": keyboard.Key.enter,
    "backspace": keyboard.Key.backspace,
    "delete": keyboard.Key.delete,
    "esc": keyboard.Key.esc,
    # Windows/Command key
    "cmd": keyboard.Key.cmd,
    "cmd_l": keyboard.Key.cmd_l,
    "cmd_r": keyboard.Key.cmd_r,
    # Arrow keys
    "up": keyboard.Key.up,
    "down": keyboard.Key.down,
    "left": keyboard.Key.left,
    "right": keyboard.Key.right,
    # Other special keys
    "print_screen": keyboard.Key.print_screen,
    "num_lock": keyboard.Key.num_lock,
    "menu": keyboard.Key.menu,
}


def key_from_string(key_str: str) -> Optional[keyboard.Key | keyboard.KeyCode]:
    """Convert a string key name to a pynput key."""
    key_str = key_str.lower().strip()

    # Check special keys
    if key_str in KEY_MAP:
        return KEY_MAP[key_str]

    # Single character
    if len(key_str) == 1:
        return keyboard.KeyCode.from_char(key_str)

    return None


def key_to_string(key: keyboard.Key | keyboard.KeyCode) -> str:
    """Convert a pynput key to a string name."""
    # Check if it's a special key in our map
    for name, k in KEY_MAP.items():
        if key == k:
            return name

    # Regular character
    if isinstance(key, keyboard.KeyCode) and key.char:
        return key.char.lower()

    # For special keys not in our map, extract name from Key enum
    # This returns "cmd" instead of "Key.cmd"
    if isinstance(key, keyboard.Key):
        return key.name

    return str(key)


def parse_hotkey_string(hotkey_str: str) -> List[keyboard.Key | keyboard.KeyCode]:
    """
    Parse a hotkey string into a list of key objects.

    Supports both single keys ("caps_lock") and combinations ("ctrl_l+f1").
    Returns a list with one or more key objects.
    """
    hotkey_str = hotkey_str.strip()

    if COMBINATION_SEPARATOR in hotkey_str:
        # Combination: split and parse each part
        parts = [p.strip() for p in hotkey_str.split(COMBINATION_SEPARATOR)]
        keys = []
        for part in parts:
            key = key_from_string(part)
            if key is not None:
                keys.append(key)
        return keys
    else:
        # Single key
        key = key_from_string(hotkey_str)
        return [key] if key else []


def keys_to_string(keys: List[keyboard.Key | keyboard.KeyCode]) -> str:
    """Convert a list of key objects back to a string representation."""
    if not keys:
        return ""
    parts = [key_to_string(k) for k in keys]
    return COMBINATION_SEPARATOR.join(parts)


def format_hotkey_display(hotkey_str: str) -> str:
    """
    Format a hotkey string for user-friendly display.

    Converts "ctrl_l+f1" to "Ctrl L + F1"
    """
    if not hotkey_str:
        return ""

    parts = hotkey_str.split(COMBINATION_SEPARATOR)
    formatted = []
    for part in parts:
        # Convert underscores to spaces, capitalize each word
        display = part.strip().replace("_", " ").title()
        formatted.append(display)

    return " + ".join(formatted)


class HotkeyListener:
    """Listen for global hotkey press/release (supports single keys and combinations)."""

    def __init__(
        self,
        hotkey: str = "caps_lock",
        on_press: Optional[Callable[[], None]] = None,
        on_release: Optional[Callable[[], None]] = None,
    ):
        self._hotkey_str = hotkey
        self._required_keys = parse_hotkey_string(hotkey)
        self._on_press = on_press
        self._on_release = on_release
        self._listener: Optional[keyboard.Listener] = None
        self._is_active = False  # Hotkey combo is currently active
        self._pressed_keys: set = set()  # Currently pressed keys (relevant to hotkey)
        self._enabled = True
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start listening for the hotkey."""
        if self._listener is not None:
            return

        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
            suppress=False,
        )
        self._listener.start()

    def stop(self) -> None:
        """Stop listening."""
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._is_active = False
        self._pressed_keys.clear()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the hotkey listener."""
        with self._lock:
            self._enabled = enabled

    def set_hotkey(self, hotkey: str) -> None:
        """Change the hotkey."""
        with self._lock:
            self._hotkey_str = hotkey
            self._required_keys = parse_hotkey_string(hotkey)
            # Reset state when hotkey changes
            self._pressed_keys.clear()
            self._is_active = False

    def get_hotkey(self) -> str:
        """Get the current hotkey string."""
        return self._hotkey_str

    def _key_matches_required(self, key: keyboard.Key | keyboard.KeyCode) -> Optional[keyboard.Key | keyboard.KeyCode]:
        """
        Check if a pressed key matches any of our required keys.
        Returns the matched required key, or None if no match.
        """
        for req_key in self._required_keys:
            if key == req_key:
                return req_key
            # Also check for KeyCode char matching
            if isinstance(key, keyboard.KeyCode) and isinstance(req_key, keyboard.KeyCode):
                if key.char and req_key.char and key.char.lower() == req_key.char.lower():
                    return req_key
        return None

    def _all_required_keys_pressed(self) -> bool:
        """Check if all required keys are currently pressed."""
        if not self._required_keys:
            return False

        for req_key in self._required_keys:
            if req_key not in self._pressed_keys:
                return False
        return True

    def _handle_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Handle key press event."""
        with self._lock:
            if not self._enabled:
                return

            # Check if this key matches any required key
            matched_key = self._key_matches_required(key)
            if matched_key is None:
                return

            # Add the required key to pressed set (use the canonical required key)
            self._pressed_keys.add(matched_key)

            # Check if all required keys are now pressed
            if not self._is_active and self._all_required_keys_pressed():
                self._is_active = True
                if self._on_press:
                    self._on_press()

    def _handle_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Handle key release event."""
        with self._lock:
            if not self._enabled:
                return

            # Check if this key matches any required key
            matched_key = self._key_matches_required(key)
            if matched_key is None:
                return

            # Remove from pressed keys
            self._pressed_keys.discard(matched_key)

            # If hotkey was active, deactivate it (ANY required key released)
            if self._is_active:
                self._is_active = False
                if self._on_release:
                    self._on_release()


class KeyCaptureDialog:
    """Utility to capture a single key press for hotkey configuration."""

    def __init__(self, callback: Callable[[str], None]):
        self._callback = callback
        self._listener: Optional[keyboard.Listener] = None

    def start_capture(self) -> None:
        """Start capturing the next key press."""
        self._listener = keyboard.Listener(
            on_press=self._on_key_press,
            suppress=True,  # Suppress the key so it doesn't type
        )
        self._listener.start()

    def _on_key_press(self, key: keyboard.Key | keyboard.KeyCode) -> bool:
        """Handle captured key."""
        key_str = key_to_string(key)
        if key_str:
            self._callback(key_str)
        if self._listener:
            self._listener.stop()
        return False  # Stop listener


class KeyCombinationCaptureDialog:
    """
    Utility to capture a key combination for hotkey configuration.

    Capture behavior:
    1. User holds keys they want to use (1-2 keys)
    2. After keys are stable for STABILITY_DELAY, capture the combination
    """

    STABILITY_DELAY = 0.3  # Seconds keys must be held together

    def __init__(self, callback: Callable[[str], None], max_keys: int = 2):
        self._callback = callback
        self._max_keys = max_keys
        self._listener: Optional[keyboard.Listener] = None
        self._pressed_keys: List[keyboard.Key | keyboard.KeyCode] = []
        self._capture_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._finished = False

    def start_capture(self) -> None:
        """Start capturing key combination."""
        self._listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
            suppress=True,
        )
        self._listener.start()

    def _on_key_press(self, key: keyboard.Key | keyboard.KeyCode) -> bool:
        """Handle key press during capture."""
        with self._lock:
            if self._finished:
                return False

            # Cancel existing timer
            if self._capture_timer:
                self._capture_timer.cancel()
                self._capture_timer = None

            # Add key if not already in list and under limit
            key_str = key_to_string(key)
            if key_str and key not in self._pressed_keys:
                if len(self._pressed_keys) < self._max_keys:
                    self._pressed_keys.append(key)

            # Start stability timer
            if self._pressed_keys:
                self._capture_timer = threading.Timer(
                    self.STABILITY_DELAY,
                    self._finish_capture
                )
                self._capture_timer.daemon = True
                self._capture_timer.start()

        return True  # Keep listening

    def _on_key_release(self, key: keyboard.Key | keyboard.KeyCode) -> bool:
        """Handle key release during capture."""
        with self._lock:
            if self._finished:
                return False

            # If timer fired (keys were stable), this release is after capture
            # Otherwise, remove the released key
            if key in self._pressed_keys:
                self._pressed_keys.remove(key)

                # Cancel timer since key set changed
                if self._capture_timer:
                    self._capture_timer.cancel()
                    self._capture_timer = None

                # If we still have keys, restart timer
                if self._pressed_keys:
                    self._capture_timer = threading.Timer(
                        self.STABILITY_DELAY,
                        self._finish_capture
                    )
                    self._capture_timer.daemon = True
                    self._capture_timer.start()

        return True

    def _finish_capture(self) -> None:
        """Finish capture and call callback."""
        with self._lock:
            if self._finished:
                return
            if not self._pressed_keys:
                return

            self._finished = True

            # Sort keys: modifiers first (Ctrl, Alt, Shift), then others
            def key_sort_order(k):
                key_str = key_to_string(k)
                if 'ctrl' in key_str:
                    return 0
                if 'alt' in key_str:
                    return 1
                if 'shift' in key_str:
                    return 2
                return 3

            sorted_keys = sorted(self._pressed_keys, key=key_sort_order)

            # Convert to string
            key_strings = [key_to_string(k) for k in sorted_keys if key_to_string(k)]
            result = COMBINATION_SEPARATOR.join(key_strings)

        # Stop listener (outside lock to avoid deadlock)
        if self._listener:
            self._listener.stop()

        # Call callback
        if result and self._callback:
            self._callback(result)

    def cancel(self) -> None:
        """Cancel capture."""
        with self._lock:
            self._finished = True
            if self._capture_timer:
                self._capture_timer.cancel()
        if self._listener:
            self._listener.stop()
