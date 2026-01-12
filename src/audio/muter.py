"""System audio muting for Ditado."""

import threading
from typing import Optional

from ..utils.logger import get_logger

logger = get_logger("muter")

# pycaw imports - Windows-specific
try:
    from pycaw.pycaw import IAudioEndpointVolume, IMMDeviceEnumerator, EDataFlow, ERole
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL, CoCreateInstance, CLSCTX_INPROC_SERVER, GUID
    import pythoncom
    PYCAW_AVAILABLE = True
    # CLSID for the MMDeviceEnumerator COM object
    CLSID_MMDeviceEnumerator = GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')
except ImportError:
    PYCAW_AVAILABLE = False
    logger.warning("pycaw not available - system audio muting disabled")


class AudioMuter:
    """Controls system audio muting during recording.

    This class provides thread-safe muting/unmuting of system audio,
    preserving the original mute state so it can be properly restored.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._was_muted: Optional[bool] = None  # Original mute state
        self._is_muted_by_us = False  # Track if WE muted the audio
        self._com_initialized = False  # Track COM initialization state
        self._volume_interface = None  # Cached volume interface

    def _init_com(self) -> bool:
        """Initialize COM for this thread if not already done."""
        if not PYCAW_AVAILABLE:
            return False

        if not self._com_initialized:
            try:
                pythoncom.CoInitialize()
                self._com_initialized = True
            except Exception as e:
                logger.error(f"Failed to initialize COM: {e}")
                return False
        return True

    def _get_volume_interface(self):
        """Get the Windows audio endpoint volume interface (cached)."""
        if not PYCAW_AVAILABLE:
            return None

        # Return cached interface if available
        if self._volume_interface is not None:
            return self._volume_interface

        try:
            # Initialize COM for this thread
            if not self._init_com():
                return None

            # Create the device enumerator
            enumerator = CoCreateInstance(
                CLSID_MMDeviceEnumerator,
                IMMDeviceEnumerator,
                CLSCTX_INPROC_SERVER
            )

            # Get the default audio render device (speakers)
            device = enumerator.GetDefaultAudioEndpoint(
                EDataFlow.eRender.value,
                ERole.eMultimedia.value
            )

            # Activate the volume control interface
            interface = device.Activate(
                IAudioEndpointVolume._iid_,
                CLSCTX_ALL,
                None
            )
            self._volume_interface = cast(interface, POINTER(IAudioEndpointVolume))
            return self._volume_interface
        except Exception as e:
            logger.error(f"Failed to get audio interface: {e}")
            return None

    def cleanup(self) -> None:
        """Clean up COM resources. Call this when done with the muter."""
        with self._lock:
            self._volume_interface = None
            if self._com_initialized and PYCAW_AVAILABLE:
                try:
                    pythoncom.CoUninitialize()
                    self._com_initialized = False
                    logger.debug("COM uninitialized")
                except Exception as e:
                    logger.error(f"Failed to uninitialize COM: {e}")

    def mute(self) -> bool:
        """Mute system audio, storing the original state.

        Returns:
            True if muting succeeded or was already muted, False on error.
        """
        with self._lock:
            if not PYCAW_AVAILABLE:
                print("[MUTER] pycaw not available")
                return False

            try:
                volume = self._get_volume_interface()
                if not volume:
                    print("[MUTER] Failed to get volume interface")
                    return False

                # Store original mute state
                self._was_muted = bool(volume.GetMute())
                print(f"[MUTER] Original mute state: {self._was_muted}")

                # Only mute if not already muted
                if not self._was_muted:
                    volume.SetMute(1, None)
                    self._is_muted_by_us = True
                    print("[MUTER] System audio MUTED")
                    logger.debug("System audio muted")
                else:
                    print("[MUTER] System was already muted, skipping")
                    logger.debug("System audio was already muted")

                return True

            except Exception as e:
                print(f"[MUTER] Exception: {e}")
                logger.error(f"Failed to mute system audio: {e}")
                self._was_muted = None
                self._is_muted_by_us = False
                return False

    def restore(self) -> bool:
        """Restore system audio to its original state.

        Returns:
            True if restoration succeeded, False on error.
        """
        with self._lock:
            if not PYCAW_AVAILABLE:
                return False

            # Only restore if we were the ones who muted
            if not self._is_muted_by_us:
                logger.debug("Audio not muted by us, skipping restore")
                return True

            try:
                volume = self._get_volume_interface()
                if not volume:
                    return False

                # Restore to original state (unmute only if it wasn't muted before)
                if self._was_muted is False:
                    volume.SetMute(0, None)
                    logger.debug("System audio restored (unmuted)")

                self._is_muted_by_us = False
                self._was_muted = None
                return True

            except Exception as e:
                logger.error(f"Failed to restore system audio: {e}")
                return False

    def force_unmute(self) -> bool:
        """Force unmute system audio (for cleanup/exit scenarios).

        This should be called during app shutdown to ensure audio
        is never left muted if the app crashes or exits unexpectedly.

        Returns:
            True if unmuting succeeded, False on error.
        """
        with self._lock:
            if not PYCAW_AVAILABLE:
                return False

            # Only force unmute if we muted it
            if not self._is_muted_by_us:
                return True

            try:
                volume = self._get_volume_interface()
                if not volume:
                    return False

                volume.SetMute(0, None)
                self._is_muted_by_us = False
                self._was_muted = None
                logger.debug("System audio force unmuted")
                return True

            except Exception as e:
                logger.error(f"Failed to force unmute: {e}")
                return False
