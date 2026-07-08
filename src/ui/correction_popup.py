"""Correction suggestion popup for Ditado — "Soft Warmth" identity.

A small cream card (matching the overlay/dashboard) that suggests adding a
detected correction to the vocabulary dictionary. Appears bottom-right and
auto-dismisses after a timeout.
"""

import tkinter as tk
import threading
from typing import Callable, Optional

from . import theme
from ..utils.logger import get_logger

logger = get_logger("correction_popup")


class CorrectionPopup:
    """A discrete popup that suggests adding a detected correction."""

    # Display duration in milliseconds
    DISPLAY_DURATION = 8000

    def __init__(
        self,
        on_accept: Optional[Callable[[str, str], None]] = None,
        on_reject: Optional[Callable[[str, str], None]] = None
    ):
        """
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

        # O popup é auto-hospedado: corre o seu próprio Tk num thread
        # dedicado (a app principal já não tem root Tkinter — o dashboard
        # é uma janela web). Comandos chegam por fila, como no overlay.
        self._host_root: Optional[tk.Tk] = None
        self._commands: list = []
        self._host_started = False

    def _ensure_host(self) -> None:
        if self._host_started:
            return
        self._host_started = True
        threading.Thread(
            target=self._host_loop, name="correction-popup", daemon=True
        ).start()

    def _host_loop(self) -> None:
        self._host_root = tk.Tk()
        self._host_root.withdraw()
        self._poll_commands()
        self._host_root.mainloop()

    def _poll_commands(self) -> None:
        while self._commands:
            cmd = self._commands.pop(0)
            try:
                if cmd[0] == "show":
                    self._show_on_host(cmd[1], cmd[2])
                elif cmd[0] == "hide":
                    self._close_popup()
            except Exception as e:
                logger.debug(f"Popup command failed: {e}")
        self._host_root.after(120, self._poll_commands)

    def show(self, wrong: str, correct: str, parent=None) -> None:
        """Show the popup. Thread-safe: enqueues onto the popup's own thread."""
        self._ensure_host()
        with self._lock:
            self._commands.append(("show", wrong, correct))

    def _show_on_host(self, wrong: str, correct: str) -> None:
        """Build the popup window (runs on the host Tk thread)."""
        self._close_popup()

        self._current_wrong = wrong
        self._current_correct = correct

        self._root = tk.Toplevel(self._host_root)
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
        self._root.attributes("-alpha", 0.97)

        # 1px warm border via the root bg showing around the inner card
        self._root.configure(bg=theme.BG_OVERLAY_BORDER)

        # Prevent focus stealing
        self._root.attributes("-toolwindow", True)

    def _create_widgets(self) -> None:
        """Create the popup widgets (cream card, editorial type)."""
        serif = theme.serif_family()
        sans = theme.FONT_SANS_NAME
        card_bg = theme.BG_CARD

        # Inner cream card, inset 1px so the root bg reads as a border
        frame = tk.Frame(self._root, bg=card_bg, padx=16, pady=12)
        frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Small-caps header with terracotta dot (same language as the dashboard)
        header_row = tk.Frame(frame, bg=card_bg)
        header_row.pack(fill=tk.X)

        tk.Label(
            header_row,
            text="●",
            font=(sans, 7),
            fg=theme.ACCENT_PRIMARY,
            bg=card_bg,
        ).pack(side=tk.LEFT, padx=(0, 6))

        tk.Label(
            header_row,
            text="CORRECTION DETECTED",
            font=(sans, 8, "bold"),
            fg=theme.TEXT_GRAY,
            bg=card_bg,
        ).pack(side=tk.LEFT)

        # Correction row: struck-through original → corrected in serif
        correction_frame = tk.Frame(frame, bg=card_bg)
        correction_frame.pack(fill=tk.X, pady=(8, 0))

        tk.Label(
            correction_frame,
            text=self._current_wrong,
            font=(serif, 12, "overstrike"),
            fg=theme.TEXT_MUTED,
            bg=card_bg,
        ).pack(side=tk.LEFT)

        tk.Label(
            correction_frame,
            text="  →  ",
            font=(sans, 11),
            fg=theme.TEXT_GRAY,
            bg=card_bg,
        ).pack(side=tk.LEFT)

        tk.Label(
            correction_frame,
            text=self._current_correct,
            font=(serif, 13),
            fg=theme.ACCENT_PRIMARY_DARK,
            bg=card_bg,
        ).pack(side=tk.LEFT)

        # Question
        tk.Label(
            frame,
            text="Add to your dictionary?",
            font=(sans, 9),
            fg=theme.TEXT_GRAY,
            bg=card_bg,
        ).pack(anchor="w", pady=(10, 0))

        # Buttons
        btn_frame = tk.Frame(frame, bg=card_bg)
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        tk.Button(
            btn_frame,
            text="Add",
            font=(sans, 9, "bold"),
            bg=theme.ACCENT_PRIMARY_DARK,
            fg=theme.TEXT_LIGHT,
            activebackground=theme.ACCENT_PRIMARY,
            activeforeground=theme.TEXT_LIGHT,
            relief=tk.FLAT,
            padx=16,
            pady=4,
            cursor="hand2",
            command=self._on_accept_click,
        ).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(
            btn_frame,
            text="Dismiss",
            font=(sans, 9),
            bg=theme.BG_CARD_HOVER,
            fg=theme.TEXT_DARK,
            activebackground=theme.BG_OVERLAY_BORDER,
            activeforeground=theme.TEXT_DARK,
            relief=tk.FLAT,
            padx=14,
            pady=4,
            cursor="hand2",
            command=self._on_reject_click,
        ).pack(side=tk.LEFT)

        # Close button (X)
        tk.Button(
            frame,
            text="×",
            font=(sans, 11),
            bg=card_bg,
            fg=theme.TEXT_GRAY,
            activebackground=card_bg,
            activeforeground=theme.TEXT_DARK,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self._on_close_click,
        ).place(relx=1.0, rely=0, anchor="ne")

    def _position_window(self) -> None:
        """Position the popup in the bottom-right corner."""
        self._root.update_idletasks()

        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()
        popup_width = self._root.winfo_reqwidth()
        popup_height = self._root.winfo_reqheight()

        # Position in bottom-right with margin
        x = screen_width - popup_width - 20
        y = screen_height - popup_height - 60  # Above taskbar

        self._root.geometry(f"+{x}+{y}")

    def _on_accept_click(self) -> None:
        """Handle accept button click."""
        logger.info("User accepted a vocabulary correction")
        logger.debug(f"Accepted: '{self._current_wrong}' -> '{self._current_correct}'")
        if self._on_accept:
            self._on_accept(self._current_wrong, self._current_correct)
        self._close_popup()

    def _on_reject_click(self) -> None:
        """Handle reject button click."""
        logger.debug(f"Rejected correction: '{self._current_wrong}' -> '{self._current_correct}'")
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
        """Hide the popup (thread-safe)."""
        if not self._host_started:
            return
        with self._lock:
            self._commands.append(("hide",))
