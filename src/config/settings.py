"""Settings management for Ditado."""

import json
from pathlib import Path
from dataclasses import dataclass, field, fields, asdict
from datetime import datetime
from typing import Optional, List
import threading

from ..utils.logger import get_logger
from ..utils.json_store import write_json_atomic, backup_corrupt_file

# Secure credential storage
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

KEYRING_SERVICE = "Ditado"
KEYRING_USERNAME = "api_key"

logger = get_logger("settings")


@dataclass
class UsageStats:
    """Track API usage statistics."""
    total_minutes: float = 0.0
    total_requests: int = 0
    session_minutes: float = 0.0
    session_requests: int = 0
    # Dashboard statistics
    total_words: int = 0
    first_use_date: Optional[str] = None  # ISO format date
    last_use_date: Optional[str] = None   # ISO format date
    active_days: List[str] = field(default_factory=list)  # List of ISO date strings


@dataclass
class Settings:
    """Application settings with persistence."""

    # Hotkey configuration
    hotkey: str = "caps_lock"

    # Language (auto = auto-detect)
    language: str = "pt"

    # UI settings
    indicator_position: str = "top-right"  # top-left, top-right, bottom-left, bottom-right
    indicator_enabled: bool = True

    # Audio settings
    audio_device_index: Optional[int] = None  # None = default device
    max_recording_seconds: int = 300  # 5 minutes default max recording
    auto_stop_recording: bool = True  # Auto-stop when max reached
    mute_system_audio: bool = True  # Mute speakers during recording
    auto_start_on_boot: bool = False  # Start Ditado when Windows boots
    onboarding_dismissed: bool = False  # First-run card skipped by the user

    # API configuration (api_key stored securely via keyring)
    _api_key_cached: str = field(default="", repr=False)
    whisper_model: str = "whisper-1"
    gpt_model: str = "gpt-4o-mini"
    enhance_text: bool = True

    # Sound feedback
    sound_feedback: bool = True

    # Personalization (used in dashboard greeting)
    user_first_name: str = ""

    # Usage statistics
    stats: UsageStats = field(default_factory=UsageStats)

    # Internal
    _config_path: Optional[Path] = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    # Whether the cached key is verifiably stored in the OS keyring
    # (None = not checked yet)
    _keyring_ok: Optional[bool] = field(default=None, repr=False)

    @property
    def api_key(self) -> str:
        """Get API key from secure storage or cache."""
        if self._api_key_cached:
            return self._api_key_cached

        if KEYRING_AVAILABLE:
            try:
                key = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
                if key:
                    self._api_key_cached = key
                    self._keyring_ok = True
                    return key
            except Exception:
                pass

        return self._api_key_cached

    @api_key.setter
    def api_key(self, value: str) -> None:
        """Store API key in secure storage, verifying the write took."""
        self._api_key_cached = value
        self._keyring_ok = None

        if KEYRING_AVAILABLE and value:
            try:
                keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, value)
                # Round-trip check: never assume the backend actually stored it
                self._keyring_ok = (
                    keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME) == value
                )
            except Exception as e:
                self._keyring_ok = False
                logger.error(f"Could not store API key in Windows Credential Manager: {e}")

    def _key_stored_in_keyring(self) -> bool:
        """True when the cached key is verifiably present in the OS keyring."""
        if not KEYRING_AVAILABLE or not self._api_key_cached:
            return False
        if self._keyring_ok is None:
            try:
                self._keyring_ok = (
                    keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
                    == self._api_key_cached
                )
            except Exception:
                self._keyring_ok = False
        return bool(self._keyring_ok)

    @classmethod
    def get_default_config_path(cls) -> Path:
        """Get the default config file path."""
        # Store in user's app data
        app_data = Path.home() / ".ditado"
        app_data.mkdir(exist_ok=True)
        return app_data / "config.json"

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Settings":
        """Load settings from file or create defaults."""
        path = config_path or cls.get_default_config_path()

        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Handle nested stats (drop unknown keys from other versions)
                stats_data = data.pop("stats", {}) or {}
                stats_known = {f.name for f in fields(UsageStats)}
                stats = UsageStats(
                    **{k: v for k, v in stats_data.items() if k in stats_known}
                )

                # Migrate API key from config file to secure storage
                old_api_key = data.pop("api_key", "")

                # Keep only known public fields — an unknown key (e.g. config
                # written by a newer version) must not nuke the whole file
                known = {f.name for f in fields(cls) if not f.name.startswith("_")}
                data = {k: v for k, v in data.items() if k in known}

                settings = cls(**data, stats=stats)
                settings._config_path = path

                # Load API key from secure storage first
                if KEYRING_AVAILABLE:
                    try:
                        secure_key = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
                        if secure_key:
                            settings._api_key_cached = secure_key
                            settings._keyring_ok = True
                    except Exception:
                        pass

                # If no secure key but old key in config, migrate it. save()
                # keeps the key in the file whenever the keyring write could
                # not be verified — the user's key is never silently lost.
                if not settings._api_key_cached and old_api_key:
                    settings.api_key = old_api_key
                    settings.save()

                return settings
            except (json.JSONDecodeError, TypeError) as e:
                backup = backup_corrupt_file(path)
                logger.error(
                    f"Config file corrupt ({e}). Backed up to '{backup}' "
                    "and starting with defaults."
                )

        # Create new settings with defaults
        settings = cls()
        settings._config_path = path
        settings.save()
        return settings

    def save(self) -> None:
        """Save settings to file (API key stored separately in secure storage)."""
        with self._lock:
            path = self._config_path or self.get_default_config_path()

            # Convert to dict, excluding internal fields and API key
            # API key is stored securely via keyring, not in config file
            data = {
                "hotkey": self.hotkey,
                "language": self.language,
                "indicator_position": self.indicator_position,
                "indicator_enabled": self.indicator_enabled,
                "audio_device_index": self.audio_device_index,
                "max_recording_seconds": self.max_recording_seconds,
                "auto_stop_recording": self.auto_stop_recording,
                "mute_system_audio": self.mute_system_audio,
                "auto_start_on_boot": self.auto_start_on_boot,
                "whisper_model": self.whisper_model,
                "gpt_model": self.gpt_model,
                "enhance_text": self.enhance_text,
                "sound_feedback": self.sound_feedback,
                "onboarding_dismissed": self.onboarding_dismissed,
                "user_first_name": self.user_first_name,
                "stats": asdict(self.stats),
            }

            # Fallback: if the key is NOT verifiably in the OS keyring, keep
            # it in the config file — less secure, but never silently lost.
            if self._api_key_cached and not self._key_stored_in_keyring():
                data["api_key"] = self._api_key_cached
                logger.warning(
                    "Keyring unavailable — API key stored in config.json as fallback"
                )

            write_json_atomic(path, data)

    def add_usage(self, minutes: float, word_count: int = 0) -> None:
        """Add usage statistics."""
        today = datetime.now().date().isoformat()

        with self._lock:
            self.stats.total_minutes += minutes
            self.stats.total_requests += 1
            self.stats.session_minutes += minutes
            self.stats.session_requests += 1
            self.stats.total_words += word_count

            # Track first use date
            if self.stats.first_use_date is None:
                self.stats.first_use_date = today

            # Track last use date
            self.stats.last_use_date = today

            # Track active days (deduplicated)
            if today not in self.stats.active_days:
                self.stats.active_days.append(today)

        self.save()

    def reset_session_stats(self) -> None:
        """Reset session statistics."""
        with self._lock:
            self.stats.session_minutes = 0.0
            self.stats.session_requests = 0

    def get_estimated_cost(self) -> dict:
        """Calculate estimated API costs."""
        # Whisper: $0.006 per minute
        # GPT-4o-mini: ~$0.00015 per 1K input tokens (roughly $0.0003 per request avg)
        whisper_cost = self.stats.total_minutes * 0.006
        gpt_cost = self.stats.total_requests * 0.0003 if self.enhance_text else 0

        return {
            "whisper": round(whisper_cost, 4),
            "gpt": round(gpt_cost, 4),
            "total": round(whisper_cost + gpt_cost, 4),
        }

    def is_configured(self) -> bool:
        """Check if the app is properly configured."""
        return bool(self.api_key)

    def get_weeks_active(self) -> int:
        """Calculate number of weeks with at least one transcription."""
        if not self.stats.active_days:
            return 0

        weeks = set()
        for date_str in self.stats.active_days:
            try:
                date = datetime.fromisoformat(date_str)
                week_key = date.isocalendar()[:2]  # (year, week_number)
                weeks.add(week_key)
            except (ValueError, TypeError):
                continue

        return len(weeks)

    def get_estimated_wpm(self) -> int:
        """Estimate words per minute based on total words and recording time."""
        if self.stats.total_minutes == 0:
            return 0
        return round(self.stats.total_words / self.stats.total_minutes)


# Singleton instance
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings.load()
    return _settings_instance
