"""GPT text enhancement module for Ditado."""

from openai import OpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError
import httpx

from ..utils.logger import get_logger

logger = get_logger("enhancer")


class EnhancementError(Exception):
    """Custom exception for enhancement errors."""
    pass


class TextEnhancer:
    """Enhance transcribed text using GPT."""

    SYSTEM_PROMPT = """You are a text cleanup assistant. Your job is to clean up dictated text while preserving the speaker's meaning and intent.

Rules:
1. Remove filler words (um, uh, like, you know, I mean, so, basically, actually, literally)
2. Fix obvious grammar mistakes
3. Add proper punctuation and capitalization
4. Keep the text natural - don't make it overly formal
5. Preserve technical terms, names, and intentional informal language
6. If the text is already clean, return it unchanged
7. ONLY return the cleaned text - no explanations or commentary
8. If the input is very short (1-3 words), return it unchanged unless there's an obvious typo"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = OpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(30.0, connect=10.0)  # 30s total, 10s connect
        )
        self.model = model

    def enhance(self, text: str) -> str:
        """
        Enhance/clean up transcribed text.

        Args:
            text: Raw transcribed text

        Returns:
            Enhanced text

        Raises:
            EnhancementError: If enhancement fails
        """
        # Skip very short text (single words only)
        if len(text.split()) <= 1:
            return text

        try:
            logger.debug(f"Calling GPT API for enhancement with model {self.model}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                max_tokens=len(text) * 2,  # Allow for some expansion
                temperature=0.3,  # Low temperature for consistent output
            )

            enhanced = response.choices[0].message.content.strip()

            # Sanity check: if the response is way longer or shorter, use original
            # Use word count instead of character count since filler word removal
            # can legitimately reduce character count by 40-50%
            original_words = len(text.split())
            enhanced_words = len(enhanced.split())
            if enhanced_words > original_words * 3 or enhanced_words < original_words * 0.3:
                logger.debug("Enhancement result rejected (word count mismatch)")
                return text

            logger.debug(f"Enhancement successful: {original_words} -> {enhanced_words} words")
            return enhanced

        except AuthenticationError as e:
            logger.error("Authentication failed - invalid API key")
            raise EnhancementError("Invalid API key. Please check your settings.") from e
        except RateLimitError as e:
            logger.warning("Rate limit exceeded")
            raise EnhancementError("Rate limit exceeded. Please wait and try again.") from e
        except APIConnectionError as e:
            logger.error(f"Network error: {e}")
            raise EnhancementError("Network error. Please check your connection.") from e
        except APIError as e:
            logger.error(f"API error: {e}")
            raise EnhancementError(f"API error: {str(e)}") from e
        except Exception as e:
            logger.error(f"Enhancement failed: {e}")
            raise EnhancementError(f"Enhancement failed: {str(e)}") from e

    def update_api_key(self, api_key: str) -> None:
        """Update the API key."""
        self.client = OpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(30.0, connect=10.0)
        )
