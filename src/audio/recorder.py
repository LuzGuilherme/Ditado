"""Audio recording module for Ditado."""

import io
import wave
import threading
from typing import Optional, Callable
import numpy as np
import sounddevice as sd

from ..utils.logger import get_logger

logger = get_logger("recorder")


class AudioRecordingError(Exception):
    """Custom exception for audio recording errors."""
    pass


class AudioRecorder:
    """Records audio from the microphone."""

    SAMPLE_RATE = 16000  # Whisper expects 16kHz
    CHANNELS = 1  # Mono
    DTYPE = np.int16
    MIN_AUDIO_LEVEL = 0.001  # Minimum average level to consider non-silent

    def __init__(self, device_index: Optional[int] = None):
        """
        Initialize the audio recorder.

        Args:
            device_index: Specific audio device to use, or None for default
        """
        self._device_index = device_index
        self._recording = False
        self._audio_data: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()
        self._on_level_callback: Optional[Callable[[float], None]] = None
        self._error: Optional[str] = None

    def set_device(self, device_index: Optional[int]) -> None:
        """Set the audio input device."""
        self._device_index = device_index

    def set_level_callback(self, callback: Callable[[float], None]) -> None:
        """Set callback for audio level updates (for UI visualization)."""
        self._on_level_callback = callback

    def get_last_error(self) -> Optional[str]:
        """Get the last error message, if any."""
        return self._error

    def start(self) -> bool:
        """
        Start recording audio.

        Returns:
            True if recording started successfully, False otherwise
        """
        with self._lock:
            if self._recording:
                return True

            self._audio_data = []
            self._error = None

            try:
                self._stream = sd.InputStream(
                    samplerate=self.SAMPLE_RATE,
                    channels=self.CHANNELS,
                    dtype=self.DTYPE,
                    device=self._device_index,
                    callback=self._audio_callback,
                )
                self._stream.start()
                self._recording = True
                return True
            except sd.PortAudioError as e:
                self._error = f"Audio device error: {e}"
                logger.error(self._error)
                return False
            except Exception as e:
                self._error = f"Failed to start recording: {e}"
                logger.error(self._error)
                return False

    def stop(self) -> Optional[bytes]:
        """
        Stop recording and return WAV audio data.

        Returns:
            WAV audio bytes, or None if recording was too short, silent, or failed
        """
        with self._lock:
            if not self._recording:
                return None

            self._recording = False

            try:
                if self._stream:
                    self._stream.stop()
                    self._stream.close()
                    self._stream = None
            except Exception as e:
                self._error = f"Error stopping stream: {e}"
                logger.error(self._error)

            if not self._audio_data:
                self._error = "No audio data captured"
                return None

            # Combine all audio chunks
            audio = np.concatenate(self._audio_data)

            # Check minimum duration (0.5 seconds)
            min_samples = int(0.5 * self.SAMPLE_RATE)
            if len(audio) < min_samples:
                self._error = "Recording too short"
                return None

            # Check if audio is essentially silent
            avg_level = np.abs(audio).mean() / 32768.0
            if avg_level < self.MIN_AUDIO_LEVEL:
                self._error = "Recording appears to be silent"
                return None

            # Convert to WAV format
            return self._to_wav(audio)

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording

    def get_duration(self) -> float:
        """Get current recording duration in seconds."""
        with self._lock:
            if not self._audio_data:
                return 0.0
            total_samples = sum(len(chunk) for chunk in self._audio_data)
            return total_samples / self.SAMPLE_RATE

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """Callback for audio stream."""
        if status:
            logger.debug(f"Audio callback status: {status}")

        # Store audio data
        self._audio_data.append(indata.copy())

        # Calculate audio level for visualization
        if self._on_level_callback:
            level = np.abs(indata).mean() / 32768.0  # Normalize to 0-1
            self._on_level_callback(level)

    def _to_wav(self, audio: np.ndarray) -> bytes:
        """Convert numpy array to WAV bytes."""
        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(self.CHANNELS)
            wav_file.setsampwidth(2)  # 16-bit = 2 bytes
            wav_file.setframerate(self.SAMPLE_RATE)
            wav_file.writeframes(audio.tobytes())

        buffer.seek(0)
        return buffer.read()


def list_audio_devices() -> list[dict]:
    """List available audio input devices."""
    devices = []
    for i, device in enumerate(sd.query_devices()):
        if device["max_input_channels"] > 0:
            devices.append({
                "index": i,
                "name": device["name"],
                "channels": device["max_input_channels"],
                "sample_rate": device["default_samplerate"],
            })
    return devices


def get_default_input_device() -> Optional[dict]:
    """Get the default input device."""
    try:
        device_id = sd.default.device[0]
        if device_id is not None:
            device = sd.query_devices(device_id)
            return {
                "index": device_id,
                "name": device["name"],
                "channels": device["max_input_channels"],
                "sample_rate": device["default_samplerate"],
            }
    except Exception:
        pass
    return None


def check_audio_available() -> tuple[bool, str]:
    """
    Check if audio recording is available.

    Returns:
        Tuple of (is_available, error_message)
    """
    try:
        devices = list_audio_devices()
        if not devices:
            return False, "No audio input devices found. Please connect a microphone."

        default = get_default_input_device()
        if not default:
            return False, "No default audio input device set."

        return True, ""
    except sd.PortAudioError as e:
        return False, f"Audio system error: {e}"
    except Exception as e:
        return False, f"Failed to check audio devices: {e}"
