"""
agents/prompt_processor.py - Natural Language Query Preprocessing & Speech Wrapping.

Normalizes user intent, validates query boundaries, and guarantees that speech
synthesis directives are properly formatted for parsing by the Void model runtime.
"""

from security.sanitizer import InputSanitizer


class PromptPreprocessor:
    """Preprocesses and normalizes natural language queries for the Void agent."""

    @staticmethod
    def preprocess(query: str) -> str:
        """
        Cleans user query, strips ANSI/control escapes, and formats speech commands
        with exact quoting required for LLM tool extraction.
        """
        if not query:
            return ""

        clean = InputSanitizer.sanitize_string(query, max_length=1000)
        lower = clean.lower()

        # Wrap speech verbs in explicit quotation if not already enclosed
        for verb in ("speak ", "say ", "tell me "):
            if lower.startswith(verb):
                prefix = clean[:len(verb)]
                body = clean[len(verb):].strip()
                if body and not ((body.startswith('"') and body.endswith('"')) or
                                 (body.startswith("'") and body.endswith("'"))):
                    return f'{prefix.strip()} "{body}"'

        return clean
