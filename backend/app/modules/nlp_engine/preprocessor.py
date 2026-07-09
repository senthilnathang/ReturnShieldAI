from __future__ import annotations

import re
from typing import Optional

from .config import nlp_config

try:
    from nltk.corpus import stopwords as nltk_stopwords

    _STOPWORDS = set(nltk_stopwords.words(nlp_config.stopwords_language))
except Exception:
    _STOPWORDS = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "by", "with", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "need", "dare",
        "ought", "used", "i", "you", "he", "she", "it", "we", "they", "me",
        "him", "her", "us", "them", "my", "your", "his", "its", "our", "their",
        "mine", "yours", "hers", "ours", "theirs", "this", "that", "these",
        "those", "some", "any", "no", "every", "each", "all", "both", "few",
        "many", "much", "several", "not", "so", "very", "too", "quite",
        "really", "just", "about", "almost", "nearly", "such", "only", "also",
        "very", "really", "quite", "just",
    }

try:
    from nltk.stem import WordNetLemmatizer

    _lemmatizer = WordNetLemmatizer()
except Exception:
    _lemmatizer = None


class TextPreprocessor:
    def __init__(
        self,
        remove_stopwords: bool = True,
        lemmatize: bool = True,
        min_token_length: int = 2,
    ):
        self.remove_stopwords = remove_stopwords
        self.lemmatize = lemmatize and _lemmatizer is not None
        self.min_token_length = min_token_length

    def tokenize(self, text: str) -> list[str]:
        return text.split()

    def preprocess(self, text: str) -> str:
        if not text:
            return ""
        tokens = self.tokenize(text)
        processed = []
        for token in tokens:
            if len(token) < self.min_token_length:
                continue
            if self.remove_stopwords and token in _STOPWORDS:
                continue
            if self.lemmatize:
                token = _lemmatizer.lemmatize(token)
            processed.append(token)
        return " ".join(processed)

    def preprocess_sources(self, sources: dict[str, str]) -> dict[str, str]:
        return {key: self.preprocess(val) for key, val in sources.items()}
