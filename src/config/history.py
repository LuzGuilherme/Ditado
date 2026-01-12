"""Transcription history management for Ditado."""

import json
import uuid
import threading
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional


@dataclass
class TranscriptionHistoryEntry:
    """A single transcription history entry."""
    id: str
    timestamp: str  # ISO format datetime
    text: str
    word_count: int
    duration_seconds: float
    language: str
    enhanced: bool

    @classmethod
    def create(
        cls,
        text: str,
        duration_seconds: float,
        language: str,
        enhanced: bool,
    ) -> "TranscriptionHistoryEntry":
        """Create a new history entry with auto-generated id and timestamp."""
        return cls(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            text=text,
            word_count=len(text.split()) if text else 0,
            duration_seconds=duration_seconds,
            language=language,
            enhanced=enhanced,
        )


@dataclass
class TranscriptionHistory:
    """Manages transcription history with thread-safe operations."""
    entries: List[TranscriptionHistoryEntry] = field(default_factory=list)
    max_entries: int = 100
    store_full_text: bool = True
    _config_path: Optional[Path] = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def get_default_path(cls) -> Path:
        """Get the default history file path."""
        app_data = Path.home() / ".ditado"
        app_data.mkdir(exist_ok=True)
        return app_data / "history.json"

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "TranscriptionHistory":
        """Load history from file or create empty."""
        file_path = path or cls.get_default_path()

        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                entries_data = data.get("entries", [])
                entries = [
                    TranscriptionHistoryEntry(**entry)
                    for entry in entries_data
                ]

                history = cls(
                    entries=entries,
                    max_entries=data.get("max_entries", 100),
                    store_full_text=data.get("store_full_text", True),
                )
                history._config_path = file_path
                return history
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                print(f"Error loading history: {e}. Starting fresh.")

        history = cls()
        history._config_path = file_path
        return history

    def save(self) -> None:
        """Save history to file."""
        with self._lock:
            self._save_unsafe()

    def _save_unsafe(self) -> None:
        """Internal save without lock (caller must hold lock)."""
        path = self._config_path or self.get_default_path()

        data = {
            "entries": [asdict(entry) for entry in self.entries],
            "max_entries": self.max_entries,
            "store_full_text": self.store_full_text,
        }

        path.parent.mkdir(exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add_entry(self, entry: TranscriptionHistoryEntry) -> None:
        """Add a new transcription entry."""
        with self._lock:
            # Apply privacy setting
            if not self.store_full_text:
                entry.text = f"[{entry.word_count} words]"

            # Insert at beginning (most recent first)
            self.entries.insert(0, entry)

            # Enforce max entries
            if len(self.entries) > self.max_entries:
                self.entries = self.entries[:self.max_entries]

            self._save_unsafe()

    def get_recent(self, count: int = 20) -> List[TranscriptionHistoryEntry]:
        """Get the most recent entries (thread-safe copy)."""
        with self._lock:
            return self.entries[:count].copy()

    def clear(self) -> None:
        """Clear all history entries."""
        with self._lock:
            self.entries.clear()
            self._save_unsafe()

    def delete_entry(self, entry_id: str) -> bool:
        """Delete a specific entry by ID."""
        with self._lock:
            for i, entry in enumerate(self.entries):
                if entry.id == entry_id:
                    del self.entries[i]
                    self._save_unsafe()
                    return True
            return False

    def set_privacy_mode(self, store_full_text: bool) -> None:
        """Update privacy setting."""
        with self._lock:
            self.store_full_text = store_full_text
            self._save_unsafe()


def format_relative_time(timestamp: str) -> str:
    """Format timestamp as human-readable relative time."""
    try:
        dt = datetime.fromisoformat(timestamp)
        now = datetime.now()
        diff = now - dt

        seconds = diff.total_seconds()

        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} min ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif dt.date() == now.date():
            return f"Today, {dt.strftime('%I:%M %p')}"
        elif (now.date() - dt.date()).days == 1:
            return f"Yesterday, {dt.strftime('%I:%M %p')}"
        else:
            return dt.strftime("%b %d, %I:%M %p")
    except (ValueError, TypeError):
        return timestamp
