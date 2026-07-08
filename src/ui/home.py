"""Unified Dashboard for Ditado - "Soft Warmth" identity."""

import os
import sys
import customtkinter as ctk
import threading
import webbrowser
from datetime import datetime, timedelta
from typing import Callable, Optional, List
from PIL import Image
from .. import __version__
from ..config.settings import Settings
from ..config.history import TranscriptionHistory, format_relative_time
from ..transcription.whisper import SUPPORTED_LANGUAGES
from ..input.hotkey import KeyCombinationCaptureDialog, format_hotkey_display
from ..audio.recorder import list_audio_devices
from .editorial import (
    SessionCard,
    HistoryWaveCard,
    StreakCard,
    SERIF_FAMILY,
    SANS_FAMILY,
)


def get_asset_path(filename: str) -> str:
    """Get the path to an asset file, works for both dev and bundled exe."""
    if getattr(sys, 'frozen', False):
        # Running as bundled exe
        base_path = sys._MEIPASS
    else:
        # Running in development
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_path, "assets", filename)


# ============================================
# COLOR PALETTE - "Soft Warmth" identity
# ============================================
# Source of truth lives in src/ui/theme.py - importing here keeps the
# dashboard, overlay, and any future surfaces visually coherent.
from .theme import (
    BG_MAIN,
    BG_CARD,
    BG_CARD_HOVER,
    BG_SIDEBAR,
    ACCENT_PRIMARY,
    ACCENT_PRIMARY_DARK,
    ACCENT_PRIMARY_LIGHT,
    TEXT_DARK,
    TEXT_GRAY,
    TEXT_LIGHT,
    TEXT_MUTED,
    SUCCESS,
    SUCCESS_TEXT,
    ERROR,
    ERROR_TEXT,
    WARNING,
    WARNING_TEXT,
    WARNING_BG,
    ICON_INACTIVE,
    ICON_ACTIVE,
    SIDEBAR_TEXT_MUTED,
)


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
                fg_color=ACCENT_PRIMARY_DARK,
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
                    fg_color=ACCENT_PRIMARY_DARK,
                    hover_color=ACCENT_PRIMARY,
                    text_color=TEXT_LIGHT,
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
        self._history_text_var: Optional[ctk.BooleanVar] = None

        # Status labels / async-action widgets
        self._mic_status: Optional[ctk.CTkLabel] = None
        self._api_status: Optional[ctk.CTkLabel] = None
        self._mic_test_btn: Optional[ctk.CTkButton] = None
        self._api_test_btn: Optional[ctk.CTkButton] = None
        self._save_btns: List[ctk.CTkButton] = []
        self._toast_frame: Optional[ctk.CTkToplevel] = None

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

        # Set window icon
        try:
            icon_path = get_asset_path("icon.ico")
            self._window.after(300, lambda: self._window.iconbitmap(icon_path))
        except Exception:
            pass

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
        try:
            logo_path = get_asset_path("logo.png")
            logo_image = Image.open(logo_path)
            ctk_logo = ctk.CTkImage(light_image=logo_image, dark_image=logo_image, size=(36, 36))
            logo_btn = ctk.CTkButton(
                sidebar,
                text="",
                image=ctk_logo,
                width=40,
                height=40,
                corner_radius=20,
                fg_color="transparent",
                hover_color="#3A3A3A",
                command=lambda: self._switch_tab("dashboard"),
            )
        except Exception:
            # Fallback to text if logo not found
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
                fg_color=ACCENT_PRIMARY if tab_name == "dashboard" else "transparent",
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
            text_color=SIDEBAR_TEXT_MUTED,
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
                btn.configure(fg_color=ACCENT_PRIMARY, text_color=TEXT_DARK)
            else:
                btn.configure(fg_color="transparent", text_color=ICON_INACTIVE)

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
        """Build the dashboard tab content - "Soft Warmth" editorial layout."""
        tab = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._tab_frames["dashboard"] = tab

        # =====================================================
        # TOP BAR: date (small caps) on left, streak card on right
        # =====================================================
        top_bar = ctk.CTkFrame(tab, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 6))

        # Date small caps (left)
        date_label = ctk.CTkLabel(
            top_bar,
            text=self._get_date_label(),
            font=ctk.CTkFont(family=SANS_FAMILY, size=11, weight="bold"),
            text_color=TEXT_GRAY,
        )
        date_label.pack(side="left")

        # Streak counter (right) - only if user has dictated at least once
        streak_days = self._get_streak_days()
        if streak_days > 0:
            StreakCard(top_bar, days=streak_days).pack(side="right")

        # =====================================================
        # HERO GREETING: serif "Good {time of day}, {Name}."
        # =====================================================
        greeting_text = self._get_greeting_text()
        hero = ctk.CTkLabel(
            tab,
            text=greeting_text,
            font=ctk.CTkFont(family=SERIF_FAMILY, size=42),
            text_color=TEXT_DARK,
            anchor="w",
            justify="left",
        )
        hero.pack(fill="x", pady=(8, 24), anchor="w")

        # =====================================================
        # ONBOARDING (if first-time) OR API WARNING (if mid-setup)
        # =====================================================
        is_first_time_user = (
            not self._settings.is_configured() and
            self._settings.stats.total_requests == 0
        )

        self._onboarding_card: Optional[OnboardingCard] = None
        if is_first_time_user:
            self._onboarding_card = OnboardingCard(
                tab,
                on_get_api_key=lambda: self._switch_tab("api"),
                on_settings=lambda: self._switch_tab("settings"),
                on_skip=self._dismiss_onboarding,
            )
            self._onboarding_card.pack(fill="x", pady=(0, 20))
        else:
            self._api_warning_frame = ctk.CTkFrame(
                tab,
                fg_color=WARNING_BG,
                corner_radius=12,
                border_width=1,
                border_color=WARNING_TEXT,
            )
            if not self._settings.is_configured():
                self._api_warning_frame.pack(fill="x", pady=(0, 16))
                warn_content = ctk.CTkFrame(self._api_warning_frame, fg_color="transparent")
                warn_content.pack(fill="x", padx=16, pady=12)

                ctk.CTkLabel(
                    warn_content,
                    text="⚠",
                    font=ctk.CTkFont(size=15),
                    text_color=WARNING_TEXT,
                ).pack(side="left")

                ctk.CTkLabel(
                    warn_content,
                    text="API key not configured. Add your OpenAI key in the API tab to start dictating.",
                    font=ctk.CTkFont(family=SANS_FAMILY, size=12),
                    text_color=TEXT_DARK,
                ).pack(side="left", padx=(10, 0))

        # =====================================================
        # SESSION CARD - centerpiece (READY state)
        # =====================================================
        self._session_card = SessionCard(
            tab,
            hotkey_label=format_hotkey_display(self._settings.hotkey),
            on_change_hotkey=lambda: self._switch_tab("settings"),
            on_open_settings=lambda: self._switch_tab("settings"),
            on_view_history=lambda: None,  # already on dashboard; no-op
        )
        self._session_card.pack(fill="x", pady=(0, 26))

        # =====================================================
        # HISTORY ROW (horizontal, 3 cards)
        # =====================================================
        history_header = ctk.CTkFrame(tab, fg_color="transparent")
        history_header.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            history_header,
            text="Recent dictations",
            font=ctk.CTkFont(family=SERIF_FAMILY, size=18),
            text_color=TEXT_DARK,
        ).pack(side="left")

        ctk.CTkButton(
            history_header,
            text="Clear history",
            command=self._clear_history,
            fg_color="transparent",
            hover_color=BG_CARD_HOVER,
            text_color=TEXT_GRAY,
            font=ctk.CTkFont(family=SANS_FAMILY, size=11),
            width=100,
            height=28,
        ).pack(side="right")

        # Horizontal container that holds the history cards row.
        # Refresh logic re-populates this.
        self._history_row = ctk.CTkFrame(tab, fg_color="transparent")
        self._history_row.pack(fill="both", expand=True)

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
            fg_color=ACCENT_PRIMARY,
            hover_color=ACCENT_PRIMARY_DARK,
            text_color=TEXT_LIGHT,
            font=ctk.CTkFont(size=14, weight="bold"),
            width=120,
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
            button_color=ACCENT_PRIMARY,
            button_hover_color=ACCENT_PRIMARY_DARK,
            text_color=TEXT_DARK,
        ).pack(anchor="w", padx=20, pady=(0, 8))

        mic_btn_row = ctk.CTkFrame(mic_frame, fg_color="transparent")
        mic_btn_row.pack(anchor="w", padx=20, pady=(0, 16))

        self._mic_test_btn = ctk.CTkButton(
            mic_btn_row,
            text="Test Microphone",
            command=self._test_microphone,
            fg_color=ACCENT_PRIMARY,
            hover_color=ACCENT_PRIMARY_DARK,
            text_color=TEXT_LIGHT,
            font=ctk.CTkFont(size=14, weight="bold"),
            width=150,
        )
        self._mic_test_btn.pack(side="left")

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
            button_color=ACCENT_PRIMARY,
            button_hover_color=ACCENT_PRIMARY_DARK,
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
            progress_color=ACCENT_PRIMARY,
            button_color=ACCENT_PRIMARY_DARK,
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
            button_color=ACCENT_PRIMARY,
            button_hover_color=ACCENT_PRIMARY_DARK,
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
            button_color=ACCENT_PRIMARY,
            button_hover_color=ACCENT_PRIMARY_DARK,
            text_color=TEXT_DARK,
        ).pack(side="left", padx=(12, 0))

        self._auto_stop_var = ctk.BooleanVar(value=self._settings.auto_stop_recording)
        ctk.CTkSwitch(
            limits_frame,
            text="Auto-stop when limit reached",
            variable=self._auto_stop_var,
            font=ctk.CTkFont(size=13),
            text_color=TEXT_DARK,
            progress_color=ACCENT_PRIMARY,
            button_color=ACCENT_PRIMARY_DARK,
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
            progress_color=ACCENT_PRIMARY,
            button_color=ACCENT_PRIMARY_DARK,
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
            progress_color=ACCENT_PRIMARY,
            button_color=ACCENT_PRIMARY_DARK,
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
            progress_color=ACCENT_PRIMARY,
            button_color=ACCENT_PRIMARY_DARK,
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            autostart_frame,
            text="Ditado will start automatically when you log in",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 16))

        # Privacy Section
        self._build_section_header(scroll, "Privacy")

        privacy_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12)
        privacy_frame.pack(fill="x", pady=(0, 10))

        self._history_text_var = ctk.BooleanVar(value=self._history.store_full_text)
        ctk.CTkSwitch(
            privacy_frame,
            text="Store transcription text in history",
            variable=self._history_text_var,
            font=ctk.CTkFont(size=14),
            text_color=TEXT_DARK,
            progress_color=ACCENT_PRIMARY,
            button_color=ACCENT_PRIMARY_DARK,
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            privacy_frame,
            text="When off, new history entries keep only word counts — no text is saved to disk",
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

        self._api_test_btn = ctk.CTkButton(
            btn_row,
            text="Test Connection",
            command=self._test_api,
            fg_color=ACCENT_PRIMARY,
            hover_color=ACCENT_PRIMARY_DARK,
            text_color=TEXT_LIGHT,
            font=ctk.CTkFont(size=14, weight="bold"),
            width=150,
        )
        self._api_test_btn.pack(side="left", padx=(10, 0))

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
            text_color=ACCENT_PRIMARY_DARK,
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
            button_color=ACCENT_PRIMARY,
            button_hover_color=ACCENT_PRIMARY_DARK,
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
            button_color=ACCENT_PRIMARY,
            button_hover_color=ACCENT_PRIMARY_DARK,
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
        self._add_stat_row(cost_frame, "Total", f"${costs['total']:.4f}", bold=True, color=SUCCESS_TEXT)

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
            text_color=ACCENT_PRIMARY_DARK,
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
        """Add a save button to a tab (one per tab; all get the saved feedback)."""
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(25, 15))

        save_btn = ctk.CTkButton(
            btn_frame,
            text="Save Settings",
            command=self._save_settings,
            fg_color=ACCENT_PRIMARY,
            hover_color=ACCENT_PRIMARY_DARK,
            text_color=TEXT_LIGHT,
            height=44,
            width=150,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=12,
        )
        save_btn.pack(side="left")
        self._save_btns.append(save_btn)

    # ========================
    # SOFT WARMTH HELPERS
    # ========================
    def _get_date_label(self) -> str:
        """Format today's date as small-caps editorial label.

        Example output: "FRIDAY  ·  22 MAY 2026"
        """
        now = datetime.now()
        # Locale-independent English day/month names (matches reference design)
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday",
                    "Friday", "Saturday", "Sunday"]
        months = ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
        day_name = weekdays[now.weekday()].upper()
        month_name = months[now.month - 1].upper()
        return f"{day_name}  ·  {now.day} {month_name} {now.year}"

    def _get_first_name(self) -> str:
        """Best-effort: the user's first name for the greeting."""
        # Prefer a future settings field, fall back to OS username
        name = getattr(self._settings, "user_first_name", "") or ""
        if not name:
            try:
                name = os.getlogin()
            except Exception:
                name = ""
        if not name:
            return "there"
        # Take first token, capitalize
        first = name.replace("_", " ").split()[0] if name.strip() else ""
        return first.capitalize() or "there"

    def _get_greeting_text(self) -> str:
        """Build the hero greeting: "Good morning/afternoon/evening, {Name}."."""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            slot = "Good morning"
        elif 12 <= hour < 18:
            slot = "Good afternoon"
        else:
            slot = "Good evening"
        return f"{slot}, {self._get_first_name()}."

    def _get_streak_days(self) -> int:
        """Count consecutive days (including today) with at least one dictation."""
        entries = self._history.entries
        if not entries:
            return 0

        # Build set of unique dictation dates
        days = set()
        for entry in entries:
            try:
                dt = datetime.fromisoformat(entry.timestamp)
                days.add(dt.date())
            except (ValueError, TypeError):
                continue

        if not days:
            return 0

        # Walk back from today as long as each previous day appears
        today = datetime.now().date()
        # If no dictation today and not yesterday either, no active streak
        if today not in days and (today - max(days)).days > 1:
            return 0

        streak = 0
        cursor = today if today in days else max(days)
        while cursor in days:
            streak += 1
            cursor = cursor - timedelta(days=1)
        return streak

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
        """Test the selected microphone (worker thread; UI updates marshaled)."""
        selected_name = self._audio_device_var.get()
        device_index = None
        if selected_name != "System Default":
            for d in self._audio_devices:
                if d["name"] == selected_name:
                    device_index = d["index"]
                    break

        if self._mic_test_btn:
            self._mic_test_btn.configure(state="disabled")
        self._mic_status.configure(text="Recording a 1s sample...", text_color=TEXT_GRAY)

        def test():
            try:
                import sounddevice as sd
                import numpy as np

                audio = sd.rec(16000, samplerate=16000, channels=1, dtype=np.int16, device=device_index)
                sd.wait()
                avg_level = np.abs(audio).mean() / 32768.0

                if avg_level > 0.01:
                    result = ("Microphone working great!", SUCCESS_TEXT)
                elif avg_level > 0.001:
                    result = ("Mic detected but volume is low. Speak louder or move closer.", WARNING_TEXT)
                else:
                    result = ("No sound detected. Check mic connection.", ERROR_TEXT)
            except Exception as e:
                error_msg = str(e)
                if "PortAudio" in error_msg or "device" in error_msg.lower():
                    result = ("Mic not found. Check it's connected.", ERROR_TEXT)
                else:
                    result = (f"Error: {error_msg[:40]}", ERROR_TEXT)
            self._finish_async_test(self._mic_test_btn, self._mic_status, result)

        threading.Thread(target=test, daemon=True).start()

    def _test_api(self) -> None:
        """Test the API connection (worker thread; UI updates marshaled)."""
        api_key = self._api_key_entry.get().strip()
        if not api_key:
            self._api_status.configure(text="API key is empty", text_color=ERROR_TEXT)
            return
        if not api_key.startswith("sk-"):
            self._api_status.configure(text="Key should start with 'sk-'", text_color=ERROR_TEXT)
            return

        if self._api_test_btn:
            self._api_test_btn.configure(state="disabled")
        self._api_status.configure(text="Testing...", text_color=TEXT_GRAY)

        def test():
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key)
                client.models.list()
                result = ("Connection successful!", SUCCESS_TEXT)
            except Exception as e:
                result = (f"Error: {str(e)[:40]}", ERROR_TEXT)
            self._finish_async_test(self._api_test_btn, self._api_status, result)

        threading.Thread(target=test, daemon=True).start()

    def _finish_async_test(self, btn, label, result) -> None:
        """Post a worker-thread test result onto the Tk main loop.

        Tkinter widgets must only be touched from the thread running the
        mainloop; workers hand their (text, color) result to this method.
        """
        text, color = result

        def apply():
            if label is not None and label.winfo_exists():
                label.configure(text=text, text_color=color)
            if btn is not None and btn.winfo_exists():
                btn.configure(state="normal")

        try:
            if self._window is not None:
                self._window.after(0, apply)
        except Exception:
            pass  # window torn down while the test was running

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

        # History privacy preference
        if self._history_text_var is not None:
            self._history.set_privacy_mode(self._history_text_var.get())

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

        # Main card with rounded corners and subtle terracotta border
        card = ctk.CTkFrame(
            self._toast_frame,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=ACCENT_PRIMARY_LIGHT,
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

        # Also update the save buttons temporarily (one per tab)
        for btn in self._save_btns:
            if btn.winfo_exists():
                btn.configure(text="✓ Saved!", fg_color=SUCCESS)

        def restore_buttons():
            for btn in self._save_btns:
                if btn.winfo_exists():
                    btn.configure(text="Save Settings", fg_color=ACCENT_PRIMARY)

        self._window.after(2000, restore_buttons)

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
        self.refresh_history()
        self._update_info_card()

    def refresh_history(self) -> None:
        """Update the horizontal history cards row (Soft Warmth layout)."""
        if not self._window or not self._window.winfo_exists():
            return

        row = getattr(self, "_history_row", None)
        if row is None:
            return

        # Clear current cards
        for widget in row.winfo_children():
            widget.destroy()

        entries = self._history.get_recent(3)  # 3-card row

        if not entries:
            # Empty state — single subtle prompt where the cards would be
            empty = ctk.CTkFrame(row, fg_color="transparent")
            empty.pack(fill="both", expand=True, pady=24)

            ctk.CTkLabel(
                empty,
                text="No dictations yet.",
                font=ctk.CTkFont(family=SERIF_FAMILY, size=15),
                text_color=TEXT_MUTED,
            ).pack()

            ctk.CTkLabel(
                empty,
                text=f"Hold {format_hotkey_display(self._settings.hotkey)} to start.",
                font=ctk.CTkFont(family=SANS_FAMILY, size=11),
                text_color=TEXT_MUTED,
            ).pack(pady=(4, 0))
            return

        # Grid: 3 equal-width columns
        row.grid_columnconfigure((0, 1, 2), weight=1, uniform="hist")

        for i, entry in enumerate(entries):
            card = HistoryWaveCard(
                row,
                timestamp_label=format_relative_time(entry.timestamp),
                title_preview=entry.text,
                duration_seconds=entry.duration_seconds,
                word_count=entry.word_count,
                seed=entry.id,
            )
            card.grid(row=0, column=i, padx=(0 if i == 0 else 12, 0), sticky="nsew")

    def _update_info_card(self) -> None:
        """Update the hotkey hint wherever it's displayed."""
        # Session card (Soft Warmth layout) - update headline hotkey label
        session = getattr(self, "_session_card", None)
        if session is not None:
            try:
                session.set_hotkey_label(format_hotkey_display(self._settings.hotkey))
            except Exception:
                pass

    def _update_api_warning(self) -> None:
        """Update API warning visibility."""
        if self._api_warning_frame:
            if self._settings.is_configured():
                self._api_warning_frame.pack_forget()
            else:
                # Re-pack it if not configured
                pass  # It's already packed on initial build
