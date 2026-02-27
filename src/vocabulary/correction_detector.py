"""Correction detection module for Ditado.

Monitors for user corrections after dictation and suggests adding them
to the vocabulary dictionary.
"""

import threading
import time
import difflib
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass

from ..utils.logger import get_logger

logger = get_logger("correction_detector")

# Try to import pyperclip for clipboard monitoring
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False
    logger.warning("pyperclip not available, clipboard monitoring disabled")


@dataclass
class DetectedCorrection:
    """A detected correction from user edit."""
    original: str
    corrected: str
    confidence: float  # 0-1, how confident we are this is a correction


class CorrectionDetector:
    """
    Detects when users correct transcribed text.

    After text is inserted, monitors clipboard for a short period.
    If the user copies text that's similar to what was inserted,
    we can detect word-level corrections.
    """

    # How long to monitor after insertion (seconds)
    MONITORING_DURATION = 30.0

    # Minimum similarity for text to be considered a correction
    MIN_SIMILARITY = 0.5

    # Minimum word length to consider for corrections
    MIN_WORD_LENGTH = 2

    def __init__(
        self,
        on_correction_detected: Optional[Callable[[DetectedCorrection], None]] = None
    ):
        """
        Initialize the correction detector.

        Args:
            on_correction_detected: Callback when a correction is detected
        """
        self._callback = on_correction_detected
        self._last_inserted_text: Optional[str] = None
        self._last_inserted_time: float = 0
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_clipboard: str = ""
        self._detected_corrections: List[DetectedCorrection] = []

    def text_inserted(self, text: str) -> None:
        """
        Called when text has been inserted by dictation.

        Args:
            text: The text that was inserted
        """
        self._last_inserted_text = text
        self._last_inserted_time = time.time()
        self._detected_corrections = []

        # Start monitoring in background
        if CLIPBOARD_AVAILABLE:
            self._start_monitoring()

    def _start_monitoring(self) -> None:
        """Start clipboard monitoring in background."""
        if self._monitoring:
            self._stop_event.set()
            if self._monitor_thread:
                self._monitor_thread.join(timeout=1.0)

        self._stop_event.clear()
        self._monitoring = True

        # Get current clipboard to ignore it
        try:
            self._last_clipboard = pyperclip.paste() or ""
        except Exception:
            self._last_clipboard = ""

        self._monitor_thread = threading.Thread(
            target=self._monitor_clipboard,
            daemon=True
        )
        self._monitor_thread.start()

    def _monitor_clipboard(self) -> None:
        """Background thread that monitors clipboard changes."""
        start_time = time.time()

        while not self._stop_event.is_set():
            # Check if monitoring period expired
            if time.time() - start_time > self.MONITORING_DURATION:
                break

            try:
                current_clipboard = pyperclip.paste() or ""

                # Check if clipboard changed
                if current_clipboard and current_clipboard != self._last_clipboard:
                    self._last_clipboard = current_clipboard
                    self._check_for_corrections(current_clipboard)

            except Exception as e:
                logger.debug(f"Clipboard monitoring error: {e}")

            # Check every 500ms
            self._stop_event.wait(0.5)

        self._monitoring = False

    def _check_for_corrections(self, clipboard_text: str) -> None:
        """
        Check if clipboard text contains corrections to the inserted text.

        Args:
            clipboard_text: Current clipboard content
        """
        if not self._last_inserted_text:
            return

        # Calculate similarity
        similarity = difflib.SequenceMatcher(
            None,
            self._last_inserted_text.lower(),
            clipboard_text.lower()
        ).ratio()

        # If text is similar enough, look for word-level corrections
        if similarity < self.MIN_SIMILARITY:
            return

        # Find word-level differences
        corrections = self._find_word_corrections(
            self._last_inserted_text,
            clipboard_text
        )

        for correction in corrections:
            # Avoid duplicates
            if not any(
                c.original == correction.original and c.corrected == correction.corrected
                for c in self._detected_corrections
            ):
                self._detected_corrections.append(correction)
                logger.info(
                    f"Detected correction: '{correction.original}' -> '{correction.corrected}'"
                )

                if self._callback:
                    self._callback(correction)

    def _find_word_corrections(
        self,
        original: str,
        corrected: str
    ) -> List[DetectedCorrection]:
        """
        Find word-level corrections between two texts.

        Args:
            original: The original text
            corrected: The corrected text

        Returns:
            List of detected corrections
        """
        corrections = []

        # Tokenize into words
        original_words = original.split()
        corrected_words = corrected.split()

        # Use SequenceMatcher to find differences
        matcher = difflib.SequenceMatcher(None, original_words, corrected_words)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                # Words were replaced
                orig_segment = original_words[i1:i2]
                corr_segment = corrected_words[j1:j2]

                # If it's a 1-to-1 replacement, likely a correction
                if len(orig_segment) == 1 and len(corr_segment) == 1:
                    orig_word = orig_segment[0]
                    corr_word = corr_segment[0]

                    # Skip if words are too short
                    if len(orig_word) < self.MIN_WORD_LENGTH:
                        continue

                    # Skip if words are the same (case difference only)
                    if orig_word.lower() == corr_word.lower():
                        continue

                    # Calculate word similarity
                    word_sim = difflib.SequenceMatcher(
                        None, orig_word.lower(), corr_word.lower()
                    ).ratio()

                    # Only consider if words are somewhat similar (likely a typo/mishearing)
                    # or completely different (likely a mishearing of a name/term)
                    if word_sim > 0.3 or len(orig_word) > 4:
                        corrections.append(DetectedCorrection(
                            original=orig_word,
                            corrected=corr_word,
                            confidence=word_sim
                        ))

        return corrections

    def stop_monitoring(self) -> None:
        """Stop clipboard monitoring."""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        self._monitoring = False

    def get_pending_corrections(self) -> List[DetectedCorrection]:
        """Get all detected corrections that haven't been processed."""
        return list(self._detected_corrections)

    def clear_pending_corrections(self) -> None:
        """Clear pending corrections."""
        self._detected_corrections = []
