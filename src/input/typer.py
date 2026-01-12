"""Text injection module for Ditado."""

import time
import pyautogui
import pyperclip


class TextTyper:
    """Type text at the current cursor position."""

    def __init__(self, typing_speed: float = 0.0, use_clipboard: bool = True):
        """
        Initialize the text typer.

        Args:
            typing_speed: Delay between characters in seconds (0 = instant)
            use_clipboard: Use clipboard method by default (better Unicode support)
        """
        self.typing_speed = typing_speed
        self.use_clipboard = use_clipboard
        # Disable pyautogui's fail-safe (moving mouse to corner stops script)
        pyautogui.FAILSAFE = False

    def type_text(self, text: str) -> bool:
        """
        Type text at the current cursor position.
        Uses clipboard method by default for better Unicode support.

        Args:
            text: Text to type

        Returns:
            True if successful, False otherwise
        """
        if not text:
            return False

        if self.use_clipboard:
            return self._type_via_clipboard(text)
        else:
            return self._type_via_keyboard(text)

    def _type_via_keyboard(self, text: str) -> bool:
        """Type text directly via keyboard simulation."""
        try:
            # Small delay to ensure focus is on the target window
            time.sleep(0.05)

            if self.typing_speed > 0:
                # Type character by character with delay
                pyautogui.typewrite(text, interval=self.typing_speed)
            else:
                # Use write for better Unicode support
                pyautogui.write(text)

            return True
        except Exception as e:
            print(f"Error typing text: {e}")
            return False

    def _type_via_clipboard(self, text: str) -> bool:
        """
        Type text using clipboard (better for special characters).

        This method copies text to clipboard and pastes it, which
        handles Unicode and special characters better than pyautogui.write().
        """
        try:
            # Small delay to ensure focus is on the target window
            time.sleep(0.05)

            # Save current clipboard with multiple fallback attempts
            old_clipboard = None
            try:
                old_clipboard = pyperclip.paste()
            except Exception:
                pass

            # Copy new text to clipboard
            pyperclip.copy(text)

            # Small delay to ensure clipboard is ready
            time.sleep(0.02)

            # Paste
            pyautogui.hotkey("ctrl", "v")

            # Small delay before restoring clipboard
            time.sleep(0.15)

            # Restore old clipboard if we had one
            if old_clipboard is not None:
                try:
                    pyperclip.copy(old_clipboard)
                except Exception:
                    pass

            return True
        except Exception as e:
            print(f"Error typing via clipboard: {e}")
            # Fallback to keyboard typing
            return self._type_via_keyboard(text)

    def type_text_clipboard(self, text: str) -> bool:
        """
        Type text using clipboard (legacy method, now same as type_text).
        Kept for backwards compatibility.
        """
        return self._type_via_clipboard(text)
