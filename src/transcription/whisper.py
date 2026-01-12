"""Whisper API transcription module for Ditado."""

import io
from typing import Optional
from openai import OpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError
import httpx

from ..utils.logger import get_logger

logger = get_logger("whisper")


class TranscriptionError(Exception):
    """Custom exception for transcription errors."""
    pass


class WhisperTranscriber:
    """Transcribe audio using OpenAI's Whisper API."""

    def __init__(self, api_key: str, model: str = "whisper-1"):
        self.client = OpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(60.0, connect=10.0)  # 60s total, 10s connect
        )
        self.model = model

    def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
    ) -> tuple[str, float]:
        """
        Transcribe audio data to text.

        Args:
            audio_data: WAV audio bytes
            language: Language code (e.g., 'en', 'pt') or None for auto-detect

        Returns:
            Tuple of (transcribed text, duration in minutes)

        Raises:
            TranscriptionError: If transcription fails
        """
        # Create a file-like object from the audio bytes
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "recording.wav"

        # Prepare transcription parameters
        params = {
            "model": self.model,
            "file": audio_file,
            "response_format": "verbose_json",
        }

        # Only set language if not auto-detect
        if language and language != "auto":
            params["language"] = language

        try:
            # Call Whisper API
            logger.debug(f"Calling Whisper API with model {self.model}")
            response = self.client.audio.transcriptions.create(**params)

            # Extract text and duration
            text = response.text.strip()
            duration_minutes = getattr(response, "duration", 0) / 60.0

            logger.debug(f"Transcription successful: {len(text)} chars, {duration_minutes:.2f} min")
            return text, duration_minutes

        except AuthenticationError as e:
            logger.error("Authentication failed - invalid API key")
            raise TranscriptionError("Invalid API key. Please check your settings.") from e
        except RateLimitError as e:
            logger.warning("Rate limit exceeded")
            raise TranscriptionError("Rate limit exceeded. Please wait and try again.") from e
        except APIConnectionError as e:
            logger.error(f"Network error: {e}")
            raise TranscriptionError("Network error. Please check your connection.") from e
        except APIError as e:
            logger.error(f"API error: {e}")
            raise TranscriptionError(f"API error: {str(e)}") from e
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise TranscriptionError(f"Transcription failed: {str(e)}") from e

    def update_api_key(self, api_key: str) -> None:
        """Update the API key."""
        self.client = OpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(60.0, connect=10.0)
        )


# Language codes supported by Whisper
SUPPORTED_LANGUAGES = {
    "auto": "Auto-detect",
    "en": "English",
    "pt": "Portuguese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "ms": "Malay",
    "tl": "Tagalog",
    "uk": "Ukrainian",
    "cs": "Czech",
    "ro": "Romanian",
    "hu": "Hungarian",
    "el": "Greek",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "no": "Norwegian",
    "he": "Hebrew",
    "bg": "Bulgarian",
    "hr": "Croatian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "et": "Estonian",
    "ca": "Catalan",
    "gl": "Galician",
    "eu": "Basque",
    "cy": "Welsh",
    "af": "Afrikaans",
    "sw": "Swahili",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "bn": "Bengali",
    "ur": "Urdu",
    "fa": "Persian",
}
