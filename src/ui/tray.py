"""System tray integration for Ditado."""

import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw
import pystray


class SystemTray:
    """System tray icon with menu."""

    def __init__(
        self,
        on_toggle: Optional[Callable[[bool], None]] = None,
        on_settings: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        on_usage: Optional[Callable[[], None]] = None,
        on_dashboard: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize the system tray.

        Args:
            on_toggle: Callback when enabled/disabled is toggled
            on_settings: Callback when Settings is clicked (opens dashboard)
            on_exit: Callback when Exit is clicked
            on_usage: Callback when Usage Stats is clicked
            on_dashboard: Callback when Show Dashboard is clicked
        """
        self._on_toggle = on_toggle
        self._on_exit = on_exit
        self._on_usage = on_usage
        # Settings and Dashboard now both open the unified dashboard
        self._on_dashboard = on_dashboard or on_settings
        self._enabled = True
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the system tray icon."""
        if self._icon is not None:
            return

        # Create the icon
        image = self._create_icon()

        # Create menu (Settings integrated into Dashboard)
        menu = pystray.Menu(
            pystray.MenuItem("Show Dashboard", self._show_dashboard),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Enabled",
                self._toggle_enabled,
                checked=lambda item: self._enabled,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._exit),
        )

        self._icon = pystray.Icon(
            name="Ditado",
            icon=image,
            title="Ditado - Voice Dictation",
            menu=menu,
        )

        # Run in a separate thread
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the system tray icon."""
        if self._icon:
            self._icon.stop()
            self._icon = None

    def set_enabled(self, enabled: bool) -> None:
        """Update the enabled state."""
        self._enabled = enabled
        if self._icon:
            self._icon.icon = self._create_icon()

    def show_notification(self, title: str, message: str) -> None:
        """Show a system notification."""
        if self._icon:
            self._icon.notify(message, title)

    def _create_icon(self) -> Image.Image:
        """Create the tray icon image."""
        # Create a simple microphone icon
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Background circle
        bg_color = "#E53935" if self._enabled else "#666666"
        draw.ellipse([4, 4, size - 4, size - 4], fill=bg_color)

        # Microphone body (simplified)
        mic_color = "#FFFFFF"
        center_x = size // 2
        center_y = size // 2

        # Mic head
        draw.ellipse(
            [center_x - 10, center_y - 18, center_x + 10, center_y - 2],
            fill=mic_color
        )

        # Mic body
        draw.rectangle(
            [center_x - 10, center_y - 12, center_x + 10, center_y + 5],
            fill=mic_color
        )

        # Mic base
        draw.ellipse(
            [center_x - 10, center_y, center_x + 10, center_y + 10],
            fill=mic_color
        )

        # Stand
        draw.line(
            [center_x, center_y + 10, center_x, center_y + 20],
            fill=mic_color, width=4
        )
        draw.line(
            [center_x - 10, center_y + 20, center_x + 10, center_y + 20],
            fill=mic_color, width=4
        )

        return image

    def _show_dashboard(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """Show the dashboard window."""
        if self._on_dashboard:
            self._on_dashboard()

    def _toggle_enabled(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """Toggle enabled state."""
        self._enabled = not self._enabled
        icon.icon = self._create_icon()
        if self._on_toggle:
            self._on_toggle(self._enabled)

    def _exit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """Exit the application."""
        if self._on_exit:
            self._on_exit()
        self.stop()
