"""Main application class for Ditado."""

import atexit
import os
import sys
import threading
import time
from typing import Optional

import webview

from .config.settings import Settings, get_settings
from .config.history import TranscriptionHistory, TranscriptionHistoryEntry
from .audio.recorder import AudioRecorder
from .audio.muter import AudioMuter
from .audio.sound_player import SoundPlayer
from .transcription.whisper import WhisperTranscriber, TranscriptionError
from .transcription.enhancer import TextEnhancer, EnhancementError
from .input.hotkey import HotkeyListener
from .input.typer import TextTyper
from .recording_controller import RecordingController
from .ui.weboverlay import WebOverlay
from .ui.tray import SystemTray
from .ui.webhost import WebDashboard
from .ui.correction_popup import CorrectionPopup
from .vocabulary.dictionary import get_dictionary
from .vocabulary.correction_detector import CorrectionDetector, DetectedCorrection
from .utils.logger import get_logger, setup_logging
from .utils.window_context import get_foreground_context, WindowContext

logger = get_logger("app")

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2]  # Backoff before the 2nd and 3rd attempts

# Whisper rejects uploads over ~25 MB; leave headroom (~13 min at 16 kHz mono)
MAX_UPLOAD_BYTES = 24 * 1024 * 1024


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

        # Vocabulary learning system
        self._vocabulary = get_dictionary()
        self._correction_popup = CorrectionPopup(
            on_accept=self._on_correction_accepted,
            on_reject=self._on_correction_rejected
        )
        self._correction_detector = CorrectionDetector(
            on_correction_detected=self._on_correction_detected
        )

        # Register cleanup handler for unexpected exits
        atexit.register(self._cleanup_on_exit)

        # UI components — overlay web "Fita" (pill WebView2, nunca rouba foco)
        self._overlay = WebOverlay(position=self._settings.indicator_position)

        # Live audio level -> overlay waveform (called from recorder thread)
        self._recorder.set_level_callback(self._overlay.set_audio_level)
        self._tray = SystemTray(
            on_toggle=self._on_toggle,
            on_settings=self._show_home,  # Settings now integrated in dashboard
            on_exit=self._exit,
            on_usage=self._show_usage,
            on_dashboard=self._show_home,
        )

        # Hotkey listener
        self._hotkey = HotkeyListener(
            hotkey=self._settings.hotkey,
            on_press=self._on_hotkey_press,
            on_release=self._on_hotkey_release,
        )

        # Serializes text injection so two finished dictations can't interleave
        self._typing_lock = threading.Lock()

        # Last cleaned dictation (used to prime Whisper acoustic decoding)
        self._last_dictation: str = ""

        # Recording state machine: single-owner worker thread that serializes
        # press/release/auto-stop/toggle and keeps hook callbacks cheap
        self._controller = RecordingController(
            recorder=self._recorder,
            muter=self._muter,
            sound_player=self._sound_player,
            overlay=self._overlay,
            get_settings=lambda: self._settings,
            capture_context=self._capture_foreground_context,
            on_audio_ready=self._start_processing_job,
            notify=self._tray.show_notification,
        )

        # Dashboard web (WebView2) — a janela em si é criada em run()
        self._dashboard = WebDashboard(
            settings=self._settings,
            history=self._history,
            on_save=self._on_settings_saved,
            get_enabled=lambda: self._enabled,
        )
        # Estado do pipeline em tempo real no dashboard (dot REC, status)
        self._controller.on_state = self._dashboard.notify_state

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

        # Start components (controller before hotkey so events have a consumer)
        self._overlay.start()
        self._tray.start()
        self._controller.start()
        self._hotkey.start()

        logger.info("Ditado is running")
        logger.info(f"Current hotkey: {self._settings.hotkey}")
        print("Ditado is running. Hold your hotkey to dictate.")
        print(f"Current hotkey: {self._settings.hotkey}")

        # Dashboard web (WebView2). webview.start() bloqueia até a janela ser
        # destruída no stop(); fechar a janela apenas a esconde (fica no tray).
        self._dashboard.create()
        self._overlay.create()
        try:
            webview.start()
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

        # Stop the recording controller (ends any live recording, restores audio)
        try:
            self._controller.stop()
        except Exception as e:
            logger.debug(f"Error stopping controller: {e}")

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

        # Destroy the dashboard window (unblocks webview.start on main thread)
        try:
            self._dashboard.destroy()
        except Exception as e:
            logger.debug(f"Error destroying dashboard: {e}")

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
        # Stops and discards a live recording so the mic is never left open
        self._controller.set_enabled(enabled)

        # Reflect the new state on the dashboard
        self._dashboard.notify_enabled(enabled)

        if enabled:
            logger.info("Dictation enabled")
            print("Ditado: Enabled")
        else:
            logger.info("Dictation disabled")
            print("Ditado: Disabled")

    def _show_home(self) -> None:
        """Show the dashboard window (thread-safe; called from the tray)."""
        self._dashboard.show()

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

        logger.info(f"Settings saved. Hotkey: {settings.hotkey}")
        print(f"Settings saved. Hotkey: {settings.hotkey}")

    def _exit(self) -> None:
        """Exit the application (called from the tray thread)."""
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
        """Hotkey pressed — enqueue only; the hook thread must never block."""
        self._controller.on_press()

    def _on_hotkey_release(self) -> None:
        """Hotkey released — enqueue only; the hook thread must never block."""
        self._controller.on_release()

    def _capture_foreground_context(self) -> Optional[WindowContext]:
        """Capture which app the user is dictating into (never Ditado itself)."""
        try:
            ctx = get_foreground_context()
            if ctx and "ditado" not in (ctx.process_name or "").lower():
                return ctx
        except Exception:
            pass
        return None

    def _start_processing_job(self, audio_data: bytes, duration: float,
                              context: Optional[WindowContext]) -> None:
        """Spawn the per-dictation processing thread (called by the controller)."""
        threading.Thread(
            target=self._process_audio,
            args=(audio_data, duration, context),
            daemon=True,
        ).start()

    def _process_audio(self, audio_data: bytes, duration: float,
                       context: Optional[WindowContext]) -> None:
        """Process recorded audio (transcribe and type)."""
        try:
            self._process_audio_inner(audio_data, duration, context)
        except Exception as e:
            # Never let this worker die silently: the overlay would stay
            # stuck in its "transcribing"/"enhancing" animation forever.
            logger.exception(f"Unexpected error while processing dictation: {e}")
            try:
                self._tray.show_notification("Ditado Error", f"Unexpected error: {str(e)[:80]}")
                self._controller.job_set_state("error")
                time.sleep(1.6)
            except Exception:
                pass
        finally:
            # The controller reverts the overlay once no job is running
            self._controller.job_finished()

    def _process_audio_inner(self, audio_data: bytes, duration: float,
                             context: Optional[WindowContext]) -> None:
        """Inner processing logic."""
        if not self._transcriber:
            logger.error("Transcriber not initialized")
            print("Error: Transcriber not initialized")
            self._tray.show_notification("Ditado", "API not configured")
            return

        # Fail fast on oversized audio instead of uploading a doomed payload
        if len(audio_data) > MAX_UPLOAD_BYTES:
            logger.error(f"Recording too large for Whisper: {len(audio_data) / 1e6:.1f} MB")
            self._tray.show_notification(
                "Ditado Error",
                "Recording too long to transcribe (max ~13 min). "
                "Enable auto-stop or dictate in shorter takes.",
            )
            return

        # Warn for long recordings
        if duration > 300:  # 5 minutes
            logger.warning(f"Long recording: {duration/60:.1f} min")
            print(f"Warning: Long recording ({duration/60:.1f} min). This may be expensive.")

        # Try transcription with retries
        text = None
        minutes = 0.0
        last_error = None

        # Build Whisper context prompt: user's vocab + tail of previous dictation
        whisper_prompt = self._build_whisper_prompt()

        for attempt in range(MAX_RETRIES):
            try:
                text, minutes = self._transcriber.transcribe(
                    audio_data,
                    language=self._settings.language,
                    prompt=whisper_prompt,
                )
                break  # Success
            except TranscriptionError as e:
                last_error = e
                if not e.retryable:
                    # Deterministic failure (bad key, 4xx): retrying would only
                    # re-upload the audio and delay the error message
                    logger.error(f"Transcription failed (not retrying): {e}")
                    print(f"Transcription failed: {e}")
                    break
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
                # Brief error glyph on the overlay so failure is visible
                # in-product, not only as an easy-to-miss OS balloon
                self._controller.job_set_state("error")
                time.sleep(1.6)
            else:
                logger.debug("No speech detected")
                print("No speech detected.")
            return

        # Privacy: dictated content stays out of INFO logs (sizes only)
        logger.info(f"Transcribed ({minutes:.2f} min, {len(text)} chars)")
        # Handle Unicode safely for console output
        try:
            print(f"Transcribed: {text}")
        except UnicodeEncodeError:
            print(f"Transcribed: [contains special characters, {len(text)} chars]")

        # Enhance with GPT if enabled (with retries)
        if self._settings.enhance_text and self._enhancer:
            self._controller.job_set_state("enhancing")
            app_label = context.app_label if context else None
            for attempt in range(MAX_RETRIES):
                try:
                    enhanced = self._enhancer.enhance(
                        text,
                        language=self._settings.language,
                        app_context=app_label,
                    )
                    if enhanced != text:
                        logger.info(f"Enhanced ({len(enhanced)} chars)")
                        try:
                            print(f"Enhanced: {enhanced}")
                        except UnicodeEncodeError:
                            print(f"Enhanced: [contains special characters, {len(enhanced)} chars]")
                        text = enhanced
                    break
                except EnhancementError as e:
                    if not e.retryable:
                        logger.error(f"Enhancement failed (not retrying), using original: {e}")
                        print(f"Enhancement failed: {e}. Using original text.")
                        break
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAYS[attempt]
                        logger.warning(f"Enhancement failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                        print(f"Enhancement failed, retrying in {delay}s... ({e})")
                        time.sleep(delay)
                    else:
                        logger.error(f"Enhancement failed after {MAX_RETRIES} attempts, using original")
                        print(f"Enhancement failed after {MAX_RETRIES} attempts, using original text")
                        # Continue with original text

        # Type the text (serialized: concurrent dictations must not interleave)
        with self._typing_lock:
            self._controller.job_set_state("typing")
            time.sleep(0.1)  # Small delay before typing

            # Stop watching the previous dictation BEFORE our own paste hits
            # the clipboard, so Ditado can't mistake itself for a user edit
            # and poison the vocabulary with a self-"correction"
            self._correction_detector.stop_monitoring()

            success = self._typer.type_text(text)
            if not success:
                # Both injection paths already failed inside type_text — leave
                # the text on the clipboard and TELL the user (the old
                # "fallback" silently repeated the exact same clipboard path)
                if self._typer.copy_to_clipboard(text):
                    self._tray.show_notification(
                        "Ditado",
                        "Couldn't type into this app — text copied to clipboard. "
                        "Press Ctrl+V to paste.",
                    )
                else:
                    self._tray.show_notification(
                        "Ditado Error",
                        "Couldn't type or copy the text. "
                        "You can copy it from the dashboard history.",
                    )

            # Remember the tail of this dictation to prime Whisper next time
            self._last_dictation = text

            # Notify correction detector that text was inserted
            # (starts monitoring clipboard for corrections)
            self._correction_detector.text_inserted(text)

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

        # Atualiza o histórico no dashboard web
        self._dashboard.notify_history_changed()

        logger.info(f"Dictation complete ({minutes:.2f} min)")
        print(f"Done. ({minutes:.2f} min)")

    def _build_whisper_prompt(self) -> Optional[str]:
        """Build a Whisper `prompt` to bias acoustic decoding.

        Combines (in priority order):
          - User's custom vocabulary (preferred spellings, names, technical terms)
          - Tail of the previous dictation (helps continuity & style)

        Whisper hard-caps the prompt at ~224 tokens, so we keep this compact.
        """
        parts: list[str] = []

        vocab_terms = self._vocabulary.get_terms_for_whisper_prompt(max_chars=400)
        if vocab_terms:
            parts.append(vocab_terms)

        if self._last_dictation:
            # Keep ~200 trailing chars - long enough for context, short enough for budget
            tail = self._last_dictation[-200:]
            parts.append(tail)

        if not parts:
            return None

        return " ".join(parts)

    def _on_correction_detected(self, correction: DetectedCorrection) -> None:
        """Handle detected correction from user edit."""
        logger.debug(f"Correction detected: '{correction.original}' -> '{correction.corrected}'")

        # O popup é auto-hospedado (thread Tk próprio) — chamada direta
        self._correction_popup.show(correction.original, correction.corrected)

    def _on_correction_accepted(self, wrong: str, correct: str) -> None:
        """Handle user accepting a correction."""
        self._vocabulary.add_correction(wrong, correct)
        logger.info("Correction added to dictionary")
        logger.debug(f"Correction: '{wrong}' -> '{correct}'")

        # Show confirmation
        self._tray.show_notification(
            "Ditado",
            f"Adicionado ao dicionário: {wrong} → {correct}"
        )

    def _on_correction_rejected(self, wrong: str, correct: str) -> None:
        """Handle user rejecting a correction."""
        logger.debug(f"Correction rejected: '{wrong}' -> '{correct}'")
