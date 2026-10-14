"""
NLP Processing Service.
Full pipeline: cleaning → tokenization → stopword removal → lemmatization → TF-IDF.
"""

import re
import string
import logging
from typing import List, Dict, Any

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

logger = logging.getLogger(__name__)

# ── Ensure NLTK resources are available ───────────────────────────────────────
def _download_nltk_resources():
    resources = [
        ("tokenizers/punkt", "punkt"),
        ("tokenizers/punkt_tab", "punkt_tab"),
        ("corpora/stopwords", "stopwords"),
        ("corpora/wordnet", "wordnet"),
        ("corpora/omw-1.4", "omw-1.4"),
    ]
    for path, name in resources:
        try:
            nltk.data.find(path)
        except (LookupError, OSError):
            nltk.download(name, quiet=True)


_download_nltk_resources()

# ── Phishing keyword lexicon ───────────────────────────────────────────────────
PHISHING_KEYWORDS = {
    "urgent": 3, "immediately": 3, "verify": 2, "suspend": 3, "account": 1,
    "password": 2, "click": 1, "link": 1, "confirm": 2, "update": 1,
    "winner": 3, "congratulations": 2, "prize": 3, "free": 2, "limited": 2,
    "offer": 1, "bank": 2, "credit": 2, "debit": 2, "paypal": 2,
    "invoice": 2, "payment": 1, "refund": 2, "transaction": 1, "security": 1,
    "alert": 2, "warning": 2, "login": 2, "signin": 2, "username": 1,
    "ssn": 3, "social security": 3, "tax": 2, "irs": 3, "government": 1,
    "deadline": 2, "expire": 3, "expir": 3, "suspended": 3, "blocked": 2,
    "unusual activity": 3, "unauthorized": 3, "risk": 2, "fraud": 3,
}

LEMMATIZER = WordNetLemmatizer()
STOP_WORDS = set(stopwords.words("english"))


class NLPProcessor:
    """Full NLP preprocessing pipeline for email content."""

    def __init__(self):
        self.lemmatizer = LEMMATIZER
        self.stop_words = STOP_WORDS

    # ── Public API ─────────────────────────────────────────────────────────────

    def process(self, text: str) -> Dict[str, Any]:
        """
        Full pipeline: clean → tokenize → remove stopwords → lemmatize.
        Returns preprocessed text + features.
        """
        cleaned = self._clean_text(text)
        tokens = self._tokenize(cleaned)
        filtered = self._remove_stopwords(tokens)
        lemmatized = self._lemmatize(filtered)
        keywords = self._extract_phishing_keywords(text.lower())
        urgency_score = self._compute_urgency_score(keywords)

        return {
            "original_length": len(text),
            "cleaned_text": cleaned,
            "tokens": tokens[:50],              # Sample for debugging
            "processed_text": " ".join(lemmatized),
            "token_count": len(lemmatized),
            "phishing_keywords": keywords,
            "keyword_count": len(keywords),
            "urgency_score": urgency_score,
            "has_urgent_language": urgency_score > 5,
            "exclamation_count": text.count("!"),
            "caps_ratio": self._caps_ratio(text),
            "has_html": bool(re.search(r"<[a-zA-Z]", text)),
        }

    def get_features_for_model(self, text: str) -> str:
        """Return the processed text string ready for TF-IDF vectorization."""
        result = self.process(text)
        return result["processed_text"]

    # ── Private helpers ────────────────────────────────────────────────────────

    def _clean_text(self, text: str) -> str:
        """Remove HTML tags, special chars, extra whitespace."""
        # Strip HTML
        text = re.sub(r"<[^>]+>", " ", text)
        # Remove URLs (handled separately by URL scanner)
        text = re.sub(r"http\S+|www\.\S+", " URL ", text)
        # Remove email addresses
        text = re.sub(r"\S+@\S+", " EMAIL ", text)
        # Remove special chars but keep spaces and basic punctuation
        text = re.sub(r"[^a-zA-Z0-9\s!?.,-]", " ", text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text.lower()

    def _tokenize(self, text: str) -> List[str]:
        """Word tokenize using NLTK."""
        try:
            return word_tokenize(text)
        except Exception:
            return text.split()

    def _remove_stopwords(self, tokens: List[str]) -> List[str]:
        """Remove English stopwords and punctuation tokens."""
        return [
            t for t in tokens
            if t not in self.stop_words and t not in string.punctuation and len(t) > 2
        ]

    def _lemmatize(self, tokens: List[str]) -> List[str]:
        """Lemmatize each token to its base form."""
        return [self.lemmatizer.lemmatize(t) for t in tokens]

    def _extract_phishing_keywords(self, text: str) -> List[str]:
        """Return list of phishing keywords found in text."""
        found = []
        for kw in PHISHING_KEYWORDS:
            if kw in text:
                found.append(kw)
        return found

    def _compute_urgency_score(self, keywords: List[str]) -> int:
        """Calculate weighted urgency score from flagged keywords."""
        return sum(PHISHING_KEYWORDS.get(kw, 0) for kw in keywords)

    def _caps_ratio(self, text: str) -> float:
        """Ratio of UPPERCASE characters — phishing emails often shout."""
        letters = [c for c in text if c.isalpha()]
        if not letters:
            return 0.0
        upper = sum(1 for c in letters if c.isupper())
        return round(upper / len(letters), 3)
