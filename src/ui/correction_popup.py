"""Correction suggestion popup for Ditado."""

import tkinter as tk
from tkinter import ttk
import threading
from typing import Callable, Optional

from ..utils.logger import get_logger

logger = get_logger("correction_popup")


class CorrectionPopup:
    """
    A discrete popup that suggests adding a detected correction to the dictionary.

    Appears in the bottom-right corner of the screen and auto-dismisses after a timeout.
    """

    # Display duration in milliseconds
    DISPLAY_DURATION = 8000

    # Animation duration in milliseconds
    FADE_DURATION = 300

    def __init__(
        self,
        on_accept: Optional[Callable[[str, str], None]] = None,
        on_reject: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize the correction popup.

        Args:
            on_accept: Callback when user accepts the correction (wrong, correct)
            on_reject: Callback when user rejects the correction
        """
        self._on_accept = on_accept
        self._on_reject = on_reject
        self._root: Optional[tk.Toplevel] = None
        self._current_wrong: str = ""
        self._current_correct: str = ""
        self._dismiss_timer: Optional[str] = None
        self._lock = threading.Lock()

    def show(self, wrong: str, correct: str, parent: Optional[tk.Tk] = None) -> None:
        """
        Show the correction suggestion popup.

        Args:
            wrong: The incorrectly transcribed word
            correct: The corrected word
            parent: Parent Tk window (optional)
        """
        with self._lock:
            # Close any existing popup
            self._close_popup()

            self._current_wrong = wrong
            self._current_correct = correct

            # Create popup window
            if parent:
                self._root = tk.Toplevel(parent)
            else:
                self._root = tk.Toplevel()

            self._setup_window()
            self._create_widgets()
            self._position_window()

            # Schedule auto-dismiss
            self._dismiss_timer = self._root.after(
                self.DISPLAY_DURATION,
                self._on_timeout
            )

    def _setup_window(self) -> None:
        """Configure the popup window."""
        self._root.overrideredirect(True)  # Remove window decorations
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.95)

        # Dark theme colors
        self._root.configure(bg="#2b2b2b")

        # Prevent focus stealing
        self._root.attributes("-toolwindow", True)

    def _create_widgets(self) -> None:
        """Create the popup widgets."""
        # Main frame with padding
        frame = tk.Frame(
            self._root,
            bg="#2b2b2b",
            padx=15,
            pady=10
        )
        frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Label(
            frame,
            text="Correção detectada",
            font=("Segoe UI", 9),
            fg="#888888",
            bg="#2b2b2b"
        )
        header.pack(anchor="w")

        # Correction text
        correction_frame = tk.Frame(frame, bg="#2b2b2b")
        correction_frame.pack(fill=tk.X, pady=(5, 0))

        wrong_label = tk.Label(
            correction_frame,
            text=f'"{self._current_wrong}"',
            font=("Segoe UI", 11),
            fg="#ff6b6b",
            bg="#2b2b2b"
        )
        wrong_label.pack(side=tk.LEFT)

        arrow_label = tk.Label(
            correction_frame,
            text=" → ",
            font=("Segoe UI", 11),
            fg="#888888",
            bg="#2b2b2b"
        )
        arrow_label.pack(side=tk.LEFT)

        correct_label = tk.Label(
            correction_frame,
            text=f'"{self._current_correct}"',
            font=("Segoe UI", 11),
            fg="#69db7c",
            bg="#2b2b2b"
        )
        correct_label.pack(side=tk.LEFT)

        # Question
        question = tk.Label(
            frame,
            text="Adicionar ao dicionário?",
            font=("Segoe UI", 9),
            fg="#aaaaaa",
            bg="#2b2b2b"
        )
        question.pack(anchor="w", pady=(8, 0))

        # Buttons frame
        btn_frame = tk.Frame(frame, bg="#2b2b2b")
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        # Style for buttons
        style = ttk.Style()
        style.configure(
            "Accept.TButton",
            padding=(10, 5),
        )
        style.configure(
            "Reject.TButton",
            padding=(10, 5),
        )

        # Accept button
        accept_btn = tk.Button(
            btn_frame,
            text="Sim",
            font=("Segoe UI", 9),
            bg="#3d5a3d",
            fg="white",
            activebackground="#4a6d4a",
            activeforeground="white",
            relief=tk.FLAT,
            padx=15,
            pady=3,
            cursor="hand2",
            command=self._on_accept_click
        )
        accept_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Reject button
        reject_btn = tk.Button(
            btn_frame,
            text="Não",
            font=("Segoe UI", 9),
            bg="#4a4a4a",
            fg="white",
            activebackground="#5a5a5a",
            activeforeground="white",
            relief=tk.FLAT,
            padx=15,
            pady=3,
            cursor="hand2",
            command=self._on_reject_click
        )
        reject_btn.pack(side=tk.LEFT)

        # Close button (X)
        close_btn = tk.Button(
            frame,
            text="×",
            font=("Segoe UI", 12),
            bg="#2b2b2b",
            fg="#666666",
            activebackground="#2b2b2b",
            activeforeground="#888888",
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self._on_close_click
        )
        close_btn.place(relx=1.0, rely=0, anchor="ne")

    def _position_window(self) -> None:
        """Position the popup in the bottom-right corner."""
        self._root.update_idletasks()

        # Get screen dimensions
        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()

        # Get popup dimensions
        popup_width = self._root.winfo_reqwidth()
        popup_height = self._root.winfo_reqheight()

        # Position in bottom-right with margin
        x = screen_width - popup_width - 20
        y = screen_height - popup_height - 60  # Above taskbar

        self._root.geometry(f"+{x}+{y}")

    def _on_accept_click(self) -> None:
        """Handle accept button click."""
        logger.info(f"User accepted correction: '{self._current_wrong}' -> '{self._current_correct}'")
        if self._on_accept:
            self._on_accept(self._current_wrong, self._current_correct)
        self._close_popup()

    def _on_reject_click(self) -> None:
        """Handle reject button click."""
        logger.debug(f"User rejected correction: '{self._current_wrong}' -> '{self._current_correct}'")
        if self._on_reject:
            self._on_reject(self._current_wrong, self._current_correct)
        self._close_popup()

    def _on_close_click(self) -> None:
        """Handle close button click."""
        self._close_popup()

    def _on_timeout(self) -> None:
        """Handle auto-dismiss timeout."""
        logger.debug("Correction popup timed out")
        self._close_popup()

    def _close_popup(self) -> None:
        """Close the popup window."""
        if self._dismiss_timer and self._root:
            try:
                self._root.after_cancel(self._dismiss_timer)
            except Exception:
                pass
            self._dismiss_timer = None

        if self._root:
            try:
                self._root.destroy()
            except Exception:
                pass
            self._root = None

    def is_visible(self) -> bool:
        """Check if the popup is currently visible."""
        return self._root is not None

    def hide(self) -> None:
        """Hide the popup."""
        with self._lock:
            self._close_popup()
