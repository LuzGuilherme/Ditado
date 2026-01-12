"""Sound feedback for Ditado events using system beeps."""

import winsound
import threading


class SoundPlayer:
    """Plays notification beeps for app events."""

    # Frequency (Hz) and duration (ms) for each sound
    SOUNDS = {
        "start": [(800, 100)],   # Beep on hotkey press
        "end": [(600, 100)],     # Beep on hotkey release
    }

    def __init__(self, enabled: bool = True):
        self._enabled = enabled

    def play(self, sound_name: str) -> None:
        """Play a sound asynchronously."""
        if not self._enabled:
            return

        beeps = self.SOUNDS.get(sound_name)
        if beeps:
            threading.Thread(target=self._play_beeps, args=(beeps,), daemon=True).start()

    def _play_beeps(self, beeps: list) -> None:
        """Play a sequence of beeps."""
        for freq, duration in beeps:
            winsound.Beep(freq, duration)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable sound feedback."""
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        """Return whether sound feedback is enabled."""
        return self._enabled
