"""Vocabulary dictionary management for Ditado."""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime
import threading

from ..utils.logger import get_logger

logger = get_logger("vocabulary")


@dataclass
class CorrectionEntry:
    """A single correction entry in the dictionary."""
    wrong: str
    correct: str
    count: int = 1  # Number of times this correction was used
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class VocabularyData:
    """Data structure for vocabulary storage."""
    # Corrections: wrong word -> correct word
    corrections: Dict[str, CorrectionEntry] = field(default_factory=dict)
    # Context terms: words to preserve exactly (technical terms, names)
    context_terms: List[str] = field(default_factory=list)
    # Statistics
    total_corrections_applied: int = 0


class VocabularyDictionary:
    """Manages the user's personal vocabulary dictionary."""

    def __init__(self, config_path: Optional[Path] = None):
        self._path = config_path or self._get_default_path()
        self._lock = threading.Lock()
        self._data = self._load()

    @staticmethod
    def _get_default_path() -> Path:
        """Get the default vocabulary file path."""
        app_data = Path.home() / ".ditado"
        app_data.mkdir(exist_ok=True)
        return app_data / "vocabulary.json"

    def _load(self) -> VocabularyData:
        """Load vocabulary from file."""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Parse corrections into CorrectionEntry objects
                corrections = {}
                for wrong, entry in data.get("corrections", {}).items():
                    if isinstance(entry, dict):
                        corrections[wrong.lower()] = CorrectionEntry(**entry)
                    else:
                        # Legacy format: just the correct word
                        corrections[wrong.lower()] = CorrectionEntry(
                            wrong=wrong,
                            correct=entry
                        )

                return VocabularyData(
                    corrections=corrections,
                    context_terms=data.get("context_terms", []),
                    total_corrections_applied=data.get("total_corrections_applied", 0)
                )
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Error loading vocabulary: {e}")

        return VocabularyData()

    def _save(self) -> None:
        """Save vocabulary to file."""
        with self._lock:
            data = {
                "corrections": {
                    wrong: asdict(entry)
                    for wrong, entry in self._data.corrections.items()
                },
                "context_terms": self._data.context_terms,
                "total_corrections_applied": self._data.total_corrections_applied
            }

            self._path.parent.mkdir(exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def add_correction(self, wrong: str, correct: str) -> bool:
        """
        Add a correction to the dictionary.

        Args:
            wrong: The incorrectly transcribed word
            correct: The correct word

        Returns:
            True if added, False if already exists with same correction
        """
        wrong_lower = wrong.lower().strip()
        correct = correct.strip()

        if not wrong_lower or not correct:
            return False

        # Don't add if they're the same
        if wrong_lower == correct.lower():
            return False

        with self._lock:
            if wrong_lower in self._data.corrections:
                existing = self._data.corrections[wrong_lower]
                if existing.correct == correct:
                    # Same correction, just update count
                    existing.count += 1
                    existing.last_used = datetime.now().isoformat()
                    self._save()
                    return False
                else:
                    # Different correction, update it
                    existing.correct = correct
                    existing.count += 1
                    existing.last_used = datetime.now().isoformat()
            else:
                # New correction
                self._data.corrections[wrong_lower] = CorrectionEntry(
                    wrong=wrong,
                    correct=correct
                )

            logger.info(f"Added correction: '{wrong}' -> '{correct}'")
            self._save()
            return True

    def remove_correction(self, wrong: str) -> bool:
        """Remove a correction from the dictionary."""
        wrong_lower = wrong.lower().strip()

        with self._lock:
            if wrong_lower in self._data.corrections:
                del self._data.corrections[wrong_lower]
                self._save()
                logger.info(f"Removed correction for: '{wrong}'")
                return True
        return False

    def get_correction(self, word: str) -> Optional[str]:
        """Get the correction for a word if it exists."""
        word_lower = word.lower().strip()
        entry = self._data.corrections.get(word_lower)
        return entry.correct if entry else None

    def apply_corrections(self, text: str) -> str:
        """
        Apply all corrections to a text.

        Args:
            text: The text to correct

        Returns:
            Text with corrections applied
        """
        if not self._data.corrections:
            return text

        corrected = text
        corrections_made = 0

        for wrong, entry in self._data.corrections.items():
            # Use word boundaries for matching
            pattern = re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE)

            def replace_match(match):
                nonlocal corrections_made
                original = match.group(0)
                # Preserve case of first letter
                if original[0].isupper():
                    replacement = entry.correct[0].upper() + entry.correct[1:]
                else:
                    replacement = entry.correct
                corrections_made += 1
                return replacement

            corrected = pattern.sub(replace_match, corrected)

        if corrections_made > 0:
            with self._lock:
                self._data.total_corrections_applied += corrections_made
                self._save()
            logger.debug(f"Applied {corrections_made} corrections to text")

        return corrected

    def add_context_term(self, term: str) -> bool:
        """Add a term to preserve exactly (technical term, name, etc.)."""
        term = term.strip()
        if not term:
            return False

        with self._lock:
            if term not in self._data.context_terms:
                self._data.context_terms.append(term)
                self._save()
                logger.info(f"Added context term: '{term}'")
                return True
        return False

    def remove_context_term(self, term: str) -> bool:
        """Remove a context term."""
        term = term.strip()
        with self._lock:
            if term in self._data.context_terms:
                self._data.context_terms.remove(term)
                self._save()
                return True
        return False

    def get_context_terms(self) -> List[str]:
        """Get all context terms."""
        return list(self._data.context_terms)

    def get_all_corrections(self) -> Dict[str, str]:
        """Get all corrections as a simple dict."""
        return {
            entry.wrong: entry.correct
            for entry in self._data.corrections.values()
        }

    def get_corrections_for_prompt(self) -> str:
        """Get corrections formatted for GPT prompt."""
        if not self._data.corrections and not self._data.context_terms:
            return ""

        lines = []

        if self._data.corrections:
            lines.append("Custom vocabulary corrections (apply these):")
            for entry in sorted(
                self._data.corrections.values(),
                key=lambda e: e.count,
                reverse=True
            )[:20]:  # Top 20 most used
                lines.append(f"  - \"{entry.wrong}\" should be \"{entry.correct}\"")

        if self._data.context_terms:
            lines.append("\nTechnical terms to preserve exactly:")
            lines.append(f"  {', '.join(self._data.context_terms[:30])}")  # Top 30

        return "\n".join(lines)

    def get_terms_for_whisper_prompt(self, max_chars: int = 400) -> str:
        """Return a compact list of vocabulary terms for the Whisper `prompt` parameter.

        Whisper biases decoding toward the spelling of words it sees in the prompt.
        We list the user's preferred spellings (the `correct` side of corrections,
        plus all context terms), most-used first, capped to roughly `max_chars`.
        """
        terms: list[str] = []
        seen = set()

        # Most-used corrections first - we want Whisper to recognise the *correct* form
        for entry in sorted(
            self._data.corrections.values(),
            key=lambda e: e.count,
            reverse=True,
        ):
            term = entry.correct.strip()
            key = term.lower()
            if term and key not in seen:
                terms.append(term)
                seen.add(key)

        # Then context terms
        for term in self._data.context_terms:
            term = term.strip()
            key = term.lower()
            if term and key not in seen:
                terms.append(term)
                seen.add(key)

        if not terms:
            return ""

        # Pack into a comma-separated list, respecting char budget
        out_parts: list[str] = []
        used = 0
        for t in terms:
            piece = t if not out_parts else f", {t}"
            if used + len(piece) > max_chars:
                break
            out_parts.append(piece)
            used += len(piece)

        return "".join(out_parts)

    def get_stats(self) -> dict:
        """Get vocabulary statistics."""
        return {
            "total_corrections": len(self._data.corrections),
            "total_context_terms": len(self._data.context_terms),
            "total_corrections_applied": self._data.total_corrections_applied
        }


# Singleton instance
_dictionary_instance: Optional[VocabularyDictionary] = None


def get_dictionary() -> VocabularyDictionary:
    """Get the global vocabulary dictionary instance."""
    global _dictionary_instance
    if _dictionary_instance is None:
        _dictionary_instance = VocabularyDictionary()
    return _dictionary_instance
