"""Main application class for Ditado."""

import atexit
import os
import sys
import threading
import time
from typing import Optional
import customtkinter as ctk

from .config.settings import Settings, get_settings
from .config.history import TranscriptionHistory, TranscriptionHistoryEntry
from .audio.recorder import AudioRecorder
from .audio.muter import AudioMuter
from .audio.sound_player import SoundPlayer
from .transcription.whisper import WhisperTranscriber, TranscriptionError
from .transcription.enhancer import TextEnhancer, EnhancementError
from .input.hotkey import HotkeyListener
from .input.typer import TextTyper
from .ui.overlay import RecordingOverlay
from .ui.tray import SystemTray, get_asset_path
from .ui.home import HomeWindow
from .utils.logger import get_logger, setup_logging

logger = get_logger("app")

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff in seconds


class DitadoApp:
    """Main application orchestrator."""

    def __init__(self):
        self._settings = get_settings()
        self._history = TranscriptionHistory.load()
        self._running = False
        self._enabled = True

        # Core components
        self._recorder = AudioRecorder(device_index=self._settings.audio_device_index)
        self._muter = AudioMuter()
        self._typer = TextTyper()
        self._sound_player = SoundPlayer(enabled=self._settings.sound_feedback)
        self._transcriber: Optional[WhisperTranscriber] = None
        self._enhancer: Optional[TextEnhancer] = None

        # Register cleanup handler for unexpected exits
        atexit.register(self._cleanup_on_exit)

        # UI components
        self._overlay = RecordingOverlay(position=self._settings.indicator_position)
        self._tray = SystemTray(
            on_toggle=self._on_toggle,
            on_settings=self._show_home,  # Settings now integrated in dashboard
            on_exit=self._exit,
            on_usage=self._show_usage,
            on_dashboard=self._show_home,
        )
        self._home_window: Optional[HomeWindow] = None

        # Hotkey listener
        self._hotkey = HotkeyListener(
            hotkey=self._settings.hotkey,
            on_press=self._on_hotkey_press,
            on_release=self._on_hotkey_release,
        )

        # Tkinter root for settings window
        self._root: Optional[ctk.CTk] = None

        # Recording limit timer
        self._recording_timer: Optional[threading.Timer] = None

        # Lock to prevent duplicate processing
        self._processing_lock = threading.Lock()
        self._is_processing = False

        # Initialize API clients if configured
        self._init_api_clients()

    def _init_api_clients(self) -> None:
        """Initialize API clients with current settings."""
        if self._settings.api_key:
            self._transcriber = WhisperTranscriber(
                api_key=self._settings.api_key,
                model=self._settings.whisper_model,
            )
            if self._settings.enhance_text:
                self._enhancer = TextEnhancer(
                    api_key=self._settings.api_key,
                    model=self._settings.gpt_model,
                )

    def run(self) -> None:
        """Run the application."""
        if self._running:
            return

        # Initialize logging
        setup_logging()

        # Set Windows AppUserModelID for proper taskbar icon
        # Must be called BEFORE any windows are created
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Ditado.VoiceDictation.1.0')

        self._running = True

        # Sync autostart setting with Windows registry
        from .utils.autostart import set_autostart, is_autostart_enabled
        if self._settings.auto_start_on_boot != is_autostart_enabled():
            set_autostart(self._settings.auto_start_on_boot)

        # Start components
        self._overlay.start()
        self._tray.start()
        self._hotkey.start()

        logger.info("Ditado is running")
        logger.info(f"Current hotkey: {self._settings.hotkey}")
        print("Ditado is running. Hold your hotkey to dictate.")
        print(f"Current hotkey: {self._settings.hotkey}")

        # Create root window for settings
        self._root = ctk.CTk()
        self._root.title("Ditado")
        self._root.geometry("1x1+0+0")  # Tiny window
        self._root.withdraw()  # Hide the main window

        # Set window icon for taskbar (300ms delay to override CustomTkinter's default at 200ms)
        try:
            icon_path = get_asset_path("icon.ico")
            self._root.after(300, lambda: self._root.iconbitmap(icon_path))
        except Exception:
            pass

        # Always show home page on startup (like Wispr Flow)
        self._root.after(100, self._show_home)

        # Run the main loop
        try:
            self._root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the application and fully terminate the process."""
        if not self._running:
            return

        self._running = False
        logger.info("Shutting down Ditado...")

        # Stop hotkey listener first (prevents new recordings)
        try:
            self._hotkey.stop()
        except Exception as e:
            logger.debug(f"Error stopping hotkey: {e}")

        # Stop overlay (has its own Tkinter instance)
        try:
            self._overlay.stop()
        except Exception as e:
            logger.debug(f"Error stopping overlay: {e}")

        # Stop system tray
        try:
            self._tray.stop()
        except Exception as e:
            logger.debug(f"Error stopping tray: {e}")

        # Ensure system audio is restored on exit
        try:
            self._muter.force_unmute()
            self._muter.cleanup()
        except Exception as e:
            logger.debug(f"Error cleaning up muter: {e}")

        # Close home window if open
        if self._home_window:
            try:
                self._home_window.close()
            except Exception as e:
                logger.debug(f"Error closing home window: {e}")
            self._home_window = None

        # Destroy Tkinter root window
        if self._root:
            try:
                # Schedule destroy on main thread
                self._root.quit()
                self._root.destroy()
            except Exception as e:
                logger.debug(f"Error destroying root window: {e}")
            self._root = None

        logger.info("Ditado shutdown complete")

        # Force terminate the process to ensure all threads exit
        # Use os._exit for immediate termination (skips cleanup handlers)
        # This is necessary because daemon threads may still be running
        os._exit(0)

    def _cleanup_on_exit(self) -> None:
        """Emergency cleanup on unexpected exit."""
        try:
            self._muter.force_unmute()
            self._muter.cleanup()
        except Exception:
            pass

    def _on_toggle(self, enabled: bool) -> None:
        """Handle enable/disable toggle from tray."""
        self._enabled = enabled
        self._hotkey.set_enabled(enabled)

        if enabled:
            logger.info("Dictation enabled")
            print("Ditado: Enabled")
        else:
            logger.info("Dictation disabled")
            print("Ditado: Disabled")

    def _show_home(self) -> None:
        """Show the home/dashboard window."""
        if self._home_window is None:
            self._home_window = HomeWindow(
                settings=self._settings,
                history=self._history,
                on_save=self._on_settings_saved,
                on_minimize=self._on_home_minimized,
                on_close=self._on_home_closed,
            )

        # Need to show in main thread
        if self._root:
            self._root.after(0, lambda: self._home_window.show(self._root))

    def _on_home_minimized(self) -> None:
        """Handle home window being minimized to tray."""
        logger.debug("Home window minimized to tray")

    def _on_home_closed(self) -> None:
        """Handle home window being closed."""
        logger.debug("Home window closed")

    def _on_settings_saved(self, settings: Settings) -> None:
        """Handle settings being saved."""
        self._settings = settings

        # Update hotkey
        self._hotkey.set_hotkey(settings.hotkey)

        # Update overlay position
        self._overlay.set_position(settings.indicator_position)

        # Update audio device
        self._recorder.set_device(settings.audio_device_index)

        # Update sound feedback setting
        self._sound_player.set_enabled(settings.sound_feedback)

        # Reinitialize API clients
        self._init_api_clients()

        # Refresh home window if open
        if self._home_window and self._root:
            self._root.after(0, self._home_window.refresh)

        logger.info(f"Settings saved. Hotkey: {settings.hotkey}")
        print(f"Settings saved. Hotkey: {settings.hotkey}")

    def _exit(self) -> None:
        """Exit the application - schedule on main thread."""
        if self._root:
            # Schedule stop on main Tkinter thread to avoid threading issues
            # (this is called from pystray's thread)
            self._root.after(0, self.stop)
        else:
            self.stop()

    def _show_usage(self) -> None:
        """Show usage statistics notification."""
        stats = self._settings.stats
        costs = self._settings.get_estimated_cost()

        message = (
            f"Session: {stats.session_requests} transcriptions ({stats.session_minutes:.2f} min)\n"
            f"Total: {stats.total_requests} transcriptions ({stats.total_minutes:.2f} min)\n"
            f"Estimated cost: ${costs['total']:.4f}"
        )

        self._tray.show_notification("Ditado Usage", message)

    def _on_hotkey_press(self) -> None:
        """Handle hotkey press - start recording."""
        if not self._enabled or not self._settings.is_configured():
            return

        # Play start sound BEFORE muting so user can hear it
        self._sound_player.play("start")

        # Mute system audio if enabled
        if self._settings.mute_system_audio:
            mute_result = self._muter.mute()
            logger.debug(f"System audio mute result: {mute_result}")
            # Small delay to ensure mute takes effect before recording starts
            time.sleep(0.05)

        logger.debug("Recording started")
        print("Recording...")
        self._overlay.show()
        self._overlay.set_state("recording")

        # Try to start recording
        if not self._recorder.start():
            error = self._recorder.get_last_error() or "Failed to start recording"
            logger.error(f"Recording failed: {error}")
            print(f"Error: {error}")
            self._tray.show_notification("Ditado Error", error)
            self._overlay.hide()
            # Restore audio if recording failed to start
            if self._settings.mute_system_audio:
                self._muter.restore()
            return

        # Start auto-stop timer if enabled
        if (self._settings.auto_stop_recording and
            self._settings.max_recording_seconds > 0):
            self._recording_timer = threading.Timer(
                self._settings.max_recording_seconds,
                self._auto_stop_recording
            )
            self._recording_timer.daemon = True
            self._recording_timer.start()
            logger.debug(f"Auto-stop timer set for {self._settings.max_recording_seconds}s")

    def _auto_stop_recording(self) -> None:
        """Auto-stop recording when limit is reached."""
        if self._recorder.is_recording():
            logger.info("Auto-stopping recording (limit reached)")
            print("Recording limit reached, auto-stopping...")
            self._tray.show_notification(
                "Ditado",
                f"Recording auto-stopped after {self._settings.max_recording_seconds // 60} min"
            )
            self._on_hotkey_release()

    def _on_hotkey_release(self) -> None:
        """Handle hotkey release - stop recording and transcribe."""
        # Cancel auto-stop timer if running
        if self._recording_timer:
            self._recording_timer.cancel()
            self._recording_timer = None

        # Restore system audio immediately
        if self._settings.mute_system_audio:
            self._muter.restore()

        # Play end sound AFTER unmuting so user can hear it
        self._sound_player.play("end")

        if not self._enabled or not self._recorder.is_recording():
            return

        # Prevent duplicate processing
        with self._processing_lock:
            if self._is_processing:
                logger.debug("Already processing, ignoring duplicate release")
                return
            self._is_processing = True

        # Stop recording
        audio_data = self._recorder.stop()
        duration = self._recorder.get_duration()

        if not audio_data:
            error = self._recorder.get_last_error() or "Recording too short"
            logger.debug(f"Recording ignored: {error}")
            print(f"{error}, ignoring.")
            self._overlay.hide()
            with self._processing_lock:
                self._is_processing = False
            return

        # Show transcribing state
        self._overlay.set_state("transcribing")
        logger.debug(f"Processing audio ({duration:.2f}s)")
        print("Processing...")

        # Process in background thread
        threading.Thread(
            target=self._process_audio,
            args=(audio_data, duration),
            daemon=True,
        ).start()

    def _process_audio(self, audio_data: bytes, duration: float) -> None:
        """Process recorded audio (transcribe and type)."""
        try:
            self._process_audio_inner(audio_data, duration)
        finally:
            # Always reset processing flag when done
            with self._processing_lock:
                self._is_processing = False

    def _process_audio_inner(self, audio_data: bytes, duration: float) -> None:
        """Inner processing logic."""
        if not self._transcriber:
            logger.error("Transcriber not initialized")
            print("Error: Transcriber not initialized")
            self._tray.show_notification("Ditado", "API not configured")
            self._overlay.hide()
            return

        # Warn for long recordings
        if duration > 300:  # 5 minutes
            logger.warning(f"Long recording: {duration/60:.1f} min")
            print(f"Warning: Long recording ({duration/60:.1f} min). This may be expensive.")

        # Try transcription with retries
        text = None
        minutes = 0.0
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                text, minutes = self._transcriber.transcribe(
                    audio_data,
                    language=self._settings.language,
                )
                break  # Success
            except TranscriptionError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.warning(f"Transcription failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                    print(f"Transcription failed, retrying in {delay}s... ({e})")
                    time.sleep(delay)
                else:
                    logger.error(f"Transcription failed after {MAX_RETRIES} attempts: {e}")
                    print(f"Transcription failed after {MAX_RETRIES} attempts: {e}")

        if not text:
            if last_error:
                self._tray.show_notification("Ditado Error", str(last_error)[:100])
            else:
                logger.debug("No speech detected")
                print("No speech detected.")
            self._overlay.hide()
            return

        logger.info(f"Transcribed ({minutes:.2f} min): {text[:50]}...")
        # Handle Unicode safely for console output
        try:
            print(f"Transcribed: {text}")
        except UnicodeEncodeError:
            print(f"Transcribed: [contains special characters, {len(text)} chars]")

        # Enhance with GPT if enabled (with retries)
        if self._settings.enhance_text and self._enhancer:
            self._overlay.set_state("enhancing")
            for attempt in range(MAX_RETRIES):
                try:
                    enhanced = self._enhancer.enhance(text)
                    if enhanced != text:
                        logger.info(f"Enhanced: {enhanced[:50]}...")
                        try:
                            print(f"Enhanced: {enhanced}")
                        except UnicodeEncodeError:
                            print(f"Enhanced: [contains special characters, {len(enhanced)} chars]")
                        text = enhanced
                    break
                except EnhancementError as e:
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAYS[attempt]
                        logger.warning(f"Enhancement failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                        print(f"Enhancement failed, retrying in {delay}s... ({e})")
                        time.sleep(delay)
                    else:
                        logger.error(f"Enhancement failed after {MAX_RETRIES} attempts, using original")
                        print(f"Enhancement failed after {MAX_RETRIES} attempts, using original text")
                        # Continue with original text

        # Type the text
        self._overlay.set_state("typing")
        time.sleep(0.1)  # Small delay before typing

        success = self._typer.type_text(text)
        if not success:
            # Fallback to clipboard
            self._typer.type_text_clipboard(text)

        # Hide overlay after typing
        self._overlay.hide()

        # Calculate word count
        word_count = len(text.split()) if text else 0

        # Update stats with word count
        self._settings.add_usage(minutes, word_count)

        # Add to transcription history
        entry = TranscriptionHistoryEntry.create(
            text=text,
            duration_seconds=duration,
            language=self._settings.language,
            enhanced=self._settings.enhance_text and self._enhancer is not None,
        )
        self._history.add_entry(entry)

        # Refresh home window if open (on main thread)
        if self._home_window and self._root:
            self._root.after(0, self._home_window.refresh)

        logger.info(f"Dictation complete ({minutes:.2f} min)")
        print(f"Done. ({minutes:.2f} min)")
