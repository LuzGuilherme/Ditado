"""Recording state controller for Ditado.

Owns the push-to-talk state machine on a single worker thread so that:

- pynput hook callbacks only enqueue events and return immediately —
  heavy work (COM audio muting, PortAudio device open, WAV encoding)
  never runs inside the Windows low-level keyboard hook;
- press / release / auto-stop / tray-toggle can never race each other:
  every state transition happens on the one controller thread;
- the microphone can never be left recording with no owner (the bug
  where a release during background processing was silently dropped);
- the overlay reflects a live recording even while previous dictations
  are still being transcribed in the background.

Processing of finished recordings still happens on separate per-dictation
threads (spawned via ``on_audio_ready``); those threads report back through
``job_set_state`` / ``job_finished``, which are routed through the same
event queue so all state stays single-threaded.
"""

import queue
import threading
import time
from typing import Callable, Optional

from .utils.window_context import WindowContext
from .utils.logger import get_logger

logger = get_logger("controller")


class RecordingController:
    """Single-owner state machine for push-to-talk recording."""

    def __init__(
        self,
        recorder,
        muter,
        sound_player,
        overlay,
        get_settings: Callable[[], object],
        capture_context: Callable[[], Optional[WindowContext]],
        on_audio_ready: Callable[[bytes, float, Optional[WindowContext]], None],
        notify: Callable[[str, str], None],
    ):
        self._recorder = recorder
        self._muter = muter
        self._sound = sound_player
        self._overlay = overlay
        self._get_settings = get_settings
        self._capture_context = capture_context
        self._on_audio_ready = on_audio_ready
        self._notify = notify

        self._events: "queue.Queue[tuple]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None

        # Observador opcional do estado do pipeline (ex.: dashboard web).
        # Recebe: recording | transcribing | enhancing | typing | error | idle
        self.on_state: Optional[Callable[[str], None]] = None

        # State below is owned exclusively by the worker thread.
        self._enabled = True
        self._recording = False
        self._jobs = 0
        self._last_job_state = "transcribing"
        self._context: Optional[WindowContext] = None
        self._auto_stop_timer: Optional[threading.Timer] = None

    # ------------------------------------------------ public API (any thread)
    def start(self) -> None:
        """Start the controller worker thread."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name="recording-controller", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Shut down: stops any live recording and restores system audio."""
        if self._thread is None:
            return
        self._events.put(("shutdown",))
        self._thread.join(timeout=timeout)
        self._thread = None

    def on_press(self) -> None:
        """Hotkey pressed (called from the pynput hook thread — must be cheap)."""
        self._events.put(("press",))

    def on_release(self) -> None:
        """Hotkey released (called from the pynput hook thread — must be cheap)."""
        self._events.put(("release",))

    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable dictation. Disabling stops and discards a live recording."""
        self._events.put(("set_enabled", enabled))

    def job_set_state(self, state: str) -> None:
        """A processing thread reports its pipeline state (transcribing/enhancing/typing)."""
        self._events.put(("job_state", state))

    def job_finished(self) -> None:
        """A processing thread finished (success or failure)."""
        self._events.put(("job_done",))

    def is_recording(self) -> bool:
        """Advisory only — state is owned by the worker thread."""
        return self._recording

    # --------------------------------------------------------- worker thread
    def _run(self) -> None:
        while True:
            event = self._events.get()
            kind = event[0]
            try:
                if kind == "shutdown":
                    self._handle_shutdown()
                    return
                elif kind == "press":
                    self._handle_press()
                elif kind == "release":
                    self._handle_stop()
                elif kind == "auto_stop":
                    self._handle_auto_stop()
                elif kind == "set_enabled":
                    self._handle_set_enabled(event[1])
                elif kind == "job_state":
                    self._handle_job_state(event[1])
                elif kind == "job_done":
                    self._handle_job_done()
            except Exception as e:
                logger.exception(f"Controller error handling '{kind}': {e}")
                # Whatever went wrong, never leave the mic open or audio muted.
                self._emergency_reset()

    def _handle_press(self) -> None:
        if self._recording:
            return  # key repeat or duplicate press
        settings = self._get_settings()
        if not self._enabled or not settings.is_configured():
            return

        # Play start sound BEFORE muting so the user can hear it
        self._sound.play("start")

        if settings.mute_system_audio:
            mute_result = self._muter.mute()
            logger.debug(f"System audio mute result: {mute_result}")
            # Small delay so the mute takes effect before recording starts
            time.sleep(0.05)

        # Capture which app the user is dictating into BEFORE our overlay
        # shows (so we don't accidentally pick up our own window).
        self._context = self._capture_context()

        if not self._recorder.start():
            error = self._recorder.get_last_error() or "Failed to start recording"
            logger.error(f"Recording failed: {error}")
            self._notify("Ditado Error", error)
            self._muter.restore()
            self._context = None
            self._refresh_overlay()
            return

        # Only signal "recording" once the stream is actually capturing,
        # so the user doesn't start speaking before the mic is live.
        self._recording = True
        logger.debug("Recording started")
        self._overlay.show()
        self._overlay.set_state("recording")
        self._emit("recording")

        if settings.auto_stop_recording and settings.max_recording_seconds > 0:
            self._auto_stop_timer = threading.Timer(
                settings.max_recording_seconds,
                lambda: self._events.put(("auto_stop",)),
            )
            self._auto_stop_timer.daemon = True
            self._auto_stop_timer.start()
            logger.debug(f"Auto-stop timer set for {settings.max_recording_seconds}s")

    def _handle_auto_stop(self) -> None:
        if not self._recording:
            return  # stale timer (recording already ended)
        settings = self._get_settings()
        logger.info("Auto-stopping recording (limit reached)")
        self._notify(
            "Ditado",
            f"Recording auto-stopped after {settings.max_recording_seconds // 60} min",
        )
        self._handle_stop()

    def _handle_stop(self, discard: bool = False) -> None:
        if self._auto_stop_timer is not None:
            self._auto_stop_timer.cancel()
            self._auto_stop_timer = None

        if not self._recording:
            return  # release with no live recording (e.g. after auto-stop)

        self._recording = False

        # Restore system audio first so the end beep is audible.
        # restore() is a safe no-op when we were not the ones who muted.
        self._muter.restore()
        self._sound.play("end")

        audio_data = self._recorder.stop()
        duration = self._recorder.get_duration()
        context, self._context = self._context, None

        if discard or not audio_data:
            if discard:
                logger.info("Recording discarded")
            else:
                error = self._recorder.get_last_error() or "Recording too short"
                logger.debug(f"Recording ignored: {error}")
            self._refresh_overlay()
            return

        logger.debug(f"Processing audio ({duration:.2f}s)")
        self._jobs += 1
        self._last_job_state = "transcribing"
        self._overlay.set_state("transcribing")
        self._emit("transcribing")
        try:
            self._on_audio_ready(audio_data, duration, context)
        except Exception as e:
            logger.exception(f"Failed to start processing job: {e}")
            self._jobs -= 1
            self._refresh_overlay()

    def _handle_set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if not enabled and self._recording:
            # Disabling mid-recording must never leave the mic open.
            self._handle_stop(discard=True)

    def _handle_job_state(self, state: str) -> None:
        self._last_job_state = state
        # A live recording owns the overlay; job states show only when idle.
        if not self._recording:
            self._overlay.set_state(state)
            self._emit(state)

    def _handle_job_done(self) -> None:
        self._jobs = max(0, self._jobs - 1)
        self._refresh_overlay()

    def _refresh_overlay(self) -> None:
        if self._recording:
            self._overlay.set_state("recording")
            self._emit("recording")
        elif self._jobs > 0:
            self._overlay.set_state(self._last_job_state)
            self._emit(self._last_job_state)
        else:
            self._overlay.hide()
            self._emit("idle")

    def _emit(self, state: str) -> None:
        """Notify the optional state observer; never let it break the machine."""
        cb = self.on_state
        if cb is None:
            return
        try:
            cb(state)
        except Exception as e:
            logger.debug(f"State observer failed: {e}")

    def _handle_shutdown(self) -> None:
        if self._auto_stop_timer is not None:
            self._auto_stop_timer.cancel()
            self._auto_stop_timer = None
        if self._recording:
            self._recording = False
            try:
                self._recorder.stop()
            except Exception:
                pass
        try:
            self._muter.restore()
        except Exception:
            pass

    def _emergency_reset(self) -> None:
        """Best-effort cleanup after an unexpected internal error."""
        try:
            if self._auto_stop_timer is not None:
                self._auto_stop_timer.cancel()
                self._auto_stop_timer = None
            self._recording = False
            self._context = None
            try:
                self._recorder.stop()
            except Exception:
                pass
            self._muter.restore()
            self._refresh_overlay()
        except Exception:
            pass
