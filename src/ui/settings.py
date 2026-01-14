"""Settings window for Ditado."""

import os
import sys
import customtkinter as ctk
from typing import Callable, Optional
from ..config.settings import Settings
from ..transcription.whisper import SUPPORTED_LANGUAGES
from ..input.hotkey import KeyCaptureDialog
from ..audio.recorder import list_audio_devices, get_default_input_device


def get_asset_path(filename: str) -> str:
    """Get the path to an asset file, works for both dev and bundled exe."""
    if getattr(sys, 'frozen', False):
        # Running as bundled exe
        base_path = sys._MEIPASS
    else:
        # Running in development
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_path, "assets", filename)


class SettingsWindow:
    """Modern settings window using CustomTkinter."""

    def __init__(
        self,
        settings: Settings,
        on_save: Optional[Callable[[Settings], None]] = None,
    ):
        self._settings = settings
        self._on_save = on_save
        self._window: Optional[ctk.CTkToplevel] = None
        self._capturing_hotkey = False

        # Set appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

    def show(self, parent: Optional[ctk.CTk] = None) -> None:
        """Show the settings window."""
        if self._window is not None and self._window.winfo_exists():
            self._window.focus()
            return

        # Create window
        if parent:
            self._window = ctk.CTkToplevel(parent)
        else:
            self._window = ctk.CTkToplevel()

        self._window.title("Ditado Settings")
        self._window.geometry("500x750")
        self._window.resizable(False, False)

        # Set window icon (300ms delay to override CustomTkinter's default at 200ms)
        try:
            icon_path = get_asset_path("icon.ico")
            self._window.after(300, lambda: self._window.iconbitmap(icon_path))
        except Exception:
            pass

        # Create main container with padding
        container = ctk.CTkFrame(self._window, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title = ctk.CTkLabel(
            container,
            text="Ditado Settings",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        title.pack(pady=(0, 20))

        # Create tabview
        tabview = ctk.CTkTabview(container)
        tabview.pack(fill="both", expand=True)

        # Add tabs
        tab_general = tabview.add("General")
        tab_api = tabview.add("API")
        tab_usage = tabview.add("Usage")

        # Build each tab
        self._build_general_tab(tab_general)
        self._build_api_tab(tab_api)
        self._build_usage_tab(tab_usage)

        # Save button
        save_btn = ctk.CTkButton(
            container,
            text="Save Settings",
            command=self._save,
            height=40,
            font=ctk.CTkFont(size=14),
        )
        save_btn.pack(pady=(20, 0), fill="x")

    def _build_general_tab(self, parent: ctk.CTkFrame) -> None:
        """Build the General settings tab."""
        # Hotkey section
        hotkey_frame = ctk.CTkFrame(parent)
        hotkey_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            hotkey_frame,
            text="Push-to-Talk Hotkey",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        hotkey_row = ctk.CTkFrame(hotkey_frame, fg_color="transparent")
        hotkey_row.pack(fill="x", padx=10, pady=(0, 10))

        self._hotkey_var = ctk.StringVar(value=self._settings.hotkey)
        self._hotkey_entry = ctk.CTkEntry(
            hotkey_row,
            textvariable=self._hotkey_var,
            width=200,
            state="readonly",
        )
        self._hotkey_entry.pack(side="left", padx=(0, 10))

        self._capture_btn = ctk.CTkButton(
            hotkey_row,
            text="Capture Key",
            command=self._start_hotkey_capture,
            width=100,
        )
        self._capture_btn.pack(side="left")

        # Language section
        lang_frame = ctk.CTkFrame(parent)
        lang_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            lang_frame,
            text="Dictation Language",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        # Create language options
        lang_options = [f"{code}: {name}" for code, name in SUPPORTED_LANGUAGES.items()]
        current_lang = f"{self._settings.language}: {SUPPORTED_LANGUAGES.get(self._settings.language, 'Unknown')}"

        self._lang_var = ctk.StringVar(value=current_lang)
        self._lang_menu = ctk.CTkOptionMenu(
            lang_frame,
            variable=self._lang_var,
            values=lang_options,
            width=250,
        )
        self._lang_menu.pack(anchor="w", padx=10, pady=(0, 10))

        # Indicator position
        pos_frame = ctk.CTkFrame(parent)
        pos_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            pos_frame,
            text="Indicator Position",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        positions = ["top-left", "top-right", "bottom-left", "bottom-right"]
        self._pos_var = ctk.StringVar(value=self._settings.indicator_position)
        self._pos_menu = ctk.CTkOptionMenu(
            pos_frame,
            variable=self._pos_var,
            values=positions,
            width=200,
        )
        self._pos_menu.pack(anchor="w", padx=10, pady=(0, 10))

        # Audio device selection
        audio_frame = ctk.CTkFrame(parent)
        audio_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            audio_frame,
            text="Microphone",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        # Get available audio devices
        self._audio_devices = list_audio_devices()
        device_names = ["System Default"]
        for device in self._audio_devices:
            device_names.append(f"{device['name']}")

        # Find current selection
        current_device = "System Default"
        if self._settings.audio_device_index is not None:
            for device in self._audio_devices:
                if device["index"] == self._settings.audio_device_index:
                    current_device = device["name"]
                    break

        self._audio_device_var = ctk.StringVar(value=current_device)
        self._audio_device_menu = ctk.CTkOptionMenu(
            audio_frame,
            variable=self._audio_device_var,
            values=device_names,
            width=350,
        )
        self._audio_device_menu.pack(anchor="w", padx=10, pady=(0, 5))

        # Test microphone button
        test_mic_btn = ctk.CTkButton(
            audio_frame,
            text="Test Microphone",
            command=self._test_microphone,
            width=120,
        )
        test_mic_btn.pack(anchor="w", padx=10, pady=(0, 5))

        self._mic_status = ctk.CTkLabel(
            audio_frame,
            text="",
            font=ctk.CTkFont(size=12),
        )
        self._mic_status.pack(anchor="w", padx=10, pady=(0, 10))

        # Recording limits section
        limits_frame = ctk.CTkFrame(parent)
        limits_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            limits_frame,
            text="Recording Limits",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        # Max recording duration
        duration_row = ctk.CTkFrame(limits_frame, fg_color="transparent")
        duration_row.pack(fill="x", padx=10, pady=(0, 5))

        ctk.CTkLabel(
            duration_row,
            text="Max duration:",
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

        # Convert seconds to minutes for display
        duration_options = ["1 min", "2 min", "5 min", "10 min", "15 min", "No limit"]
        duration_values = {
            "1 min": 60,
            "2 min": 120,
            "5 min": 300,
            "10 min": 600,
            "15 min": 900,
            "No limit": 0,
        }

        # Find current value
        current_duration = "5 min"  # default
        for name, seconds in duration_values.items():
            if seconds == self._settings.max_recording_seconds:
                current_duration = name
                break
        if self._settings.max_recording_seconds == 0:
            current_duration = "No limit"

        self._duration_var = ctk.StringVar(value=current_duration)
        self._duration_menu = ctk.CTkOptionMenu(
            duration_row,
            variable=self._duration_var,
            values=duration_options,
            width=120,
        )
        self._duration_menu.pack(side="left", padx=(10, 0))

        # Auto-stop toggle
        self._auto_stop_var = ctk.BooleanVar(value=self._settings.auto_stop_recording)
        auto_stop_switch = ctk.CTkSwitch(
            limits_frame,
            text="Auto-stop when limit reached",
            variable=self._auto_stop_var,
            font=ctk.CTkFont(size=12),
        )
        auto_stop_switch.pack(anchor="w", padx=10, pady=(5, 10))

        # Store duration values for save
        self._duration_values = duration_values

        # AI Enhancement toggle
        enhance_frame = ctk.CTkFrame(parent)
        enhance_frame.pack(fill="x", pady=10)

        self._enhance_var = ctk.BooleanVar(value=self._settings.enhance_text)
        enhance_switch = ctk.CTkSwitch(
            enhance_frame,
            text="AI Text Enhancement (GPT cleanup)",
            variable=self._enhance_var,
            font=ctk.CTkFont(size=14),
        )
        enhance_switch.pack(anchor="w", padx=10, pady=10)

        ctk.CTkLabel(
            enhance_frame,
            text="Removes filler words and fixes grammar",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        ).pack(anchor="w", padx=10, pady=(0, 10))

    def _build_api_tab(self, parent: ctk.CTkFrame) -> None:
        """Build the API settings tab."""
        # API Key section
        key_frame = ctk.CTkFrame(parent)
        key_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            key_frame,
            text="OpenAI API Key",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        self._api_key_var = ctk.StringVar(value=self._settings.api_key)
        self._api_key_entry = ctk.CTkEntry(
            key_frame,
            textvariable=self._api_key_var,
            width=400,
            show="*",
            placeholder_text="sk-...",
        )
        self._api_key_entry.pack(anchor="w", padx=10, pady=(0, 5))

        # Show/hide toggle
        self._show_key = False
        self._show_key_btn = ctk.CTkButton(
            key_frame,
            text="Show Key",
            command=self._toggle_key_visibility,
            width=80,
            height=28,
        )
        self._show_key_btn.pack(anchor="w", padx=10, pady=(0, 10))

        # Test connection button
        test_btn = ctk.CTkButton(
            key_frame,
            text="Test Connection",
            command=self._test_api,
            width=120,
        )
        test_btn.pack(anchor="w", padx=10, pady=(0, 10))

        self._api_status = ctk.CTkLabel(
            key_frame,
            text="",
            font=ctk.CTkFont(size=12),
        )
        self._api_status.pack(anchor="w", padx=10, pady=(0, 10))

        # Models section
        models_frame = ctk.CTkFrame(parent)
        models_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            models_frame,
            text="Models",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        # Whisper model
        ctk.CTkLabel(
            models_frame,
            text="Transcription Model:",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=10, pady=(5, 0))

        self._whisper_var = ctk.StringVar(value=self._settings.whisper_model)
        whisper_menu = ctk.CTkOptionMenu(
            models_frame,
            variable=self._whisper_var,
            values=["whisper-1"],
            width=200,
        )
        whisper_menu.pack(anchor="w", padx=10, pady=(0, 10))

        # GPT model
        ctk.CTkLabel(
            models_frame,
            text="Enhancement Model:",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=10, pady=(5, 0))

        self._gpt_var = ctk.StringVar(value=self._settings.gpt_model)
        gpt_menu = ctk.CTkOptionMenu(
            models_frame,
            variable=self._gpt_var,
            values=["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
            width=200,
        )
        gpt_menu.pack(anchor="w", padx=10, pady=(0, 10))

    def _build_usage_tab(self, parent: ctk.CTkFrame) -> None:
        """Build the Usage statistics tab."""
        stats = self._settings.stats
        costs = self._settings.get_estimated_cost()

        # Session stats
        session_frame = ctk.CTkFrame(parent)
        session_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            session_frame,
            text="This Session",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            session_frame,
            text=f"Transcriptions: {stats.session_requests}",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=10)

        ctk.CTkLabel(
            session_frame,
            text=f"Minutes: {stats.session_minutes:.2f}",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=10, pady=(0, 10))

        # Total stats
        total_frame = ctk.CTkFrame(parent)
        total_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            total_frame,
            text="All Time",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            total_frame,
            text=f"Transcriptions: {stats.total_requests}",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=10)

        ctk.CTkLabel(
            total_frame,
            text=f"Minutes: {stats.total_minutes:.2f}",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=10, pady=(0, 10))

        # Cost estimates
        cost_frame = ctk.CTkFrame(parent)
        cost_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            cost_frame,
            text="Estimated Costs",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            cost_frame,
            text=f"Whisper: ${costs['whisper']:.4f}",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=10)

        ctk.CTkLabel(
            cost_frame,
            text=f"GPT Enhancement: ${costs['gpt']:.4f}",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=10)

        ctk.CTkLabel(
            cost_frame,
            text=f"Total: ${costs['total']:.4f}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#4CAF50",
        ).pack(anchor="w", padx=10, pady=(5, 10))

        # Info
        ctk.CTkLabel(
            parent,
            text="Whisper: $0.006/min | GPT-4o-mini: ~$0.0003/request",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        ).pack(anchor="w", padx=10, pady=10)

    def _start_hotkey_capture(self) -> None:
        """Start capturing a new hotkey."""
        if self._capturing_hotkey:
            return

        self._capturing_hotkey = True
        self._capture_btn.configure(text="Press a key...")
        self._hotkey_entry.configure(state="normal")
        self._hotkey_entry.delete(0, "end")
        self._hotkey_entry.insert(0, "Waiting...")

        def on_key_captured(key: str):
            # Use after() to safely update UI from another thread
            if self._window and self._window.winfo_exists():
                self._window.after(0, lambda: self._finish_hotkey_capture(key))

        capture = KeyCaptureDialog(on_key_captured)
        capture.start_capture()

    def _finish_hotkey_capture(self, key: str) -> None:
        """Finish hotkey capture - called on main thread."""
        self._hotkey_entry.configure(state="normal")
        self._hotkey_entry.delete(0, "end")
        self._hotkey_entry.insert(0, key)
        self._hotkey_entry.configure(state="readonly")
        self._capture_btn.configure(text="Capture Key")
        self._capturing_hotkey = False

    def _toggle_key_visibility(self) -> None:
        """Toggle API key visibility."""
        self._show_key = not self._show_key
        self._api_key_entry.configure(show="" if self._show_key else "*")
        self._show_key_btn.configure(text="Hide Key" if self._show_key else "Show Key")

    def _test_microphone(self) -> None:
        """Test the selected microphone with a short recording."""
        import threading
        import time

        # Get selected device index
        selected_name = self._audio_device_var.get()
        device_index = None
        if selected_name != "System Default":
            for device in self._audio_devices:
                if device["name"] == selected_name:
                    device_index = device["index"]
                    break

        def test():
            try:
                import sounddevice as sd
                import numpy as np

                self._mic_status.configure(text="Recording...", text_color="gray")

                # Record 1 second of audio
                duration = 1.0
                sample_rate = 16000
                audio = sd.rec(
                    int(duration * sample_rate),
                    samplerate=sample_rate,
                    channels=1,
                    dtype=np.int16,
                    device=device_index,
                )
                sd.wait()

                # Check audio level
                avg_level = np.abs(audio).mean() / 32768.0

                if avg_level > 0.01:
                    self._mic_status.configure(
                        text=f"Microphone working! (level: {avg_level:.3f})",
                        text_color="#4CAF50"
                    )
                elif avg_level > 0.001:
                    self._mic_status.configure(
                        text=f"Low volume detected (level: {avg_level:.4f})",
                        text_color="#FFA726"
                    )
                else:
                    self._mic_status.configure(
                        text="No audio detected - check microphone",
                        text_color="#E53935"
                    )

            except Exception as e:
                self._mic_status.configure(
                    text=f"Error: {str(e)[:50]}",
                    text_color="#E53935"
                )

        self._mic_status.configure(text="Testing...", text_color="gray")
        threading.Thread(target=test, daemon=True).start()

    def _test_api(self) -> None:
        """Test the API connection."""
        import threading

        # Get the API key directly from the entry widget
        api_key = self._api_key_entry.get().strip()

        def test():
            try:
                from openai import OpenAI
                if not api_key:
                    self._api_status.configure(text="Error: API key is empty", text_color="#E53935")
                    return
                if not api_key.startswith("sk-"):
                    self._api_status.configure(text="Error: API key should start with 'sk-'", text_color="#E53935")
                    return
                print(f"Testing API key (length: {len(api_key)}, starts: {api_key[:20]}...)")
                client = OpenAI(api_key=api_key)
                # Simple test - list models
                client.models.list()
                self._api_status.configure(text="Connection successful!", text_color="#4CAF50")
            except Exception as e:
                self._api_status.configure(text=f"Error: {str(e)}", text_color="#E53935")

        self._api_status.configure(text="Testing...", text_color="gray")
        threading.Thread(target=test, daemon=True).start()

    def _save(self) -> None:
        """Save settings."""
        # Update settings - read directly from entry widgets
        self._settings.hotkey = self._hotkey_entry.get().strip()

        # Extract language code from "code: name" format
        lang_selection = self._lang_var.get()
        self._settings.language = lang_selection.split(":")[0]

        self._settings.indicator_position = self._pos_var.get()
        self._settings.enhance_text = self._enhance_var.get()
        self._settings.api_key = self._api_key_entry.get().strip()
        self._settings.whisper_model = self._whisper_var.get()
        self._settings.gpt_model = self._gpt_var.get()

        # Audio device selection
        selected_name = self._audio_device_var.get()
        if selected_name == "System Default":
            self._settings.audio_device_index = None
        else:
            for device in self._audio_devices:
                if device["name"] == selected_name:
                    self._settings.audio_device_index = device["index"]
                    break

        # Recording limits
        duration_name = self._duration_var.get()
        self._settings.max_recording_seconds = self._duration_values.get(duration_name, 300)
        self._settings.auto_stop_recording = self._auto_stop_var.get()

        # Save to file
        self._settings.save()

        # Callback
        if self._on_save:
            self._on_save(self._settings)

        # Close window
        if self._window:
            self._window.destroy()
            self._window = None

    def close(self) -> None:
        """Close the settings window."""
        if self._window:
            self._window.destroy()
            self._window = None
