from __future__ import annotations

import logging
import re
from typing import Any, Optional

from .config import nlp_config

logger = logging.getLogger(__name__)

try:
    import spacy
    _nlp = None
except ImportError:
    _nlp = None
    logger.warning("spaCy not installed; using regex-based entity extraction")


class EntityExtractor:
    def __init__(self):
        self._spacy_nlp = None
        if _nlp is not None:
            try:
                self._spacy_nlp = spacy.load(nlp_config.spacy_model, disable=["parser", "tagger"])
            except OSError:
                try:
                    self._spacy_nlp = spacy.load("en_core_web_sm", disable=["parser", "tagger"])
                except OSError:
                    logger.warning("spaCy model not found; using regex fallback")

    def extract(self, text: str) -> dict[str, Any]:
        result = {
            "order_numbers": self._extract_order_numbers(text),
            "tracking_numbers": self._extract_tracking_numbers(text),
            "couriers": self._extract_couriers(text),
            "dates": self._extract_dates(text),
            "money_amounts": self._extract_money(text),
            "product_names": self._extract_product_names(text),
            "serial_numbers": self._extract_serial_numbers(text),
            "imei": self._extract_imei(text),
            "addresses": self._extract_addresses(text),
            "phone_numbers": self._extract_phones(text),
        }
        if self._spacy_nlp:
            spacy_entities = self._extract_spacy(text)
            for key in spacy_entities:
                if spacy_entities[key]:
                    existing = result.get(key, [])
                    result[key] = list(set(existing + spacy_entities[key]))
        return result

    def _extract_spacy(self, text: str) -> dict[str, list[str]]:
        doc = self._spacy_nlp(text[:5000])
        entities = {"dates": [], "money_amounts": [], "product_names": [], "addresses": []}
        for ent in doc.ents:
            if ent.label_ == "DATE":
                entities["dates"].append(ent.text)
            elif ent.label_ == "MONEY":
                entities["money_amounts"].append(ent.text)
            elif ent.label_ == "PRODUCT":
                entities["product_names"].append(ent.text)
            elif ent.label_ in ("GPE", "LOC", "FAC"):
                entities["addresses"].append(ent.text)
        return entities

    def _extract_order_numbers(self, text: str) -> list[str]:
        patterns = [
            r"#?\bORD[-: ]?(\w{6,12})\b",
            r"#?\b(order|ord)[\s\-:#]*(\w{6,12})\b",
            r"\b\d{6,12}\b(?=\s*(?:order|return|refund))",
        ]
        matches = set()
        for p in patterns:
            for m in re.finditer(p, text, re.IGNORECASE):
                matches.add(m.group(0).strip("# "))
        return sorted(matches)

    def _extract_tracking_numbers(self, text: str) -> list[str]:
        patterns = [
            r"\b1Z\w{16}\b",
            r"\b\d{20,22}\b",
            r"\b[A-Z]{2}\d{9,12}[A-Z]{2}\b",
            r"tracking[\s#:]*(\w{8,22})",
        ]
        matches = set()
        for p in patterns:
            for m in re.finditer(p, text, re.IGNORECASE):
                matches.add(m.group(0))
        return sorted(matches)

    def _extract_couriers(self, text: str) -> list[str]:
        courier_names = [
            "fedex", "ups", "usps", "dhl", "purolator", "canada post",
            "royal mail", "australia post", "dpd", "hermes", "evri",
            "lasership", "ontrac", "amazon logistics",
        ]
        found = set()
        text_lower = text.lower()
        for name in courier_names:
            if name in text_lower:
                found.add(name.title())
        return sorted(found)

    def _extract_dates(self, text: str) -> list[str]:
        patterns = [
            r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b",
            r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",
            r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s-]\d{1,2},?\s*\d{2,4}\b",
            r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}\b",
        ]
        matches = set()
        for p in patterns:
            for m in re.finditer(p, text, re.IGNORECASE):
                matches.add(m.group(0))
        return sorted(matches)

    def _extract_money(self, text: str) -> list[dict[str, Any]]:
        pattern = r"[$£€]?\s*\d+\.?\d{0,2}\s*(?:usd|eur|gbp|dollars?|euros?|pounds?)?"
        amounts = []
        for m in re.finditer(pattern, text, re.IGNORECASE):
            amounts.append(m.group(0).strip())
        return amounts

    def _extract_product_names(self, text: str) -> list[str]:
        patterns = [
            r"\b(?:iphone|ipad|macbook|samsung|sony|nikon|canon|dell|hp|lenovo)\s+\w+\b",
            r"model\s*[#: ]?\w+",
            r"(?:product|item)\s*[#: ]?\w+",
        ]
        matches = set()
        for p in patterns:
            for m in re.finditer(p, text, re.IGNORECASE):
                matches.add(m.group(0))
        return sorted(matches)

    def _extract_serial_numbers(self, text: str) -> list[str]:
        pattern = r"(?:serial|s/n|sn)[\s#:]*([A-Z0-9]{6,20})"
        matches = set()
        for m in re.finditer(pattern, text, re.IGNORECASE):
            matches.add(m.group(0))
        return sorted(matches)

    def _extract_imei(self, text: str) -> list[str]:
        pattern = r"\b\d{15}\b"
        matches = set()
        for m in re.finditer(pattern, text):
            matches.add(m.group(0))
        return sorted(matches)

    def _extract_addresses(self, text: str) -> list[str]:
        pattern = r"\d{1,5}\s+\w+\s+(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|blvd|boulevard|way|court|ct|circle|cir)"
        matches = set()
        for m in re.finditer(pattern, text, re.IGNORECASE):
            matches.add(m.group(0))
        return sorted(matches)

    def _extract_phones(self, text: str) -> list[str]:
        pattern = r"\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"
        matches = set()
        for m in re.finditer(pattern, text):
            matches.add(m.group(0))
        return sorted(matches)
