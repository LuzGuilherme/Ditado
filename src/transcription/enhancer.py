"""GPT text enhancement module for Ditado."""

from typing import Optional
from openai import OpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError
import httpx

from ..utils.logger import get_logger
from ..vocabulary.dictionary import VocabularyDictionary, get_dictionary

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
8. If the input is very short (1-3 words), return it unchanged unless there's an obvious typo

LIST FORMATTING - Automatically format enumerations as structured lists:
- When the speaker uses ordinal markers (first/segundo, second/segundo, third/terceiro, etc.), format as a numbered list
- When the speaker uses "point one/ponto um", "point two/ponto dois", etc., format as a numbered list
- When the speaker uses "bullet", "dash", "item", or similar markers, format as a bullet list using "- "
- When listing multiple items with "and/e" or commas after an introductory phrase, consider formatting as a list
- Add a colon after the introductory phrase and place each item on its own line
- Preserve the original item content, just restructure the format

Examples:
- "I need to buy first apples second bananas third oranges" → "I need to buy:\n1. Apples\n2. Bananas\n3. Oranges"
- "preciso de fazer primeiro isto segundo aquilo terceiro outra coisa" → "Preciso de fazer:\n1. Isto\n2. Aquilo\n3. Outra coisa"
- "the main points are bullet improve performance bullet fix bugs bullet add tests" → "The main points are:\n- Improve performance\n- Fix bugs\n- Add tests"
- "quero três coisas maçãs bananas e laranjas" → "Quero três coisas:\n- Maçãs\n- Bananas\n- Laranjas"

Only apply list formatting when there's a clear enumeration pattern. Don't force lists on regular sentences."""

    PORTUGUESE_PROMPT = """

IMPORTANT - European Portuguese:
- Use European Portuguese spelling and vocabulary, NOT Brazilian Portuguese
- Use "tu" forms (fazes, tens, vais) instead of "você" forms
- Use mesoclisis when appropriate (dar-te-ei, fá-lo-ia)
- Use European vocabulary: "autocarro" not "ônibus", "telemóvel" not "celular", "pequeno-almoço" not "café da manhã", "casa de banho" not "banheiro"
- Use European spelling: "facto" not "fato", "acção" not "ação" (unless new orthographic agreement is used)
- Preserve the speaker's regional expressions and idioms"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        vocabulary: Optional[VocabularyDictionary] = None
    ):
        self.client = OpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(30.0, connect=10.0)  # 30s total, 10s connect
        )
        self.model = model
        self._vocabulary = vocabulary or get_dictionary()

    def _get_system_prompt(self, language: str = None) -> str:
        """Get the system prompt with language-specific additions and vocabulary."""
        prompt = self.SYSTEM_PROMPT

        # Use European Portuguese for any Portuguese variant
        if language and language.startswith("pt"):
            prompt += self.PORTUGUESE_PROMPT

        # Add custom vocabulary if available
        vocab_prompt = self._vocabulary.get_corrections_for_prompt()
        if vocab_prompt:
            prompt += f"\n\nUSER VOCABULARY:\n{vocab_prompt}"

        return prompt

    def enhance(self, text: str, language: str = None) -> str:
        """
        Enhance/clean up transcribed text.

        Args:
            text: Raw transcribed text
            language: Language code (e.g., 'pt-PT', 'pt-BR') for regional variants

        Returns:
            Enhanced text

        Raises:
            EnhancementError: If enhancement fails
        """
        # Apply vocabulary corrections first (pre-GPT)
        text = self._vocabulary.apply_corrections(text)

        # Skip very short text (single words only)
        if len(text.split()) <= 1:
            return text

        try:
            system_prompt = self._get_system_prompt(language)
            logger.debug(f"Calling GPT API for enhancement with model {self.model}, language={language}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                max_tokens=len(text) * 3,  # Allow for expansion (lists add line breaks)
                temperature=0.3,  # Low temperature for consistent output
            )

            enhanced = response.choices[0].message.content.strip()

            # Sanity check: if the response is way longer or shorter, use original
            # Use word count instead of character count since filler word removal
            # can legitimately reduce character count by 40-50%
            # List formatting may add numbering/bullets but shouldn't drastically change word count
            original_words = len(text.split())
            enhanced_words = len(enhanced.split())
            if enhanced_words > original_words * 4 or enhanced_words < original_words * 0.25:
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
