"""Feedback analysis: sentiment, theme detection and urgency scoring.

This is a dependency-free, rule-based engine so the platform runs anywhere.
It is designed to be swapped for an ML model (e.g. transformers) later:
only `analyze_feedback` needs to change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

POSITIVE = {
    "great", "love", "excellent", "amazing", "fast", "helpful", "easy", "good", "impressive",
    "awesome", "happy", "satisfied", "fantastic", "smooth", "reliable", "clean",
    "friendly", "intuitive", "recommend", "best", "thanks", "thank",
}
NEGATIVE = {
    "bad", "slow", "terrible", "awful", "hate", "broken", "bug", "bugs", "crash",
    "crashes", "confusing", "expensive", "rude", "late", "worst", "poor",
    "frustrating", "annoying", "useless", "error", "errors", "disappointed",
    "difficult", "unreliable", "missing", "wrong", "unacceptable", "crashing",
    "crashed", "lagging", "confused", "annoyed",
}
NEGATORS = {"not", "no", "never", "don't", "doesn't", "didn't", "isn't", "wasn't", "cannot", "can't"}
INTENSIFIERS = {"very", "really", "extremely", "super", "so", "incredibly"}

# Theme -> keywords. Extend freely for your domain.
THEMES: dict[str, set[str]] = {
    "pricing": {"price", "pricing", "expensive", "cost", "costly", "cheap", "fee", "fees", "billing", "invoice", "charged"},
    "performance": {"slow", "lag", "lagging", "laggy", "speed", "fast", "loading", "timeout", "latency", "freeze", "freezes"},
    "reliability": {"crash", "crashes", "crashing", "crashed", "bug", "bugs", "error", "errors", "broken", "down", "outage", "unreliable"},
    "usability": {"confusing", "intuitive", "easy", "difficult", "hard", "navigate", "ui", "design", "layout", "unclear"},
    "customer_support": {"support", "agent", "rude", "helpful", "response", "waited", "ticket", "help", "reply"},
    "delivery": {"delivery", "shipping", "late", "arrived", "package", "shipment", "courier"},
    "features": {"feature", "features", "missing", "wish", "integration", "export", "option", "options", "add"},
}

URGENT_WORDS = {"urgent", "immediately", "asap", "refund", "cancel", "cancelling", "canceling", "lawsuit", "unacceptable", "emergency", "legal"}

TOKEN_RE = re.compile(r"[a-zA-Z']+")


@dataclass
class Analysis:
    sentiment: str           # positive | neutral | negative
    score: float             # -1.0 .. 1.0
    themes: list[str] = field(default_factory=list)
    urgency: int = 1         # 1 (low) .. 5 (critical)
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


def sentiment_score(tokens: list[str]) -> float:
    """Lexicon score with negation and intensifier handling, normalized to [-1, 1]."""
    raw = 0.0
    hits = 0
    for i, tok in enumerate(tokens):
        if tok in POSITIVE:
            val = 1.0
        elif tok in NEGATIVE:
            val = -1.0
        else:
            continue
        hits += 1
        window = tokens[max(0, i - 2):i]
        if any(w in NEGATORS for w in window):
            val = -val * 0.8
        if any(w in INTENSIFIERS for w in window):
            val *= 1.5
        raw += val
    if hits == 0:
        return 0.0
    return max(-1.0, min(1.0, raw / hits))


def detect_themes(tokens: list[str]) -> list[str]:
    token_set = set(tokens)
    return [theme for theme, words in THEMES.items() if token_set & words]


def urgency_level(text: str, score: float, tokens: list[str]) -> int:
    level = 1
    if score <= -0.5:
        level += 2
    elif score < 0:
        level += 1
    if URGENT_WORDS & set(tokens):
        level += 2
    if text.count("!") >= 2:
        level += 1
    return max(1, min(5, level))


def analyze_feedback(text: str) -> Analysis:
    tokens = tokenize(text)
    score = sentiment_score(tokens)
    if score > 0.15:
        label = "positive"
    elif score < -0.15:
        label = "negative"
    else:
        label = "neutral"
    keywords = sorted({t for t in tokens if t in POSITIVE | NEGATIVE | URGENT_WORDS})
    return Analysis(
        sentiment=label,
        score=round(score, 3),
        themes=detect_themes(tokens),
        urgency=urgency_level(text, score, tokens),
        keywords=keywords,
    )
