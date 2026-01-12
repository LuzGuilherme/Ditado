"""Unified Dashboard for Ditado - Modern Light Theme Design."""

import customtkinter as ctk
import threading
import webbrowser
from typing import Callable, Optional, List
from .. import __version__
from ..config.settings import Settings
from ..config.history import TranscriptionHistory, TranscriptionHistoryEntry, format_relative_time
from ..transcription.whisper import SUPPORTED_LANGUAGES
from ..input.hotkey import KeyCombinationCaptureDialog, format_hotkey_display
from ..audio.recorder import list_audio_devices


# ============================================
# COLOR PALETTE - Modern Light Theme
# ============================================
# Background colors
BG_MAIN = "#E8E4D9"           # Warm cream/beige background
BG_SIDEBAR = "#1E1E1E"        # Dark charcoal sidebar
BG_CARD = "#FFFFFF"           # White cards
BG_CARD_HOVER = "#F5F5F0"     # Slightly darker card bg on hover

# Accent colors
ACCENT_LIME = "#D4E157"       # Bright lime/yellow-green (primary accent)
ACCENT_LIME_DARK = "#C0CA33"  # Darker lime for hover
ACCENT_LIME_LIGHT = "#F0F4C3" # Light lime for backgrounds

# Text colors
TEXT_DARK = "#1E1E1E"         # Primary text (near black)
TEXT_GRAY = "#757575"         # Secondary text
TEXT_LIGHT = "#FFFFFF"        # Text on dark backgrounds
TEXT_MUTED = "#9E9E9E"        # Muted/disabled text

# Status colors
SUCCESS = "#66BB6A"           # Green for success
ERROR = "#EF5350"             # Red for errors
WARNING = "#FFA726"           # Orange for warnings

# Sidebar icon colors
ICON_INACTIVE = "#6B6B6B"
ICON_ACTIVE = "#FFFFFF"


class ModernStatsCard(ctk.CTkFrame):
    """Modern statistics card with progress bar visualization."""

    def __init__(
        self,
        parent,
        title: str,
        value: str,
        subtitle: str = "",
        percentage: int = 0,
        icon: str = "",
        accent_color: str = ACCENT_LIME,
        **kwargs
    ):
        super().__init__(parent, fg_color=BG_CARD, corner_radius=16, **kwargs)

        self._percentage = percentage
        self._accent_color = accent_color

        # Main content container
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=16)

        # Header row with icon and percentage
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x")

        # Left: Icon + Title
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left")

        if icon:
            ctk.CTkLabel(
                left, text=icon,
                font=ctk.CTkFont(size=16),
                text_color=TEXT_GRAY,
            ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            left, text=title,
            font=ctk.CTkFont(size=13),
            text_color=TEXT_GRAY,
        ).pack(side="left")

        # Right: Percentage badge
        if percentage > 0:
            badge_frame = ctk.CTkFrame(header, fg_color="transparent")
            badge_frame.pack(side="right")

            ctk.CTkLabel(
                badge_frame, text=f"{percentage}%",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=TEXT_DARK,
            ).pack(side="left", padx=(0, 4))

            # Circular progress indicator (simplified as text)
            ctk.CTkLabel(
                badge_frame, text="●",
                font=ctk.CTkFont(size=14),
                text_color=accent_color,
            ).pack(side="left")

        # Value row
        value_frame = ctk.CTkFrame(content, fg_color="transparent")
        value_frame.pack(fill="x", pady=(12, 0))

        self._value_label = ctk.CTkLabel(
            value_frame, text=value,
            font=ctk.CTkFont(size=36, weight="bold"),
            text_color=TEXT_DARK,
        )
        self._value_label.pack(side="left")

        if subtitle:
            ctk.CTkLabel(
                value_frame, text=f"/{subtitle}",
                font=ctk.CTkFont(size=14),
                text_color=TEXT_MUTED,
            ).pack(side="left", anchor="s", pady=(0, 6))

        # Progress bar visualization (series of rectangles)
        bar_frame = ctk.CTkFrame(content, fg_color="transparent", height=30)
        bar_frame.pack(fill="x", pady=(12, 0))
        bar_frame.pack_propagate(False)

        self._bars = []
        for i in range(8):
            bar = ctk.CTkFrame(
                bar_frame,
                fg_color=accent_color if i < (percentage // 12.5) else "#E0E0E0",
                corner_radius=4,
                width=24,
                height=30,
            )
            bar.pack(side="left", padx=2)
            self._bars.append(bar)

    def set_value(self, value: str) -> None:
        self._value_label.configure(text=value)

    def set_percentage(self, percentage: int) -> None:
        self._percentage = percentage
        filled = int(percentage // 12.5)
        for i, bar in enumerate(self._bars):
            bar.configure(fg_color=self._accent_color if i < filled else "#E0E0E0")


class InfoCard(ctk.CTkFrame):
    """Promotional/info card with gradient-like background."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=ACCENT_LIME, corner_radius=16, **kwargs)

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            content, text="Voice Dictation",
            font=ctk.CTkFont(size=14),
            text_color=TEXT_DARK,
        ).pack(anchor="w")

        ctk.CTkLabel(
            content, text="Take Your\nProductivity to\nthe Next Level",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_DARK,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        # Spacer
        ctk.CTkFrame(content, fg_color="transparent").pack(fill="both", expand=True)

        # Hotkey hint button
        self._hint_btn = ctk.CTkButton(
            content,
            text="Hold [Key] to speak",
            fg_color=BG_CARD,
            hover_color=BG_CARD_HOVER,
            text_color=TEXT_DARK,
            corner_radius=20,
            height=36,
            font=ctk.CTkFont(size=12),
        )
        self._hint_btn.pack(anchor="w")

    def set_hotkey(self, hotkey: str) -> None:
        hotkey_text = format_hotkey_display(hotkey)
        self._hint_btn.configure(text=f"Hold [{hotkey_text}] to speak")


class OnboardingCard(ctk.CTkFrame):
    """Welcome card for first-time users with setup steps."""

    def __init__(
        self,
        parent,
        on_get_api_key: Optional[Callable[[], None]] = None,
        on_settings: Optional[Callable[[], None]] = None,
        on_skip: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color=BG_CARD, corner_radius=16, **kwargs)

        self._on_get_api_key = on_get_api_key
        self._on_settings = on_settings
        self._on_skip = on_skip

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=25)

        # Header with icon
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(
            header,
            text="🎙️",
            font=ctk.CTkFont(size=32),
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="Welcome to Ditado!",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT_DARK,
        ).pack(side="left", padx=(12, 0))

        # Subtitle
        ctk.CTkLabel(
            content,
            text="Get started with voice dictation in 3 easy steps:",
            font=ctk.CTkFont(size=14),
            text_color=TEXT_GRAY,
        ).pack(anchor="w", pady=(0, 20))

        # Steps
        steps = [
            ("1", "Add your OpenAI API key", "Get API Key", self._open_api_page),
            ("2", "Configure your hotkey", "Settings", self._go_to_settings),
            ("3", "Hold your hotkey and speak!", None, None),
        ]

        for num, text, btn_text, btn_cmd in steps:
            step_frame = ctk.CTkFrame(content, fg_color="transparent")
            step_frame.pack(fill="x", pady=8)

            # Step number circle
            ctk.CTkLabel(
                step_frame,
                text=num,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=TEXT_LIGHT,
                fg_color=ACCENT_LIME_DARK,
                corner_radius=12,
                width=24,
                height=24,
            ).pack(side="left")

            # Step text
            ctk.CTkLabel(
                step_frame,
                text=text,
                font=ctk.CTkFont(size=14),
                text_color=TEXT_DARK,
            ).pack(side="left", padx=(12, 0))

            # Action button (if any)
            if btn_text and btn_cmd:
                ctk.CTkButton(
                    step_frame,
                    text=f"{btn_text} →",
                    command=btn_cmd,
                    fg_color=ACCENT_LIME,
                    hover_color=ACCENT_LIME_DARK,
                    text_color=TEXT_DARK,
                    width=120,
                    height=32,
                    corner_radius=16,
                    font=ctk.CTkFont(size=12),
                ).pack(side="right")

        # Skip button
        ctk.CTkButton(
            content,
            text="Skip Setup",
            command=self._skip_setup,
            fg_color="transparent",
            hover_color=BG_CARD_HOVER,
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=12),
            width=100,
        ).pack(anchor="w", pady=(20, 0))

    def _open_api_page(self) -> None:
        webbrowser.open("https://platform.openai.com/api-keys")
        if self._on_get_api_key:
            self._on_get_api_key()

    def _go_to_settings(self) -> None:
        if self._on_settings:
            self._on_settings()

    def _skip_setup(self) -> None:
        if self._on_skip:
            self._on_skip()


class HistoryItem(ctk.CTkFrame):
    """Single transcription history item - light theme with copy button."""

    def __init__(self, parent, entry: TranscriptionHistoryEntry, **kwargs):
        super().__init__(parent, fg_color=BG_CARD, corner_radius=12, **kwargs)

        self._full_text = entry.text
        self._parent_widget = parent

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=14)

        # Left: lime indicator dot
        ctk.CTkLabel(
            content,
            text="●",
            font=ctk.CTkFont(size=10),
            text_color=ACCENT_LIME_DARK,
            width=20,
        ).pack(side="left")

        # Timestamp
        ctk.CTkLabel(
            content,
            text=format_relative_time(entry.timestamp),
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
            width=80,
            anchor="w",
        ).pack(side="left")

        # Text preview
        text_preview = entry.text[:70] + "..." if len(entry.text) > 70 else entry.text
        text_preview = text_preview.replace("\n", " ")

        ctk.CTkLabel(
            content,
            text=text_preview,
            font=ctk.CTkFont(size=13),
            text_color=TEXT_DARK,
            anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=(12, 12))

        # Copy button (always visible for better UX)
        self._copy_btn = ctk.CTkButton(
            content,
            text="📋",
            width=32,
            height=28,
            corner_radius=8,
            fg_color="transparent",
            hover_color=ACCENT_LIME_LIGHT,
            text_color=TEXT_GRAY,
            font=ctk.CTkFont(size=14),
            command=self._copy_to_clipboard,
        )
        self._copy_btn.pack(side="right", padx=(8, 0))

        # Word count badge
        ctk.CTkLabel(
            content,
            text=f"{entry.word_count} words",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_GRAY,
            fg_color=BG_CARD_HOVER,
            corner_radius=10,
            padx=10,
            pady=4,
        ).pack(side="right")

        # Hover effects
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, event) -> None:
        self.configure(fg_color=BG_CARD_HOVER)
        self._copy_btn.configure(fg_color=ACCENT_LIME_LIGHT)

    def _on_leave(self, event) -> None:
        self.configure(fg_color=BG_CARD)
        self._copy_btn.configure(fg_color="transparent")

    def _copy_to_clipboard(self) -> None:
        """Copy full text to clipboard."""
        try:
            # Use tkinter's clipboard
            self.clipboard_clear()
            self.clipboard_append(self._full_text)
            self.update()  # Required for clipboard to work

            # Visual feedback - change button text briefly
            self._copy_btn.configure(text="✓", text_color=SUCCESS)
            self.after(1500, lambda: self._copy_btn.configure(text="📋", text_color=TEXT_GRAY))
        except Exception:
            pass  # Silently fail if clipboard not available


class PillTabButton(ctk.CTkButton):
    """Pill-shaped tab button."""

    def __init__(self, parent, text: str, command=None, is_active: bool = False, **kwargs):
        super().__init__(
            parent,
            text=text,
            command=command,
            fg_color=ACCENT_LIME if is_active else "transparent",
            hover_color=ACCENT_LIME_LIGHT if not is_active else ACCENT_LIME_DARK,
            text_color=TEXT_DARK,
            corner_radius=20,
            height=36,
            font=ctk.CTkFont(size=13),
            **kwargs
        )
        self._is_active = is_active

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self.configure(
            fg_color=ACCENT_LIME if active else "transparent",
            hover_color=ACCENT_LIME_LIGHT if not active else ACCENT_LIME_DARK,
        )


class HomeWindow:
    """Unified dashboard window with modern light theme design."""

    def __init__(
        self,
        settings: Settings,
        history: TranscriptionHistory,
        on_save: Optional[Callable[[Settings], None]] = None,
        on_minimize: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
    ):
        self._settings = settings
        self._history = history
        self._on_save = on_save
        self._on_minimize = on_minimize
        self._on_close = on_close
        self._window: Optional[ctk.CTkToplevel] = None

        # Tab management
        self._current_tab = "dashboard"
        self._tab_buttons: dict = {}
        self._tab_frames: dict = {}
        self._content_frame: Optional[ctk.CTkFrame] = None

        # Dashboard widgets
        self._words_card: Optional[ModernStatsCard] = None
        self._wpm_card: Optional[ModernStatsCard] = None
        self._info_card: Optional[InfoCard] = None
        self._history_list: Optional[ctk.CTkScrollableFrame] = None
        self._api_warning_frame: Optional[ctk.CTkFrame] = None
        self._onboarding_card: Optional[OnboardingCard] = None

        # Settings form variables (StringVars for dropdowns/switches)
        self._lang_var: Optional[ctk.StringVar] = None
        self._pos_var: Optional[ctk.StringVar] = None
        self._audio_device_var: Optional[ctk.StringVar] = None
        self._duration_var: Optional[ctk.StringVar] = None
        self._auto_stop_var: Optional[ctk.BooleanVar] = None
        self._mute_audio_var: Optional[ctk.BooleanVar] = None
        self._sound_feedback_var: Optional[ctk.BooleanVar] = None
        self._autostart_var: Optional[ctk.BooleanVar] = None
        self._enhance_var: Optional[ctk.BooleanVar] = None
        self._whisper_var: Optional[ctk.StringVar] = None
        self._gpt_var: Optional[ctk.StringVar] = None

        # Status labels
        self._mic_status: Optional[ctk.CTkLabel] = None
        self._api_status: Optional[ctk.CTkLabel] = None
        self._save_status: Optional[ctk.CTkLabel] = None
        self._save_btn: Optional[ctk.CTkButton] = None
        self._toast_frame: Optional[ctk.CTkFrame] = None

        # Other state
        self._audio_devices = []
        self._capturing_hotkey = False
        self._show_key = False
        self._hotkey_entry: Optional[ctk.CTkEntry] = None
        self._capture_btn: Optional[ctk.CTkButton] = None
        self._api_key_entry: Optional[ctk.CTkEntry] = None
        self._show_key_btn: Optional[ctk.CTkButton] = None

        # Duration mapping
        self._duration_values = {
            "1 min": 60, "2 min": 120, "5 min": 300,
            "10 min": 600, "15 min": 900, "No limit": 0,
        }

    def show(self, parent: Optional[ctk.CTk] = None) -> None:
        """Show the dashboard window."""
        if self._window is not None and self._window.winfo_exists():
            self._window.focus()
            self._window.deiconify()
            return

        # Set light appearance mode
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self._window = ctk.CTkToplevel(parent) if parent else ctk.CTkToplevel()
        self._window.title(f"Ditado v{__version__}")
        self._window.geometry("1000x720")
        self._window.minsize(900, 650)
        self._window.configure(fg_color=BG_MAIN)
        self._window.protocol("WM_DELETE_WINDOW", self._handle_close)

        # Main container with grid
        main = ctk.CTkFrame(self._window, fg_color="transparent")
        main.pack(fill="both", expand=True)
        main.grid_columnconfigure(0, weight=0, minsize=70)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self._build_icon_sidebar(main)
        self._build_main_content(main)
        self.refresh()

    def _build_icon_sidebar(self, parent: ctk.CTkFrame) -> None:
        """Build narrow icon-only sidebar."""
        sidebar = ctk.CTkFrame(
            parent,
            fg_color=BG_SIDEBAR,
            corner_radius=20,
            width=70
        )
        sidebar.grid(row=0, column=0, sticky="ns", padx=10, pady=10)
        sidebar.grid_propagate(False)

        # Logo icon at top
        logo_btn = ctk.CTkButton(
            sidebar,
            text="+",
            width=40,
            height=40,
            corner_radius=20,
            fg_color="#3A3A3A",
            hover_color="#4A4A4A",
            text_color=TEXT_LIGHT,
            font=ctk.CTkFont(size=20, weight="bold"),
            command=lambda: self._switch_tab("dashboard"),
        )
        logo_btn.pack(pady=(20, 30))

        # Navigation icons
        nav_icons = [
            ("dashboard", "home", self._get_home_icon),
            ("settings", "gear", self._get_settings_icon),
            ("api", "link", self._get_api_icon),
            ("analytics", "chart", self._get_analytics_icon),
        ]

        self._sidebar_btns = {}
        for tab_name, icon_name, icon_func in nav_icons:
            btn = ctk.CTkButton(
                sidebar,
                text=icon_func(),
                width=40,
                height=40,
                corner_radius=12,
                fg_color=ACCENT_LIME if tab_name == "dashboard" else "transparent",
                hover_color="#3A3A3A",
                text_color=TEXT_DARK if tab_name == "dashboard" else ICON_INACTIVE,
                font=ctk.CTkFont(size=18),
                command=lambda t=tab_name: self._switch_tab(t),
            )
            btn.pack(pady=5)
            self._sidebar_btns[tab_name] = btn

        # Spacer
        ctk.CTkFrame(sidebar, fg_color="transparent").pack(fill="both", expand=True)

        # Version label
        ctk.CTkLabel(
            sidebar,
            text=f"v{__version__}",
            font=ctk.CTkFont(size=10),
            text_color=ICON_INACTIVE,
        ).pack(pady=(0, 8))

        # Minimize button at bottom
        ctk.CTkButton(
            sidebar,
            text="−",
            width=40,
            height=40,
            corner_radius=12,
            fg_color="transparent",
            hover_color="#3A3A3A",
            text_color=ICON_INACTIVE,
            font=ctk.CTkFont(size=24),
            command=self._handle_minimize,
        ).pack(pady=(0, 20))

    def _get_home_icon(self) -> str:
        return "⌂"

    def _get_settings_icon(self) -> str:
        return "⚙"

    def _get_api_icon(self) -> str:
        return "⟡"

    def _get_analytics_icon(self) -> str:
        return "◐"

    def _build_main_content(self, parent: ctk.CTkFrame) -> None:
        """Build main content area."""
        self._content_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._content_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)

        # Build all tabs
        self._build_dashboard_tab()
        self._build_settings_tab()
        self._build_api_tab()
        self._build_analytics_tab()

        # Show dashboard by default
        self._show_tab("dashboard")

    def _switch_tab(self, tab_name: str) -> None:
        """Switch to a different tab."""
        self._current_tab = tab_name

        # Update sidebar button styles
        for name, btn in self._sidebar_btns.items():
            if name == tab_name:
                btn.configure(fg_color=ACCENT_LIME, text_color=TEXT_DARK)
            else:
                btn.configure(fg_color="transparent", text_color=ICON_INACTIVE)

        # Update pill tab button styles (sync with sidebar)
        for name, btn in self._tab_buttons.items():
            btn.set_active(name == tab_name)

        self._show_tab(tab_name)

    def _show_tab(self, tab_name: str) -> None:
        """Show a specific tab."""
        for name, frame in self._tab_frames.items():
            if name == tab_name:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    # ========================
    # DASHBOARD TAB
    # ========================
    def _build_dashboard_tab(self) -> None:
        """Build the dashboard tab content."""
        tab = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._tab_frames["dashboard"] = tab

        # Header
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))

        # Title section
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left")

        ctk.CTkLabel(
            title_frame,
            text="Managing Your",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=TEXT_DARK,
        ).pack(anchor="w")

        title_row = ctk.CTkFrame(title_frame, fg_color="transparent")
        title_row.pack(anchor="w")

        ctk.CTkLabel(
            title_row,
            text="Voice",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=TEXT_DARK,
        ).pack(side="left")

        # Lime accent badge
        ctk.CTkLabel(
            title_row,
            text="●",
            font=ctk.CTkFont(size=12),
            text_color=ACCENT_LIME,
        ).pack(side="left", padx=6)

        ctk.CTkLabel(
            title_row,
            text="Workflows",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=TEXT_DARK,
        ).pack(side="left")

        # Action buttons on right
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")

        ctk.CTkButton(
            actions,
            text="⚙",
            width=40,
            height=40,
            corner_radius=12,
            fg_color=BG_CARD,
            hover_color=BG_CARD_HOVER,
            text_color=TEXT_GRAY,
            font=ctk.CTkFont(size=18),
            command=lambda: self._switch_tab("settings"),
        ).pack(side="left", padx=(0, 8))

        # Pill tabs
        tabs_frame = ctk.CTkFrame(tab, fg_color="transparent")
        tabs_frame.pack(fill="x", pady=(0, 25))

        tab_names = ["Dashboard", "Settings", "API", "Analytics"]
        tab_keys = ["dashboard", "settings", "api", "analytics"]

        for name, key in zip(tab_names, tab_keys):
            btn = PillTabButton(
                tabs_frame,
                text=name,
                is_active=(key == "dashboard"),
                command=lambda k=key: self._switch_tab(k),
            )
            btn.pack(side="left", padx=(0, 8))
            self._tab_buttons[key] = btn

        # Check if this is a first-time user (no API key and no transcriptions)
        is_first_time_user = (
            not self._settings.is_configured() and
            self._settings.stats.total_requests == 0
        )

        # Onboarding card for first-time users
        self._onboarding_card: Optional[OnboardingCard] = None
        if is_first_time_user:
            self._onboarding_card = OnboardingCard(
                tab,
                on_get_api_key=lambda: self._switch_tab("api"),
                on_settings=lambda: self._switch_tab("settings"),
                on_skip=self._dismiss_onboarding,
            )
            self._onboarding_card.pack(fill="x", pady=(0, 25))
        else:
            # API warning (only show if not first-time user but still not configured)
            self._api_warning_frame = ctk.CTkFrame(tab, fg_color="#FFF8E1", corner_radius=12)
            if not self._settings.is_configured():
                self._api_warning_frame.pack(fill="x", pady=(0, 20))
                warn_content = ctk.CTkFrame(self._api_warning_frame, fg_color="transparent")
                warn_content.pack(fill="x", padx=16, pady=12)

                ctk.CTkLabel(
                    warn_content,
                    text="⚠",
                    font=ctk.CTkFont(size=16),
                    text_color=WARNING,
                ).pack(side="left")

                ctk.CTkLabel(
                    warn_content,
                    text="API key not configured. Go to the API tab to add your OpenAI API key.",
                    font=ctk.CTkFont(size=13),
                    text_color="#F57C00",
                ).pack(side="left", padx=(10, 0))

        # Stats cards row
        cards_frame = ctk.CTkFrame(tab, fg_color="transparent")
        cards_frame.pack(fill="x", pady=(0, 25))
        cards_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Words card
        words = self._settings.stats.total_words
        words_pct = min(100, int((words / 10000) * 100)) if words else 0
        self._words_card = ModernStatsCard(
            cards_frame,
            title="Words",
            value=self._format_number(words),
            subtitle="10K",
            percentage=words_pct,
            icon="📝",
        )
        self._words_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        # WPM card
        wpm = self._settings.get_estimated_wpm()
        wpm_pct = min(100, int((wpm / 150) * 100)) if wpm else 0
        self._wpm_card = ModernStatsCard(
            cards_frame,
            title="Est. WPM",
            value=str(wpm) if wpm > 0 else "—",
            subtitle="150",
            percentage=wpm_pct,
            icon="⚡",
            accent_color=ACCENT_LIME,
        )
        self._wpm_card.grid(row=0, column=1, padx=5, sticky="nsew")

        # Info card
        self._info_card = InfoCard(cards_frame)
        self._info_card.grid(row=0, column=2, padx=(10, 0), sticky="nsew")
        self._info_card.set_hotkey(self._settings.hotkey)

        # History section
        history_frame = ctk.CTkFrame(tab, fg_color="transparent")
        history_frame.pack(fill="both", expand=True)

        # History header
        hist_header = ctk.CTkFrame(history_frame, fg_color="transparent")
        hist_header.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(
            hist_header,
            text="Recent Transcriptions",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_DARK,
        ).pack(side="left")

        ctk.CTkButton(
            hist_header,
            text="Clear History",
            command=self._clear_history,
            fg_color="transparent",
            hover_color=BG_CARD_HOVER,
            text_color=TEXT_GRAY,
            font=ctk.CTkFont(size=12),
            width=100,
            height=32,
        ).pack(side="right")

        # History list
        self._history_list = ctk.CTkScrollableFrame(
            history_frame,
            fg_color="transparent",
        )
        self._history_list.pack(fill="both", expand=True)

    # ========================
    # SETTINGS TAB
    # ========================
    def _build_settings_tab(self) -> None:
        """Build the settings tab content."""
        tab = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._tab_frames["settings"] = tab

        # Header
        self._build_tab_header(tab, "Settings", "Configure your dictation preferences")

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # Recording Setup Section
        self._build_section_header(scroll, "Recording Setup")

        # Hotkey
        hotkey_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        hotkey_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            hotkey_frame, text="Push-to-Talk Hotkey",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_DARK,
        ).pack(anchor="w", padx=20, pady=(16, 8))

        hotkey_row = ctk.CTkFrame(hotkey_frame, fg_color="transparent")
        hotkey_row.pack(fill="x", padx=20, pady=(0, 16))

        self._hotkey_entry = ctk.CTkEntry(
            hotkey_row,
            width=200,
            fg_color=BG_CARD_HOVER,
            border_color=BG_CARD_HOVER,
            text_color=TEXT_DARK,
        )
        self._hotkey_entry.pack(side="left", padx=(0, 12))
        # Insert value explicitly (CTkEntry doesn't always show textvariable on readonly)
        self._hotkey_entry.insert(0, self._settings.hotkey)
        self._hotkey_entry.configure(state="readonly")

        self._capture_btn = ctk.CTkButton(
            hotkey_row,
            text="Capture Key",
            command=self._start_hotkey_capture,
            fg_color=ACCENT_LIME,
            hover_color=ACCENT_LIME_DARK,
            text_color=TEXT_DARK,
            width=110,
        )
        self._capture_btn.pack(side="left")

        # Microphone
        mic_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        mic_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            mic_frame, text="Microphone",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_DARK,
        ).pack(anchor="w", padx=20, pady=(16, 8))

        self._audio_devices = list_audio_devices()
        device_names = ["System Default"] + [d["name"] for d in self._audio_devices]

        current_device = "System Default"
        if self._settings.audio_device_index is not None:
            for d in self._audio_devices:
                if d["index"] == self._settings.audio_device_index:
                    current_device = d["name"]
                    break

        self._audio_device_var = ctk.StringVar(value=current_device)
        ctk.CTkOptionMenu(
            mic_frame,
            variable=self._audio_device_var,
            values=device_names,
            width=320,
            fg_color=BG_CARD_HOVER,
            button_color=ACCENT_LIME,
            button_hover_color=ACCENT_LIME_DARK,
            text_color=TEXT_DARK,
        ).pack(anchor="w", padx=20, pady=(0, 8))

        mic_btn_row = ctk.CTkFrame(mic_frame, fg_color="transparent")
        mic_btn_row.pack(anchor="w", padx=20, pady=(0, 16))

        ctk.CTkButton(
            mic_btn_row,
            text="Test Microphone",
            command=self._test_microphone,
            fg_color=ACCENT_LIME,
            hover_color=ACCENT_LIME_DARK,
            text_color=TEXT_DARK,
            width=130,
        ).pack(side="left")

        self._mic_status = ctk.CTkLabel(
            mic_btn_row, text="",
            font=ctk.CTkFont(size=12),
        )
        self._mic_status.pack(side="left", padx=(12, 0))

        # Language
        lang_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        lang_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            lang_frame, text="Dictation Language",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_DARK,
        ).pack(anchor="w", padx=20, pady=(16, 8))

        lang_options = [f"{code}: {name}" for code, name in SUPPORTED_LANGUAGES.items()]
        current_lang = f"{self._settings.language}: {SUPPORTED_LANGUAGES.get(self._settings.language, 'Unknown')}"

        self._lang_var = ctk.StringVar(value=current_lang)
        ctk.CTkOptionMenu(
            lang_frame,
            variable=self._lang_var,
            values=lang_options,
            width=300,
            fg_color=BG_CARD_HOVER,
            button_color=ACCENT_LIME,
            button_hover_color=ACCENT_LIME_DARK,
            text_color=TEXT_DARK,
        ).pack(anchor="w", padx=20, pady=(0, 16))

        # Preferences Section
        self._build_section_header(scroll, "Preferences")

        # AI Enhancement
        enhance_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        enhance_frame.pack(fill="x", pady=(0, 10))

        self._enhance_var = ctk.BooleanVar(value=self._settings.enhance_text)
        ctk.CTkSwitch(
            enhance_frame,
            text="AI Text Enhancement (GPT cleanup)",
            variable=self._enhance_var,
            font=ctk.CTkFont(size=14),
            text_color=TEXT_DARK,
            progress_color=ACCENT_LIME,
            button_color=ACCENT_LIME_DARK,
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            enhance_frame, text="Removes filler words and fixes grammar",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 16))

        # Indicator Position
        pos_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        pos_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            pos_frame, text="Recording Indicator Position",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_DARK,
        ).pack(anchor="w", padx=20, pady=(16, 8))

        positions = ["top-left", "top-right", "bottom-left", "bottom-right", "bottom-center"]
        self._pos_var = ctk.StringVar(value=self._settings.indicator_position)
        ctk.CTkOptionMenu(
            pos_frame,
            variable=self._pos_var,
            values=positions,
            width=200,
            fg_color=BG_CARD_HOVER,
            button_color=ACCENT_LIME,
            button_hover_color=ACCENT_LIME_DARK,
            text_color=TEXT_DARK,
        ).pack(anchor="w", padx=20, pady=(0, 16))

        # Recording Limits
        limits_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        limits_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            limits_frame, text="Recording Limits",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_DARK,
        ).pack(anchor="w", padx=20, pady=(16, 8))

        dur_row = ctk.CTkFrame(limits_frame, fg_color="transparent")
        dur_row.pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkLabel(
            dur_row, text="Max duration:",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_GRAY,
        ).pack(side="left")

        current_duration = "5 min"
        for name, secs in self._duration_values.items():
            if secs == self._settings.max_recording_seconds:
                current_duration = name
                break

        self._duration_var = ctk.StringVar(value=current_duration)
        ctk.CTkOptionMenu(
            dur_row,
            variable=self._duration_var,
            values=list(self._duration_values.keys()),
            width=130,
            fg_color=BG_CARD_HOVER,
            button_color=ACCENT_LIME,
            button_hover_color=ACCENT_LIME_DARK,
            text_color=TEXT_DARK,
        ).pack(side="left", padx=(12, 0))

        self._auto_stop_var = ctk.BooleanVar(value=self._settings.auto_stop_recording)
        ctk.CTkSwitch(
            limits_frame,
            text="Auto-stop when limit reached",
            variable=self._auto_stop_var,
            font=ctk.CTkFont(size=13),
            text_color=TEXT_DARK,
            progress_color=ACCENT_LIME,
            button_color=ACCENT_LIME_DARK,
        ).pack(anchor="w", padx=20, pady=(4, 16))

        # System Audio Section
        self._build_section_header(scroll, "System Audio")

        mute_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        mute_frame.pack(fill="x", pady=(0, 10))

        self._mute_audio_var = ctk.BooleanVar(value=self._settings.mute_system_audio)
        ctk.CTkSwitch(
            mute_frame,
            text="Mute system audio while recording",
            variable=self._mute_audio_var,
            font=ctk.CTkFont(size=14),
            text_color=TEXT_DARK,
            progress_color=ACCENT_LIME,
            button_color=ACCENT_LIME_DARK,
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            mute_frame,
            text="Automatically mutes speakers during dictation to improve accuracy",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 16))

        # Sound Feedback
        sound_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        sound_frame.pack(fill="x", pady=(0, 10))

        self._sound_feedback_var = ctk.BooleanVar(value=self._settings.sound_feedback)
        ctk.CTkSwitch(
            sound_frame,
            text="Sound feedback",
            variable=self._sound_feedback_var,
            font=ctk.CTkFont(size=14),
            text_color=TEXT_DARK,
            progress_color=ACCENT_LIME,
            button_color=ACCENT_LIME_DARK,
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            sound_frame,
            text="Play beeps when push-to-talk starts and ends",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 16))

        # Startup Section
        self._build_section_header(scroll, "Startup")

        autostart_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        autostart_frame.pack(fill="x", pady=(0, 10))

        self._autostart_var = ctk.BooleanVar(value=self._settings.auto_start_on_boot)
        ctk.CTkSwitch(
            autostart_frame,
            text="Start Ditado when Windows boots",
            variable=self._autostart_var,
            font=ctk.CTkFont(size=14),
            text_color=TEXT_DARK,
            progress_color=ACCENT_LIME,
            button_color=ACCENT_LIME_DARK,
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            autostart_frame,
            text="Ditado will start automatically when you log in",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 16))

        # Save button
        self._add_save_button(scroll)

    # ========================
    # API TAB
    # ========================
    def _build_api_tab(self) -> None:
        """Build the API configuration tab."""
        tab = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._tab_frames["api"] = tab

        # Header
        self._build_tab_header(tab, "API Configuration", "Connect to OpenAI for transcription")

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        self._build_section_header(scroll, "OpenAI API")

        # API Key
        key_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        key_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            key_frame, text="API Key",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_DARK,
        ).pack(anchor="w", padx=20, pady=(16, 8))

        self._api_key_entry = ctk.CTkEntry(
            key_frame,
            width=420,
            show="*",
            placeholder_text="sk-...",
            fg_color=BG_CARD_HOVER,
            border_color=BG_CARD_HOVER,
            text_color=TEXT_DARK,
        )
        self._api_key_entry.pack(anchor="w", padx=20, pady=(0, 8))
        # Insert value explicitly if exists
        if self._settings.api_key:
            self._api_key_entry.insert(0, self._settings.api_key)

        btn_row = ctk.CTkFrame(key_frame, fg_color="transparent")
        btn_row.pack(anchor="w", padx=20, pady=(0, 8))

        self._show_key_btn = ctk.CTkButton(
            btn_row,
            text="Show Key",
            command=self._toggle_key_visibility,
            fg_color=BG_CARD_HOVER,
            hover_color="#E8E8E3",
            text_color=TEXT_GRAY,
            width=90,
            height=32,
        )
        self._show_key_btn.pack(side="left")

        ctk.CTkButton(
            btn_row,
            text="Test Connection",
            command=self._test_api,
            fg_color=ACCENT_LIME,
            hover_color=ACCENT_LIME_DARK,
            text_color=TEXT_DARK,
            width=130,
        ).pack(side="left", padx=(10, 0))

        self._api_status = ctk.CTkLabel(
            key_frame, text="",
            font=ctk.CTkFont(size=12),
        )
        self._api_status.pack(anchor="w", padx=20, pady=(4, 8))

        # API key helper link
        link_frame = ctk.CTkFrame(key_frame, fg_color="transparent")
        link_frame.pack(anchor="w", padx=20, pady=(0, 16))

        ctk.CTkLabel(
            link_frame,
            text="Don't have an API key?",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        ).pack(side="left")

        api_link = ctk.CTkButton(
            link_frame,
            text="Get one from OpenAI →",
            command=lambda: webbrowser.open("https://platform.openai.com/api-keys"),
            fg_color="transparent",
            hover_color=BG_CARD_HOVER,
            text_color=ACCENT_LIME_DARK,
            font=ctk.CTkFont(size=12, underline=True),
            width=150,
            height=20,
            cursor="hand2",
        )
        api_link.pack(side="left", padx=(4, 0))

        # Cost warning info box
        cost_info = ctk.CTkFrame(scroll, fg_color="#E3F2FD", corner_radius=12)
        cost_info.pack(fill="x", pady=(0, 10))

        cost_content = ctk.CTkFrame(cost_info, fg_color="transparent")
        cost_content.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(
            cost_content,
            text="ℹ",
            font=ctk.CTkFont(size=16),
            text_color="#1976D2",
        ).pack(side="left")

        ctk.CTkLabel(
            cost_content,
            text="API costs: Whisper ~$0.006/min, GPT ~$0.0003/request. At 30 min/day, expect ~$5-6/month.",
            font=ctk.CTkFont(size=12),
            text_color="#1565C0",
            wraplength=500,
        ).pack(side="left", padx=(10, 0))

        # Models Section
        self._build_section_header(scroll, "Models")

        models_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        models_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            models_frame, text="Transcription Model (Whisper)",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_GRAY,
        ).pack(anchor="w", padx=20, pady=(16, 8))

        self._whisper_var = ctk.StringVar(value=self._settings.whisper_model)
        ctk.CTkOptionMenu(
            models_frame,
            variable=self._whisper_var,
            values=["whisper-1"],
            width=200,
            fg_color=BG_CARD_HOVER,
            button_color=ACCENT_LIME,
            button_hover_color=ACCENT_LIME_DARK,
            text_color=TEXT_DARK,
        ).pack(anchor="w", padx=20, pady=(0, 12))

        ctk.CTkLabel(
            models_frame, text="Enhancement Model (GPT)",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_GRAY,
        ).pack(anchor="w", padx=20, pady=(8, 8))

        self._gpt_var = ctk.StringVar(value=self._settings.gpt_model)
        ctk.CTkOptionMenu(
            models_frame,
            variable=self._gpt_var,
            values=["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
            width=200,
            fg_color=BG_CARD_HOVER,
            button_color=ACCENT_LIME,
            button_hover_color=ACCENT_LIME_DARK,
            text_color=TEXT_DARK,
        ).pack(anchor="w", padx=20, pady=(0, 16))

        # Save button
        self._add_save_button(scroll)

    # ========================
    # ANALYTICS TAB
    # ========================
    def _build_analytics_tab(self) -> None:
        """Build the analytics/usage tab."""
        tab = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._tab_frames["analytics"] = tab

        # Header
        self._build_tab_header(tab, "Analytics", "Track your usage and costs")

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        stats = self._settings.stats
        costs = self._settings.get_estimated_cost()

        # Session stats
        self._build_section_header(scroll, "This Session")

        session_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        session_frame.pack(fill="x", pady=(0, 20))

        self._add_stat_row(session_frame, "Transcriptions", str(stats.session_requests))
        self._add_stat_row(session_frame, "Minutes", f"{stats.session_minutes:.2f}")

        # All-time stats
        self._build_section_header(scroll, "All Time")

        total_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        total_frame.pack(fill="x", pady=(0, 20))

        self._add_stat_row(total_frame, "Transcriptions", str(stats.total_requests))
        self._add_stat_row(total_frame, "Minutes", f"{stats.total_minutes:.2f}")
        self._add_stat_row(total_frame, "Words", str(stats.total_words))
        self._add_stat_row(total_frame, "Weeks Active", str(self._settings.get_weeks_active()))

        # Cost estimates
        self._build_section_header(scroll, "Estimated Costs")

        cost_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        cost_frame.pack(fill="x", pady=(0, 20))

        self._add_stat_row(cost_frame, "Whisper", f"${costs['whisper']:.4f}")
        self._add_stat_row(cost_frame, "GPT Enhancement", f"${costs['gpt']:.4f}")
        self._add_stat_row(cost_frame, "Total", f"${costs['total']:.4f}", bold=True, color=SUCCESS)

        # Pricing info
        ctk.CTkLabel(
            scroll,
            text="Whisper: $0.006/min | GPT-4o-mini: ~$0.0003/request",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 10))

        # About section
        self._build_section_header(scroll, "About")

        about_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        about_frame.pack(fill="x", pady=(0, 20))

        self._add_stat_row(about_frame, "Version", f"v{__version__}")

        # Help link row
        help_row = ctk.CTkFrame(about_frame, fg_color="transparent")
        help_row.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            help_row, text="Need help?",
            font=ctk.CTkFont(size=14),
            text_color=TEXT_GRAY,
        ).pack(side="left")

        ctk.CTkButton(
            help_row,
            text="View Documentation →",
            command=lambda: webbrowser.open("https://github.com/LuzGuilherme/Ditado#readme"),
            fg_color="transparent",
            hover_color=BG_CARD_HOVER,
            text_color=ACCENT_LIME_DARK,
            font=ctk.CTkFont(size=13),
            width=160,
            height=28,
            anchor="e",
        ).pack(side="right")

    # ========================
    # HELPER METHODS
    # ========================
    def _build_tab_header(self, parent, title: str, subtitle: str) -> None:
        """Build a tab header with title and subtitle."""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(
            header, text=title,
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=TEXT_DARK,
        ).pack(anchor="w")

        ctk.CTkLabel(
            header, text=subtitle,
            font=ctk.CTkFont(size=14),
            text_color=TEXT_GRAY,
        ).pack(anchor="w", pady=(4, 0))

    def _build_section_header(self, parent, text: str) -> None:
        """Add a section header."""
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_DARK,
        ).pack(anchor="w", pady=(20, 12))

    def _add_stat_row(self, parent, label: str, value: str, bold: bool = False, color: str = None) -> None:
        """Add a stat row to a frame."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            row, text=label,
            font=ctk.CTkFont(size=14),
            text_color=TEXT_GRAY,
        ).pack(side="left")

        ctk.CTkLabel(
            row, text=value,
            font=ctk.CTkFont(size=14, weight="bold" if bold else "normal"),
            text_color=color or TEXT_DARK,
        ).pack(side="right")

    def _add_save_button(self, parent) -> None:
        """Add save button to a tab."""
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(25, 15))

        self._save_btn = ctk.CTkButton(
            btn_frame,
            text="Save Settings",
            command=self._save_settings,
            fg_color=ACCENT_LIME,
            hover_color=ACCENT_LIME_DARK,
            text_color=TEXT_DARK,
            height=44,
            width=150,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=12,
        )
        self._save_btn.pack(side="left")

        self._save_status = ctk.CTkLabel(
            btn_frame, text="",
            font=ctk.CTkFont(size=12),
        )
        self._save_status.pack(side="left", padx=(15, 0))

    def _format_number(self, num: int) -> str:
        if num >= 1000:
            return f"{num / 1000:.1f}K"
        return str(num)

    # ========================
    # ACTIONS
    # ========================
    def _start_hotkey_capture(self) -> None:
        """Start capturing a new hotkey (single key or combination)."""
        if self._capturing_hotkey:
            return

        self._capturing_hotkey = True
        self._capture_btn.configure(text="Hold keys...")
        self._hotkey_entry.configure(state="normal")
        self._hotkey_entry.delete(0, "end")
        self._hotkey_entry.insert(0, "Hold 1-2 keys...")

        def on_key_captured(hotkey_str: str):
            if self._window and self._window.winfo_exists():
                self._window.after(0, lambda: self._finish_hotkey_capture(hotkey_str))

        # Use combination capture dialog (supports single keys and combos)
        capture = KeyCombinationCaptureDialog(on_key_captured, max_keys=2)
        capture.start_capture()

    def _finish_hotkey_capture(self, hotkey_str: str) -> None:
        """Finish hotkey capture and display result."""
        self._hotkey_entry.configure(state="normal")
        self._hotkey_entry.delete(0, "end")
        self._hotkey_entry.insert(0, hotkey_str)
        self._hotkey_entry.configure(state="readonly")
        self._capture_btn.configure(text="Capture Key")
        self._capturing_hotkey = False

    def _toggle_key_visibility(self) -> None:
        """Toggle API key visibility."""
        self._show_key = not self._show_key
        self._api_key_entry.configure(show="" if self._show_key else "*")
        self._show_key_btn.configure(text="Hide Key" if self._show_key else "Show Key")

    def _test_microphone(self) -> None:
        """Test the selected microphone."""
        selected_name = self._audio_device_var.get()
        device_index = None
        if selected_name != "System Default":
            for d in self._audio_devices:
                if d["name"] == selected_name:
                    device_index = d["index"]
                    break

        def test():
            try:
                import sounddevice as sd
                import numpy as np

                self._mic_status.configure(text="Recording...", text_color=TEXT_GRAY)

                duration = 1.0
                sample_rate = 16000
                audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype=np.int16, device=device_index)
                sd.wait()

                avg_level = np.abs(audio).mean() / 32768.0

                if avg_level > 0.01:
                    self._mic_status.configure(text="Microphone working great!", text_color=SUCCESS)
                elif avg_level > 0.001:
                    self._mic_status.configure(text="Mic detected but volume is low. Speak louder or move closer.", text_color=WARNING)
                else:
                    self._mic_status.configure(text="No sound detected. Check mic connection.", text_color=ERROR)
            except Exception as e:
                error_msg = str(e)
                if "PortAudio" in error_msg or "device" in error_msg.lower():
                    self._mic_status.configure(text="Mic not found. Check it's connected.", text_color=ERROR)
                else:
                    self._mic_status.configure(text=f"Error: {error_msg[:40]}", text_color=ERROR)

        self._mic_status.configure(text="Testing...", text_color=TEXT_GRAY)
        threading.Thread(target=test, daemon=True).start()

    def _test_api(self) -> None:
        """Test the API connection."""
        api_key = self._api_key_entry.get().strip()

        def test():
            try:
                from openai import OpenAI
                if not api_key:
                    self._api_status.configure(text="API key is empty", text_color=ERROR)
                    return
                if not api_key.startswith("sk-"):
                    self._api_status.configure(text="Key should start with 'sk-'", text_color=ERROR)
                    return

                client = OpenAI(api_key=api_key)
                client.models.list()
                self._api_status.configure(text="Connection successful!", text_color=SUCCESS)
            except Exception as e:
                self._api_status.configure(text=f"Error: {str(e)[:40]}", text_color=ERROR)

        self._api_status.configure(text="Testing...", text_color=TEXT_GRAY)
        threading.Thread(target=test, daemon=True).start()

    def _save_settings(self) -> None:
        """Save all settings."""
        # Update settings object
        self._settings.hotkey = self._hotkey_entry.get().strip()
        self._settings.language = self._lang_var.get().split(":")[0]
        self._settings.indicator_position = self._pos_var.get()
        self._settings.enhance_text = self._enhance_var.get()
        self._settings.api_key = self._api_key_entry.get().strip()
        self._settings.whisper_model = self._whisper_var.get()
        self._settings.gpt_model = self._gpt_var.get()
        self._settings.max_recording_seconds = self._duration_values.get(self._duration_var.get(), 300)
        self._settings.auto_stop_recording = self._auto_stop_var.get()
        self._settings.mute_system_audio = self._mute_audio_var.get()
        self._settings.sound_feedback = self._sound_feedback_var.get()
        self._settings.auto_start_on_boot = self._autostart_var.get()

        # Audio device
        selected_name = self._audio_device_var.get()
        if selected_name == "System Default":
            self._settings.audio_device_index = None
        else:
            for d in self._audio_devices:
                if d["name"] == selected_name:
                    self._settings.audio_device_index = d["index"]
                    break

        # Save to file
        self._settings.save()

        # Apply autostart setting to Windows registry
        from ..utils.autostart import set_autostart
        set_autostart(self._settings.auto_start_on_boot)

        # Update UI
        self._update_info_card()
        self._update_api_warning()

        # Callback
        if self._on_save:
            self._on_save(self._settings)

        # Show prominent save confirmation
        self._show_save_toast()

    def _show_save_toast(self) -> None:
        """Show a prominent toast notification for save confirmation."""
        if not self._window or not self._window.winfo_exists():
            return

        # Remove existing toast if any
        if self._toast_frame and self._toast_frame.winfo_exists():
            self._toast_frame.destroy()

        # Create a separate Toplevel window for the toast (floats above main window)
        self._toast_frame = ctk.CTkToplevel(self._window)
        self._toast_frame.overrideredirect(True)  # No window decorations
        self._toast_frame.attributes("-topmost", True)  # Always on top

        # Use white background matching app cards
        self._toast_frame.configure(fg_color=BG_CARD)

        # Calculate position (center of main window, near top)
        self._window.update_idletasks()  # Ensure geometry is current
        window_x = self._window.winfo_x()
        window_y = self._window.winfo_y()
        window_width = self._window.winfo_width()
        toast_width = 280
        toast_height = 48
        x = window_x + (window_width - toast_width) // 2
        y = window_y + 60  # 60px from top of window

        self._toast_frame.geometry(f"{toast_width}x{toast_height}+{x}+{y}")

        # Main card with rounded corners and subtle lime border
        card = ctk.CTkFrame(
            self._toast_frame,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=ACCENT_LIME_LIGHT,
        )
        card.pack(fill="both", expand=True)

        # Left accent stripe (green success color)
        accent = ctk.CTkFrame(card, fg_color=SUCCESS, width=4, corner_radius=0)
        accent.pack(side="left", fill="y")

        # Content container
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=12, pady=10)

        # Green checkmark icon
        ctk.CTkLabel(
            content,
            text="✓",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=SUCCESS,
        ).pack(side="left", padx=(0, 10))

        # Dark text message
        ctk.CTkLabel(
            content,
            text="Settings saved successfully!",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_DARK,
        ).pack(side="left")

        # Also update button temporarily
        if self._save_btn and self._save_btn.winfo_exists():
            original_text = self._save_btn.cget("text")
            self._save_btn.configure(
                text="✓ Saved!",
                fg_color=SUCCESS,
            )

            # Restore button after delay
            def restore_button():
                if self._save_btn and self._save_btn.winfo_exists():
                    self._save_btn.configure(
                        text=original_text,
                        fg_color=ACCENT_LIME,
                    )

            self._window.after(2000, restore_button)

        # Auto-hide toast after 2.5 seconds
        def hide_toast():
            if self._toast_frame and self._toast_frame.winfo_exists():
                self._toast_frame.destroy()
                self._toast_frame = None

        self._window.after(2500, hide_toast)

    def _clear_history(self) -> None:
        """Clear all history entries."""
        self._history.clear()
        self.refresh_history()

    def _dismiss_onboarding(self) -> None:
        """Dismiss the onboarding card."""
        if self._onboarding_card:
            self._onboarding_card.pack_forget()
            self._onboarding_card = None

    def _handle_close(self) -> None:
        if self._on_close:
            self._on_close()
        self.hide()

    def _handle_minimize(self) -> None:
        if self._on_minimize:
            self._on_minimize()
        self.hide()

    def hide(self) -> None:
        if self._window:
            self._window.withdraw()

    def close(self) -> None:
        if self._window:
            self._window.destroy()
            self._window = None

    def refresh(self) -> None:
        """Refresh all dashboard content."""
        self.refresh_stats()
        self.refresh_history()
        self._update_info_card()

    def refresh_stats(self) -> None:
        """Update statistics display."""
        if not self._window or not self._window.winfo_exists():
            return

        if self._words_card:
            words = self._settings.stats.total_words
            self._words_card.set_value(self._format_number(words))
            self._words_card.set_percentage(min(100, int((words / 10000) * 100)) if words else 0)

        if self._wpm_card:
            wpm = self._settings.get_estimated_wpm()
            self._wpm_card.set_value(str(wpm) if wpm > 0 else "—")
            self._wpm_card.set_percentage(min(100, int((wpm / 150) * 100)) if wpm else 0)

    def refresh_history(self) -> None:
        """Update history list."""
        if not self._window or not self._window.winfo_exists() or not self._history_list:
            return

        for widget in self._history_list.winfo_children():
            widget.destroy()

        entries = self._history.get_recent(20)

        if not entries:
            empty_frame = ctk.CTkFrame(self._history_list, fg_color="transparent")
            empty_frame.pack(fill="both", expand=True, pady=40)

            ctk.CTkLabel(
                empty_frame,
                text="No transcriptions yet",
                font=ctk.CTkFont(size=16),
                text_color=TEXT_MUTED,
            ).pack()

            ctk.CTkLabel(
                empty_frame,
                text=f"Hold your hotkey ({self._settings.hotkey}) to start dictating",
                font=ctk.CTkFont(size=13),
                text_color=TEXT_MUTED,
            ).pack(pady=(8, 0))
            return

        for entry in entries:
            HistoryItem(self._history_list, entry).pack(fill="x", pady=4)

    def _update_info_card(self) -> None:
        """Update the info card hotkey hint."""
        if self._info_card:
            self._info_card.set_hotkey(self._settings.hotkey)

    def _update_api_warning(self) -> None:
        """Update API warning visibility."""
        if self._api_warning_frame:
            if self._settings.is_configured():
                self._api_warning_frame.pack_forget()
            else:
                # Re-pack it if not configured
                pass  # It's already packed on initial build
