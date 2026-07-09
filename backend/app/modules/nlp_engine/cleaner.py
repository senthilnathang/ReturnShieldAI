from __future__ import annotations

import re
import unicodedata
from typing import Optional

from .config import nlp_config


class TextCleaner:
    def __init__(
        self,
        lowercase: bool = True,
        unicode_normalize: bool = True,
        remove_emojis: bool = True,
        normalize_punctuation: bool = True,
        clean_whitespace: bool = True,
    ):
        self.lowercase = lowercase
        self.unicode_normalize = unicode_normalize
        self.remove_emojis = remove_emojis
        self.normalize_punctuation = normalize_punctuation
        self.clean_whitespace = clean_whitespace

        self._emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
            "\U00002600-\U000026FF\U00002B50\U00002300-\U000023FF\u200d\u200b"
            "\U0000FE00-\U0000FE0F\u00a9\u00ae]+"
        )
        self._punctuation_pattern = re.compile(r"[^\w\s\'\-]")
        self._multi_space = re.compile(r"\s{2,}")
        self._multi_newline = re.compile(r"\n{3,}")

    def clean(self, text: Optional[str]) -> str:
        if not text:
            return ""
        text = str(text)
        if len(text) > nlp_config.max_text_length:
            text = text[: nlp_config.max_text_length]
        if self.unicode_normalize:
            text = unicodedata.normalize("NFKC", text)
        if self.lowercase:
            text = text.lower()
        if self.remove_emojis:
            text = self._emoji_pattern.sub(" ", text)
        if self.normalize_punctuation:
            text = self._punctuation_pattern.sub(" ", text)
        if self.clean_whitespace:
            text = self._multi_newline.sub("\n\n", text)
            text = self._multi_space.sub(" ", text)
            text = text.strip()
        return text

    def clean_sources(self, sources: dict[str, Optional[str]]) -> dict[str, str]:
        return {key: self.clean(val) for key, val in sources.items()}

    def merge_sources(self, sources: dict[str, Optional[str]]) -> str:
        cleaned = self.clean_sources(sources)
        parts = [v for v in cleaned.values() if v.strip()]
        return " ".join(parts)
