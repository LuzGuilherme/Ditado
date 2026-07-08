"""Text injection module for Ditado."""

import time
import pyautogui
import pyperclip

from ..utils.logger import get_logger

logger = get_logger("typer")


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

    def copy_to_clipboard(self, text: str) -> bool:
        """Best-effort: leave text on the clipboard (used when typing fails,
        so the user can still paste it manually)."""
        try:
            pyperclip.copy(text)
            return True
        except Exception as e:
            logger.error(f"Could not copy text to clipboard: {e}")
            return False

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
            logger.error(f"Error typing text: {e}")
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

            # Save current clipboard TEXT (pyperclip can only read text;
            # images/files come back as "")
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

            # The target app consumes the paste asynchronously — restoring the
            # clipboard too early makes slow apps (Electron, RDP) paste the OLD
            # content instead. 0.3s is a compromise, not a guarantee.
            time.sleep(0.3)

            # Restore only when there was real text. pyperclip returns "" for
            # images/files, and writing "" back would destroy that content.
            if old_clipboard:
                try:
                    pyperclip.copy(old_clipboard)
                except Exception:
                    pass

            return True
        except Exception as e:
            logger.error(f"Error typing via clipboard: {e}")
            # Fallback to keyboard typing
            return self._type_via_keyboard(text)
