"""Editorial-style UI components for the Soft Warmth dashboard.

These components mirror the visual language from the reference design:
- Cream/paper backgrounds
- Serif headings (Georgia falls back gracefully on Windows)
- Small-caps metadata labels with terracotta dot markers
- Decorative vertical-bar waveforms drawn on tk.Canvas
- Pill-shaped action buttons

They are framework-light: built on tk.Canvas + CTkFrame so they integrate
cleanly with the rest of the CustomTkinter dashboard.
"""

from __future__ import annotations

import hashlib
import math
import random
import tkinter as tk
from typing import Callable, List, Optional

import customtkinter as ctk

from . import theme


# Serif font Tkinter is virtually guaranteed to resolve on Windows
SERIF_FAMILY = "Georgia"
SANS_FAMILY = "Segoe UI"


# ---------------------------------------------------------------------------
# Decorative waveform (Canvas)
# ---------------------------------------------------------------------------
class WaveformCanvas(ctk.CTkFrame):
    """Vertical-bar waveform.

    Wraps a tk.Canvas inside a CTkFrame so it composes cleanly with the rest
    of the CustomTkinter widget tree. Use modes:
      - Static bars driven by a seed (deterministic per history entry)
      - Or supply an explicit list of normalized levels (0..1)

    `pack()`/`grid()` works as for any CTk widget. The component exposes the
    same `width`/`height` as you'd expect.
    """

    def __init__(
        self,
        master,
        width: int = 600,
        height: int = 60,
        num_bars: int = 80,
        bar_width: int = 2,
        bar_gap: int = 4,
        color: str = theme.ACCENT_PRIMARY,
        bg: str = theme.BG_CARD,
        seed: Optional[str] = None,
        levels: Optional[List[float]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=bg, corner_radius=0, **kwargs)
        self._width_px = width
        self._height_px = height
        self._num_bars = num_bars
        self._bar_width = bar_width
        self._bar_gap = bar_gap
        self._color = color
        self._bg = bg

        # Inner tk.Canvas hosts the actual bar drawing.
        self._canvas = tk.Canvas(
            self,
            width=width,
            height=height,
            bg=bg,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(fill="both", expand=True)

        if levels is not None:
            self._levels = list(levels)[:num_bars]
        elif seed is not None:
            self._levels = self._levels_from_seed(seed, num_bars)
        else:
            self._levels = self._levels_from_seed("default", num_bars)

        self._render_bars()

    @staticmethod
    def _levels_from_seed(seed: str, n: int) -> List[float]:
        """Deterministically generate n normalized bar heights from a string.

        Uses a SHA1 digest as the random stream so the same seed always
        renders the same shape — handy for history items keyed by their text.
        """
        digest = hashlib.sha1(seed.encode("utf-8")).digest()
        rng = random.Random(int.from_bytes(digest[:8], "big"))
        # Use a gentle sine envelope so the waveform reads as "speech" not noise
        out: List[float] = []
        for i in range(n):
            envelope = (math.sin(i / n * math.pi * 1.8) + 1) / 2  # 0..1
            noise = rng.random()
            mixed = envelope * 0.5 + noise * 0.5
            # Bias toward shorter bars at the edges
            edge_dampen = 1.0 - abs(i - n / 2) / (n / 2) * 0.25
            out.append(max(0.05, min(1.0, mixed * edge_dampen)))
        return out

    def set_levels(self, levels: List[float]) -> None:
        """Replace the rendered levels and redraw."""
        self._levels = list(levels)[: self._num_bars]
        self._render_bars()

    def set_color(self, color: str) -> None:
        self._color = color
        self._render_bars()

    def _render_bars(self) -> None:
        self._canvas.delete("all")
        # Tile the bars across the available width
        total_w = self._num_bars * self._bar_width + (self._num_bars - 1) * self._bar_gap
        start_x = max(0, (self._width_px - total_w) / 2)
        center_y = self._height_px / 2
        min_h = 2
        max_h = self._height_px - 6

        for i, lvl in enumerate(self._levels):
            x = start_x + i * (self._bar_width + self._bar_gap)
            bar_h = min_h + lvl * (max_h - min_h)
            y1 = center_y - bar_h / 2
            y2 = center_y + bar_h / 2
            self._canvas.create_rectangle(
                x, y1, x + self._bar_width, y2,
                fill=self._color, outline=self._color,
            )


# ---------------------------------------------------------------------------
# Small-caps label with terracotta dot
# ---------------------------------------------------------------------------
class CapsLabel(ctk.CTkFrame):
    """A row with a terracotta dot + small-caps tracked text."""

    def __init__(
        self,
        master,
        text: str,
        dot_color: str = theme.ACCENT_PRIMARY,
        text_color: str = theme.TEXT_DARK,
        fg_color: str = "transparent",
        **kwargs,
    ):
        super().__init__(master, fg_color=fg_color, **kwargs)
        self._dot = ctk.CTkLabel(
            self,
            text="●",
            font=ctk.CTkFont(family=SANS_FAMILY, size=9),
            text_color=dot_color,
        )
        self._dot.pack(side="left", padx=(0, 6))
        # Small caps simulated by spaced uppercase
        display = text.upper()
        self._label = ctk.CTkLabel(
            self,
            text=display,
            font=ctk.CTkFont(family=SANS_FAMILY, size=10, weight="bold"),
            text_color=text_color,
        )
        self._label.pack(side="left")

    def set_text(self, text: str) -> None:
        self._label.configure(text=text.upper())


# ---------------------------------------------------------------------------
# Pill button (rounded action button)
# ---------------------------------------------------------------------------
class PillButton(ctk.CTkButton):
    """Pill-shaped action button. Two visual variants: filled (primary) and outlined."""

    def __init__(
        self,
        master,
        text: str,
        command: Optional[Callable] = None,
        variant: str = "outlined",
        accent: str = theme.ACCENT_PRIMARY,
        **kwargs,
    ):
        if variant == "filled":
            fg_color = accent
            hover_color = theme.ACCENT_PRIMARY_DARK
            text_color = theme.TEXT_LIGHT
            border_width = 0
            border_color = accent
            # 14pt bold qualifies as WCAG "large text" (3:1) on terracotta
            font = ctk.CTkFont(family=SANS_FAMILY, size=14, weight="bold")
        else:
            fg_color = "transparent"
            hover_color = theme.ACCENT_PRIMARY_LIGHT
            text_color = theme.TEXT_DARK
            border_width = 1
            border_color = theme.BG_OVERLAY_BORDER
            font = ctk.CTkFont(family=SANS_FAMILY, size=12)

        super().__init__(
            master,
            text=text,
            command=command,
            corner_radius=20,
            height=36,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            border_width=border_width,
            border_color=border_color,
            font=font,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Session card — centerpiece of the dashboard
# ---------------------------------------------------------------------------
class SessionCard(ctk.CTkFrame):
    """The large active-session card.

    Shows: small-caps status row, large serif headline, decorative waveform,
    body text, and a row of pill action buttons.
    """

    def __init__(
        self,
        master,
        hotkey_label: str = "Caps Lock",
        on_change_hotkey: Optional[Callable] = None,
        on_open_settings: Optional[Callable] = None,
        on_view_history: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BG_CARD, corner_radius=18, **kwargs)
        self._hotkey_label = hotkey_label

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=28, pady=24)

        # Header: small-caps status (left) — currently fixed at "READY · DICTATION ENABLED"
        header_row = ctk.CTkFrame(inner, fg_color="transparent")
        header_row.pack(fill="x")

        self._status = CapsLabel(header_row, "Ready · Dictation enabled")
        self._status.pack(side="left")

        # Large serif headline
        self._headline = ctk.CTkLabel(
            inner,
            text=self._format_headline(hotkey_label),
            font=ctk.CTkFont(family=SERIF_FAMILY, size=30),
            text_color=theme.TEXT_DARK,
            anchor="w",
            justify="left",
        )
        self._headline.pack(fill="x", pady=(14, 18), anchor="w")

        # Decorative waveform
        self._waveform = WaveformCanvas(
            inner,
            width=900,
            height=64,
            num_bars=90,
            bar_width=2,
            bar_gap=4,
            color=theme.ACCENT_PRIMARY,
            bg=theme.BG_CARD,
            seed="ditado-ready-state",
        )
        self._waveform.pack(fill="x", pady=(0, 18))

        # Body text in serif
        # Use a short two-line copy so it never collides with the card's
        # right edge regardless of the dashboard's resized width.
        body = ctk.CTkLabel(
            inner,
            text=(
                "Hold the hotkey, speak, release. Your words are transcribed,\n"
                "polished, and typed at the cursor — wherever you are."
            ),
            font=ctk.CTkFont(family=SERIF_FAMILY, size=15),
            text_color=theme.TEXT_DARK,
            justify="left",
            anchor="w",
        )
        body.pack(fill="x", pady=(0, 22), anchor="w")

        # Action pill row
        actions = ctk.CTkFrame(inner, fg_color="transparent")
        actions.pack(fill="x")

        PillButton(
            actions,
            text=f"  Change hotkey · {hotkey_label}  ",
            variant="filled",
            command=on_change_hotkey,
        ).pack(side="left", padx=(0, 10))

        PillButton(
            actions,
            text="  Open settings  ",
            variant="outlined",
            command=on_open_settings,
        ).pack(side="left", padx=(0, 10))

        PillButton(
            actions,
            text="  View history  ",
            variant="outlined",
            command=on_view_history,
        ).pack(side="left")

    @staticmethod
    def _format_headline(hotkey_label: str) -> str:
        return f"Press {hotkey_label} to start dictating."

    def set_hotkey_label(self, label: str) -> None:
        self._hotkey_label = label
        self._headline.configure(text=self._format_headline(label))


# ---------------------------------------------------------------------------
# History waveform card — small variant for the history row
# ---------------------------------------------------------------------------
class HistoryWaveCard(ctk.CTkFrame):
    """Compact history entry with a mini decorative waveform."""

    def __init__(
        self,
        master,
        timestamp_label: str,
        title_preview: str,
        duration_seconds: float,
        word_count: int,
        seed: str,
        on_click: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BG_CARD, corner_radius=14, **kwargs)
        self._on_click = on_click
        # Keep the full, untruncated text so the card can copy it to clipboard.
        self._full_text = title_preview

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=14)

        # Header row: timestamp small caps (left) + copy button (right).
        # The copy button lives here (not the footer) so it stays visible
        # even when the card's lower edge is clipped by the window.
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x")

        CapsLabel(
            header,
            text=timestamp_label,
            text_color=theme.TEXT_GRAY,
        ).pack(side="left")

        self._copy_btn = ctk.CTkButton(
            header,
            text="📋 Copy",
            width=64,
            height=24,
            corner_radius=8,
            fg_color="transparent",
            hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_GRAY,
            font=ctk.CTkFont(family=SANS_FAMILY, size=10),
            command=self._copy_to_clipboard,
        )
        self._copy_btn.pack(side="right")

        # Title preview (truncated, serif)
        preview = title_preview.replace("\n", " ").strip()
        if len(preview) > 48:
            preview = preview[:45].rstrip() + "…"

        ctk.CTkLabel(
            inner,
            text=preview,
            font=ctk.CTkFont(family=SERIF_FAMILY, size=15),
            text_color=theme.TEXT_DARK,
            anchor="w",
            justify="left",
            wraplength=240,
        ).pack(fill="x", anchor="w", pady=(8, 10))

        # Mini waveform
        WaveformCanvas(
            inner,
            width=240,
            height=26,
            num_bars=42,
            bar_width=2,
            bar_gap=3,
            color=theme.ACCENT_PRIMARY,
            bg=theme.BG_CARD,
            seed=seed,
        ).pack(anchor="w", pady=(0, 8))

        # Footer: duration · words
        duration_str = self._format_duration(duration_seconds)
        ctk.CTkLabel(
            inner,
            text=f"{duration_str}  ·  {word_count} words",
            font=ctk.CTkFont(family=SANS_FAMILY, size=10),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w")

        # Click-through and hover affordance. Clicking anywhere on the card
        # (except the copy button) copies the full text to the clipboard.
        for widget in (self, inner, header, *inner.winfo_children()):
            if widget is self._copy_btn:
                continue
            widget.bind("<Button-1>", self._handle_click)
        # Bind the timestamp label inside the header too (but never the button).
        for widget in header.winfo_children():
            if widget is not self._copy_btn:
                widget.bind("<Button-1>", self._handle_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f} sec"
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m} min {s:02d} sec" if s else f"{m} min"

    def _handle_click(self, _event=None) -> None:
        if self._on_click:
            self._on_click()
        else:
            # Default affordance: clicking the card copies its full text.
            self._copy_to_clipboard()

    def _copy_to_clipboard(self) -> None:
        """Copy the full transcription text to the clipboard, with feedback."""
        try:
            self.clipboard_clear()
            self.clipboard_append(self._full_text)
            self.update_idletasks()  # required for the clipboard to take effect

            # Brief visual confirmation on the button.
            self._copy_btn.configure(text="✓ Copied", text_color=theme.SUCCESS_TEXT)
            self.after(
                1500,
                lambda: self._copy_btn.winfo_exists()
                and self._copy_btn.configure(text="📋 Copy", text_color=theme.TEXT_GRAY),
            )
        except Exception:
            pass  # silently ignore if clipboard is unavailable

    def _on_enter(self, _event=None) -> None:
        self.configure(fg_color=theme.BG_CARD_HOVER)

    def _on_leave(self, _event=None) -> None:
        self.configure(fg_color=theme.BG_CARD)


# ---------------------------------------------------------------------------
# Streak counter (top-right tiny card)
# ---------------------------------------------------------------------------
class StreakCard(ctk.CTkFrame):
    """Tiny streak counter card, terracotta-tinted."""

    def __init__(self, master, days: int, **kwargs):
        super().__init__(
            master,
            fg_color=theme.ACCENT_PRIMARY_LIGHT,
            corner_radius=12,
            **kwargs,
        )

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(padx=14, pady=10)

        # Left column: tiny "day streak" label
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            left,
            text="DAY",
            font=ctk.CTkFont(family=SANS_FAMILY, size=9, weight="bold"),
            text_color=theme.ACCENT_PRIMARY_TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="STREAK",
            font=ctk.CTkFont(family=SANS_FAMILY, size=9, weight="bold"),
            text_color=theme.ACCENT_PRIMARY_TEXT,
        ).pack(anchor="w")

        # Right: big number in serif
        ctk.CTkLabel(
            inner,
            text=str(days),
            font=ctk.CTkFont(family=SERIF_FAMILY, size=28),
            text_color=theme.ACCENT_PRIMARY_DARK,
        ).pack(side="left")
