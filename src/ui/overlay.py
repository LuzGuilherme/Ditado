"""Recording overlay for Ditado - "Soft Warmth" identity.

A floating cream-coloured pill that hosts an animated waveform. The waveform
reacts to real microphone audio level during recording (rolling buffer), and
falls back to scripted motion during transcribing / enhancing / typing states.
"""

import tkinter as tk
from typing import Optional, List
import threading
import math
import random

from . import theme


class RecordingOverlay:
    """Floating waveform indicator in Soft Warmth style."""

    # Pill geometry — wider than the old design to host a real waveform
    WIDTH = 200
    HEIGHT = 44
    CORNER_RADIUS = 22

    # Waveform
    NUM_BARS = 13
    BAR_WIDTH = 3
    BAR_GAP = 5
    MIN_BAR_HEIGHT = 3
    MAX_BAR_HEIGHT = 28

    # Animation cadence (~30fps)
    ANIMATION_SPEED_MS = 33

    # Color used as the "transparent" key — picked to never appear in the design
    CHROMA_KEY = "magenta"

    def __init__(self, position: str = "bottom-center"):
        """
        Args:
            position: Screen position (top-left, top-right, bottom-left,
                      bottom-right, bottom-center).
        """
        self._position = position
        self._root: Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None
        self._state = "idle"
        self._visible = False
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._update_queue: List[str] = []

        # Animation frame counter
        self._animation_frame = 0

        # Per-bar interpolated height (smooth render)
        self._bar_heights: List[float] = [self.MIN_BAR_HEIGHT] * self.NUM_BARS
        # Per-bar target height (driven by audio level or scripted animation)
        self._bar_targets: List[float] = [self.MIN_BAR_HEIGHT] * self.NUM_BARS

        # Rolling buffer of recent normalized audio levels (oldest..newest).
        # During recording each bar reads from a position in this buffer so
        # the waveform appears to scroll right-to-left.
        self._level_buffer: List[float] = [0.0] * self.NUM_BARS
        self._level_lock = threading.Lock()
        self._buffer_dirty = False

        # Success animation progress
        self._success_progress = 0.0

    # ------------------------------------------------------------------ API
    def start(self) -> None:
        """Start the overlay in a dedicated Tkinter thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Tear down the overlay window."""
        self._running = False
        if self._root:
            try:
                self._root.quit()
                self._root.destroy()
            except Exception:
                pass
            self._root = None

    def show(self) -> None:
        self._update_queue.append("show")

    def hide(self) -> None:
        self._update_queue.append("hide")

    def set_state(self, state: str) -> None:
        """idle | recording | transcribing | enhancing | typing"""
        self._update_queue.append(f"state:{state}")

    def set_position(self, position: str) -> None:
        self._position = position
        self._update_queue.append("reposition")

    def set_audio_level(self, level: float) -> None:
        """Push a new normalized audio level (0..1) into the rolling buffer.

        Called from the recorder's audio thread — must be cheap and lock-safe.
        """
        # Light non-linear shaping so quiet speech still produces visible bars
        # without saturating on loud peaks.
        shaped = min(1.0, math.pow(max(0.0, level) * 8.0, 0.7))
        with self._level_lock:
            self._level_buffer.append(shaped)
            if len(self._level_buffer) > self.NUM_BARS:
                self._level_buffer = self._level_buffer[-self.NUM_BARS:]
            self._buffer_dirty = True

    # ---------------------------------------------------------- Tk thread
    def _run(self) -> None:
        """Tk mainloop on this thread."""
        self._root = tk.Tk()
        self._root.title("Ditado")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.97)
        self._root.withdraw()

        # Set icon (delayed to override CustomTkinter defaults if any)
        try:
            from .tray import get_asset_path
            icon_path = get_asset_path("icon.ico")
            self._root.after(300, lambda: self._root.iconbitmap(icon_path))
        except Exception:
            pass

        # Chroma-key transparency: anything painted in CHROMA_KEY becomes see-through.
        self._root.configure(bg=self.CHROMA_KEY)
        try:
            self._root.attributes("-transparentcolor", self.CHROMA_KEY)
        except Exception:
            pass

        self._canvas = tk.Canvas(
            self._root,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=self.CHROMA_KEY,
            highlightthickness=0,
        )
        self._canvas.pack()

        self._draw_indicator()
        self._update_position()

        self._root.after(self.ANIMATION_SPEED_MS, self._animation_loop)
        self._root.mainloop()

    def _animation_loop(self) -> None:
        if not self._running:
            return

        self._process_commands()

        if self._visible:
            self._update_animation()
            self._draw_indicator()

        if self._running and self._root:
            self._root.after(self.ANIMATION_SPEED_MS, self._animation_loop)

    def _process_commands(self) -> None:
        while self._update_queue:
            cmd = self._update_queue.pop(0)

            if cmd == "show":
                self._root.deiconify()
                self._visible = True
                self._animation_frame = 0
                self._success_progress = 0.0
                # Reset the level buffer so the previous session's tail
                # doesn't bleed into the next recording.
                with self._level_lock:
                    self._level_buffer = [0.0] * self.NUM_BARS
            elif cmd == "hide":
                self._root.withdraw()
                self._visible = False
            elif cmd.startswith("state:"):
                new_state = cmd.split(":", 1)[1]
                if new_state != self._state:
                    self._state = new_state
                    self._success_progress = 0.0
            elif cmd == "reposition":
                self._update_position()

    # --------------------------------------------------------- Animation
    def _update_animation(self) -> None:
        self._animation_frame += 1

        if self._state == "recording":
            self._animate_recording()
        elif self._state in ("transcribing", "processing"):
            self._animate_transcribing()
        elif self._state == "enhancing":
            self._animate_enhancing()
        elif self._state == "typing":
            self._animate_success()
        else:
            for i in range(self.NUM_BARS):
                self._bar_targets[i] = self.MIN_BAR_HEIGHT

        self._interpolate_bars()

    def _animate_recording(self) -> None:
        """Drive each bar from the rolling audio-level buffer.

        Bars on the right are most recent (newest sample), bars on the left
        are older — creates a natural right-to-left scrolling waveform.
        """
        with self._level_lock:
            buf = list(self._level_buffer)

        # Pad / trim defensively
        if len(buf) < self.NUM_BARS:
            buf = [0.0] * (self.NUM_BARS - len(buf)) + buf
        else:
            buf = buf[-self.NUM_BARS:]

        for i in range(self.NUM_BARS):
            level = buf[i]
            # Mirror symmetric (center taller — gentle stylization)
            center_boost = 1.0 - abs((i - (self.NUM_BARS - 1) / 2)) / self.NUM_BARS * 0.15
            height = (
                self.MIN_BAR_HEIGHT
                + level * (self.MAX_BAR_HEIGHT - self.MIN_BAR_HEIGHT) * center_boost
            )
            self._bar_targets[i] = height

    def _animate_transcribing(self) -> None:
        """Slow shimmer while we wait for Whisper."""
        for i in range(self.NUM_BARS):
            phase = self._animation_frame * 0.12 + i * 0.45
            base = (math.sin(phase) + 1) / 2
            ratio = 0.25 + base * 0.4
            self._bar_targets[i] = (
                self.MIN_BAR_HEIGHT
                + ratio * (self.MAX_BAR_HEIGHT - self.MIN_BAR_HEIGHT)
            )

    def _animate_enhancing(self) -> None:
        """Slightly faster shimmer for GPT cleanup phase, with travelling peak."""
        for i in range(self.NUM_BARS):
            # Travelling crest
            phase = self._animation_frame * 0.18 - i * 0.35
            base = (math.sin(phase) + 1) / 2
            ratio = 0.3 + base * 0.5
            self._bar_targets[i] = (
                self.MIN_BAR_HEIGHT
                + ratio * (self.MAX_BAR_HEIGHT - self.MIN_BAR_HEIGHT)
            )

    def _animate_success(self) -> None:
        """Bars collapse toward zero, then a checkmark fades in."""
        self._success_progress = min(1.0, self._success_progress + 0.08)
        collapse_ratio = 1.0 - self._success_progress
        for i in range(self.NUM_BARS):
            self._bar_targets[i] = self.MIN_BAR_HEIGHT + collapse_ratio * (
                self._bar_heights[i] - self.MIN_BAR_HEIGHT
            )

    def _interpolate_bars(self) -> None:
        lerp = 0.35
        for i in range(self.NUM_BARS):
            diff = self._bar_targets[i] - self._bar_heights[i]
            self._bar_heights[i] += diff * lerp

    # ---------------------------------------------------------- Position
    def _update_position(self) -> None:
        if not self._root:
            return
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        pad = 20
        taskbar = 40

        if self._position == "top-left":
            x, y = pad, pad
        elif self._position == "top-right":
            x, y = sw - self.WIDTH - pad, pad
        elif self._position == "bottom-left":
            x, y = pad, sh - self.HEIGHT - pad - taskbar
        elif self._position == "bottom-center":
            x = (sw - self.WIDTH) // 2
            y = sh - self.HEIGHT - pad - taskbar
        else:  # bottom-right (default)
            x = sw - self.WIDTH - pad
            y = sh - self.HEIGHT - pad - taskbar

        self._root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

    # --------------------------------------------------------- Rendering
    def _draw_indicator(self) -> None:
        if not self._canvas:
            return
        self._canvas.delete("all")

        # Pill background (cream paper)
        self._draw_rounded_rect(
            1, 1, self.WIDTH - 1, self.HEIGHT - 1,
            self.CORNER_RADIUS - 1, theme.BG_OVERLAY
        )
        # Soft 1px warm border on top of the pill
        self._draw_rounded_outline(
            1, 1, self.WIDTH - 1, self.HEIGHT - 1,
            self.CORNER_RADIUS - 1, theme.BG_OVERLAY_BORDER
        )

        # Pick bar color based on state
        if self._state == "recording":
            bar_color = theme.STATE_RECORDING
        elif self._state in ("transcribing", "processing"):
            bar_color = theme.STATE_TRANSCRIBING
        elif self._state == "enhancing":
            bar_color = theme.STATE_ENHANCING
        elif self._state == "typing":
            bar_color = theme.STATE_TYPING
        else:
            bar_color = theme.TEXT_MUTED

        if self._state == "typing" and self._success_progress > 0.6:
            self._draw_checkmark(bar_color)
        else:
            self._draw_waveform(bar_color)

    def _draw_waveform(self, color: str) -> None:
        total_w = (
            self.NUM_BARS * self.BAR_WIDTH
            + (self.NUM_BARS - 1) * self.BAR_GAP
        )
        start_x = (self.WIDTH - total_w) / 2
        center_y = self.HEIGHT / 2

        for i in range(self.NUM_BARS):
            x = start_x + i * (self.BAR_WIDTH + self.BAR_GAP)
            h = max(self.MIN_BAR_HEIGHT, self._bar_heights[i])
            y1 = center_y - h / 2
            y2 = center_y + h / 2
            # Rounded vertical bar
            self._draw_rounded_rect(
                x, y1, x + self.BAR_WIDTH, y2,
                self.BAR_WIDTH / 2, color
            )

    def _draw_checkmark(self, color: str) -> None:
        cx = self.WIDTH / 2
        cy = self.HEIGHT / 2
        size = 12
        self._canvas.create_line(
            cx - size * 0.6, cy,
            cx - size * 0.1, cy + size * 0.5,
            fill=color, width=3, capstyle="round",
        )
        self._canvas.create_line(
            cx - size * 0.1, cy + size * 0.5,
            cx + size * 0.7, cy - size * 0.4,
            fill=color, width=3, capstyle="round",
        )

    # ------------------------------------------------- Shape primitives
    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, color):
        """Filled rounded rectangle via arcs + rectangles."""
        radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
        # Corner arcs
        self._canvas.create_arc(
            x1, y1, x1 + radius * 2, y1 + radius * 2,
            start=90, extent=90, fill=color, outline=color,
        )
        self._canvas.create_arc(
            x2 - radius * 2, y1, x2, y1 + radius * 2,
            start=0, extent=90, fill=color, outline=color,
        )
        self._canvas.create_arc(
            x2 - radius * 2, y2 - radius * 2, x2, y2,
            start=270, extent=90, fill=color, outline=color,
        )
        self._canvas.create_arc(
            x1, y2 - radius * 2, x1 + radius * 2, y2,
            start=180, extent=90, fill=color, outline=color,
        )
        # Two rectangles to fill the cross
        self._canvas.create_rectangle(
            x1 + radius, y1, x2 - radius, y2,
            fill=color, outline=color,
        )
        self._canvas.create_rectangle(
            x1, y1 + radius, x2, y2 - radius,
            fill=color, outline=color,
        )

    def _draw_rounded_outline(self, x1, y1, x2, y2, radius, color):
        """1px rounded outline (for the warm border)."""
        radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
        # Corner arcs as 1px strokes
        self._canvas.create_arc(
            x1, y1, x1 + radius * 2, y1 + radius * 2,
            start=90, extent=90, style="arc", outline=color, width=1,
        )
        self._canvas.create_arc(
            x2 - radius * 2, y1, x2, y1 + radius * 2,
            start=0, extent=90, style="arc", outline=color, width=1,
        )
        self._canvas.create_arc(
            x2 - radius * 2, y2 - radius * 2, x2, y2,
            start=270, extent=90, style="arc", outline=color, width=1,
        )
        self._canvas.create_arc(
            x1, y2 - radius * 2, x1 + radius * 2, y2,
            start=180, extent=90, style="arc", outline=color, width=1,
        )
        # Straight edges
        self._canvas.create_line(x1 + radius, y1, x2 - radius, y1, fill=color, width=1)
        self._canvas.create_line(x1 + radius, y2, x2 - radius, y2, fill=color, width=1)
        self._canvas.create_line(x1, y1 + radius, x1, y2 - radius, fill=color, width=1)
        self._canvas.create_line(x2, y1 + radius, x2, y2 - radius, fill=color, width=1)
