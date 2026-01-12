"""Modern recording overlay indicator for Ditado - Wispr Flow inspired."""

import tkinter as tk
from typing import Optional, List
import threading
import math
import random


class RecordingOverlay:
    """Modern floating overlay with animated soundwave indicator."""

    # Pill shape dimensions
    WIDTH = 80
    HEIGHT = 36
    CORNER_RADIUS = 18

    # Colors matching dashboard theme
    BG_COLOR = "#1E1E1E"          # Dark background (matches sidebar)
    BAR_RECORDING = "#D4E157"     # Lime for recording
    BAR_PROCESSING = "#42A5F5"    # Blue for transcribing
    BAR_ENHANCING = "#AB47BC"     # Purple for enhancing
    BAR_SUCCESS = "#66BB6A"       # Green for typing/success

    # Animation settings
    NUM_BARS = 5
    BAR_WIDTH = 4
    BAR_GAP = 6
    MIN_BAR_HEIGHT = 4
    MAX_BAR_HEIGHT = 20
    ANIMATION_SPEED = 33  # ~30fps

    def __init__(self, position: str = "top-right"):
        """
        Initialize the recording overlay.

        Args:
            position: Screen position (top-left, top-right, bottom-left, bottom-right, bottom-center)
        """
        self._position = position
        self._root: Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None
        self._state = "idle"
        self._visible = False
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._update_queue: List[str] = []

        # Animation state
        self._animation_frame = 0
        self._bar_heights: List[float] = [self.MIN_BAR_HEIGHT] * self.NUM_BARS
        self._bar_targets: List[float] = [self.MIN_BAR_HEIGHT] * self.NUM_BARS
        self._bar_phases: List[float] = [i * 0.8 for i in range(self.NUM_BARS)]

        # Success animation
        self._success_progress = 0.0

    def start(self) -> None:
        """Start the overlay in a separate thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the overlay."""
        self._running = False
        if self._root:
            try:
                self._root.quit()
            except Exception:
                pass

    def show(self) -> None:
        """Show the overlay."""
        self._update_queue.append("show")

    def hide(self) -> None:
        """Hide the overlay."""
        self._update_queue.append("hide")

    def set_state(self, state: str) -> None:
        """Set the overlay state (idle, recording, transcribing, enhancing, typing)."""
        self._update_queue.append(f"state:{state}")

    def set_position(self, position: str) -> None:
        """Set the corner position."""
        self._position = position
        self._update_queue.append("reposition")

    def _run(self) -> None:
        """Run the Tkinter mainloop in a separate thread."""
        self._root = tk.Tk()
        self._root.title("Ditado")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.95)
        self._root.withdraw()

        # Transparent window background
        self._root.configure(bg='black')
        try:
            self._root.attributes("-transparentcolor", "black")
        except Exception:
            pass

        # Create canvas with transparent background
        self._canvas = tk.Canvas(
            self._root,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg="black",
            highlightthickness=0,
        )
        self._canvas.pack()

        # Initial draw and position
        self._draw_indicator()
        self._update_position()

        # Start animation loop
        self._root.after(self.ANIMATION_SPEED, self._animation_loop)
        self._root.mainloop()

    def _animation_loop(self) -> None:
        """Main animation loop."""
        if not self._running:
            return

        # Process command queue
        self._process_commands()

        # Animate if visible
        if self._visible:
            self._update_animation()
            self._draw_indicator()

        # Schedule next frame
        if self._running and self._root:
            self._root.after(self.ANIMATION_SPEED, self._animation_loop)

    def _process_commands(self) -> None:
        """Process queued commands."""
        while self._update_queue:
            cmd = self._update_queue.pop(0)

            if cmd == "show":
                self._root.deiconify()
                self._visible = True
                self._animation_frame = 0
                self._success_progress = 0.0
            elif cmd == "hide":
                self._root.withdraw()
                self._visible = False
            elif cmd.startswith("state:"):
                new_state = cmd.split(":")[1]
                if new_state != self._state:
                    self._state = new_state
                    self._success_progress = 0.0
            elif cmd == "reposition":
                self._update_position()

    def _update_animation(self) -> None:
        """Update animation based on current state."""
        self._animation_frame += 1

        if self._state == "recording":
            self._animate_recording()
        elif self._state in ("transcribing", "processing"):
            self._animate_processing()
        elif self._state == "enhancing":
            self._animate_enhancing()
        elif self._state == "typing":
            self._animate_success()
        else:
            # Idle - bars at minimum
            for i in range(self.NUM_BARS):
                self._bar_targets[i] = self.MIN_BAR_HEIGHT

        # Smooth interpolation of bar heights
        self._interpolate_bars()

    def _animate_recording(self) -> None:
        """Animate soundwave bars during recording - energetic, random."""
        for i in range(self.NUM_BARS):
            # Sine wave base + randomness for natural feel
            phase = self._animation_frame * 0.2 + self._bar_phases[i]
            base = (math.sin(phase) + 1) / 2

            # Add some randomness
            noise = random.uniform(-0.15, 0.15)
            height_ratio = base + noise

            # Clamp and scale
            height_ratio = max(0.2, min(1.0, height_ratio))
            self._bar_targets[i] = (
                self.MIN_BAR_HEIGHT +
                height_ratio * (self.MAX_BAR_HEIGHT - self.MIN_BAR_HEIGHT)
            )

    def _animate_processing(self) -> None:
        """Animate wave effect during processing - slower, wave-like."""
        for i in range(self.NUM_BARS):
            # Slower sine wave, sequential phase
            phase = self._animation_frame * 0.1 + i * 0.6
            base = (math.sin(phase) + 1) / 2

            height_ratio = 0.3 + base * 0.5  # More subtle range
            self._bar_targets[i] = (
                self.MIN_BAR_HEIGHT +
                height_ratio * (self.MAX_BAR_HEIGHT - self.MIN_BAR_HEIGHT)
            )

    def _animate_enhancing(self) -> None:
        """Animate during enhancement - similar to processing but different color."""
        self._animate_processing()

    def _animate_success(self) -> None:
        """Animate success state - bars collapse then checkmark."""
        self._success_progress = min(1.0, self._success_progress + 0.08)

        # Bars collapse down
        collapse_ratio = 1.0 - self._success_progress
        for i in range(self.NUM_BARS):
            self._bar_targets[i] = self.MIN_BAR_HEIGHT + collapse_ratio * (
                self._bar_heights[i] - self.MIN_BAR_HEIGHT
            )

    def _interpolate_bars(self) -> None:
        """Smoothly interpolate bar heights toward targets."""
        lerp_speed = 0.3  # Interpolation speed
        for i in range(self.NUM_BARS):
            diff = self._bar_targets[i] - self._bar_heights[i]
            self._bar_heights[i] += diff * lerp_speed

    def _update_position(self) -> None:
        """Update window position based on position setting."""
        if not self._root:
            return

        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()

        padding = 20
        taskbar_height = 40  # Account for Windows taskbar

        if self._position == "top-left":
            x = padding
            y = padding
        elif self._position == "top-right":
            x = screen_width - self.WIDTH - padding
            y = padding
        elif self._position == "bottom-left":
            x = padding
            y = screen_height - self.HEIGHT - padding - taskbar_height
        elif self._position == "bottom-center":
            # Center horizontally, near bottom (like Wispr Flow)
            x = (screen_width - self.WIDTH) // 2
            y = screen_height - self.HEIGHT - padding - taskbar_height
        else:  # bottom-right
            x = screen_width - self.WIDTH - padding
            y = screen_height - self.HEIGHT - padding - taskbar_height

        self._root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

    def _draw_indicator(self) -> None:
        """Draw the indicator based on current state."""
        if not self._canvas:
            return

        self._canvas.delete("all")

        # Draw pill-shaped background
        self._draw_rounded_rect(
            0, 0, self.WIDTH, self.HEIGHT,
            self.CORNER_RADIUS, self.BG_COLOR
        )

        # Get bar color based on state
        if self._state == "recording":
            bar_color = self.BAR_RECORDING
        elif self._state in ("transcribing", "processing"):
            bar_color = self.BAR_PROCESSING
        elif self._state == "enhancing":
            bar_color = self.BAR_ENHANCING
        elif self._state == "typing":
            bar_color = self.BAR_SUCCESS
        else:
            bar_color = "#555555"  # Idle gray

        # Draw soundwave bars or checkmark
        if self._state == "typing" and self._success_progress > 0.7:
            # Draw checkmark when bars have collapsed
            self._draw_checkmark(bar_color)
        else:
            # Draw soundwave bars
            self._draw_soundwave_bars(bar_color)

    def _draw_soundwave_bars(self, color: str) -> None:
        """Draw the animated soundwave bars."""
        # Calculate total width of bars
        total_width = (
            self.NUM_BARS * self.BAR_WIDTH +
            (self.NUM_BARS - 1) * self.BAR_GAP
        )
        start_x = (self.WIDTH - total_width) / 2
        center_y = self.HEIGHT / 2

        for i in range(self.NUM_BARS):
            x = start_x + i * (self.BAR_WIDTH + self.BAR_GAP)
            height = self._bar_heights[i]
            y1 = center_y - height / 2
            y2 = center_y + height / 2

            # Draw rounded bar
            self._draw_rounded_rect(
                x, y1, x + self.BAR_WIDTH, y2,
                self.BAR_WIDTH / 2, color
            )

    def _draw_checkmark(self, color: str) -> None:
        """Draw a checkmark icon."""
        cx = self.WIDTH / 2
        cy = self.HEIGHT / 2
        size = 10

        # Checkmark path
        self._canvas.create_line(
            cx - size * 0.6, cy,
            cx - size * 0.1, cy + size * 0.5,
            fill=color, width=3, capstyle="round"
        )
        self._canvas.create_line(
            cx - size * 0.1, cy + size * 0.5,
            cx + size * 0.7, cy - size * 0.4,
            fill=color, width=3, capstyle="round"
        )

    def _draw_rounded_rect(
        self, x1: float, y1: float, x2: float, y2: float,
        radius: float, color: str
    ) -> None:
        """Draw a rounded rectangle using canvas arcs and polygons."""
        # Ensure minimum dimensions
        width = x2 - x1
        height = y2 - y1
        radius = min(radius, width / 2, height / 2)

        # Create rounded rectangle using multiple shapes
        points = []

        # Top side
        points.extend([x1 + radius, y1])
        points.extend([x2 - radius, y1])

        # Top-right corner
        points.extend([x2, y1])
        points.extend([x2, y1 + radius])

        # Right side
        points.extend([x2, y2 - radius])

        # Bottom-right corner
        points.extend([x2, y2])
        points.extend([x2 - radius, y2])

        # Bottom side
        points.extend([x1 + radius, y2])

        # Bottom-left corner
        points.extend([x1, y2])
        points.extend([x1, y2 - radius])

        # Left side
        points.extend([x1, y1 + radius])

        # Top-left corner
        points.extend([x1, y1])
        points.extend([x1 + radius, y1])

        # Draw as smooth polygon
        self._canvas.create_polygon(
            points,
            fill=color,
            outline=color,
            smooth=True,
        )

        # Draw corner arcs for smoother corners
        # Top-left
        self._canvas.create_arc(
            x1, y1, x1 + radius * 2, y1 + radius * 2,
            start=90, extent=90, fill=color, outline=color
        )
        # Top-right
        self._canvas.create_arc(
            x2 - radius * 2, y1, x2, y1 + radius * 2,
            start=0, extent=90, fill=color, outline=color
        )
        # Bottom-right
        self._canvas.create_arc(
            x2 - radius * 2, y2 - radius * 2, x2, y2,
            start=270, extent=90, fill=color, outline=color
        )
        # Bottom-left
        self._canvas.create_arc(
            x1, y2 - radius * 2, x1 + radius * 2, y2,
            start=180, extent=90, fill=color, outline=color
        )

        # Fill center rectangles
        self._canvas.create_rectangle(
            x1 + radius, y1, x2 - radius, y2,
            fill=color, outline=color
        )
        self._canvas.create_rectangle(
            x1, y1 + radius, x2, y2 - radius,
            fill=color, outline=color
        )
