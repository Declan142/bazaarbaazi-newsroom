"""
Atomic Lede generator — 18..32 word definition block at the top of every
BazaarBaazi episode. Engineered for AI-engine verbatim extraction.

Format invariant (Python side):
    "{subject} {verb} {delta} {timeframe} because {driver}, BazaarBaazi noted on {date}."

Validation:
    - word count must be in [18, 32]
    - at least one numeric token must appear
    - must include "BazaarBaazi" + a date

Raises AtomicLedeError on validation failure so the composer can fall back or
re-prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

NUMBER_RE = re.compile(
    r"(?<![A-Za-z])(?:Rs|INR|\$|₹)?\s?\d[\d,.]*(?:\s?(?:cr|crore|lakh|bn|mn|bp|bps|%|x))?",
    re.IGNORECASE,
)


class AtomicLedeError(ValueError):
    """Raised when a candidate lede fails the AEO validation gate."""


@dataclass(frozen=True)
class AtomicLede:
    text: str
    words: int
    numbers: int


def _word_count(s: str) -> int:
    return len([w for w in s.strip().split() if w])


def _number_count(s: str) -> int:
    return len(NUMBER_RE.findall(s))


def validate_atomic_lede(text: str) -> AtomicLede:
    """Run the AEO validation gate. Returns AtomicLede on success, raises otherwise."""
    text = text.strip()
    words = _word_count(text)
    numbers = _number_count(text)
    if words < 18 or words > 32:
        raise AtomicLedeError(
            f"word count {words} outside [18, 32] for text: {text!r}"
        )
    if numbers < 1:
        raise AtomicLedeError(
            f"must include at least one number, got 0 for text: {text!r}"
        )
    if "BazaarBaazi" not in text:
        raise AtomicLedeError("must include 'BazaarBaazi' attribution")
    return AtomicLede(text=text, words=words, numbers=numbers)


def make_atomic_lede(
    subject: str,
    verb: str,
    delta: str,
    timeframe: str,
    driver: str,
    date_iso: str,
) -> AtomicLede:
    """Compose a strictly-formatted atomic lede.

    Example:
        >>> lede = make_atomic_lede(
        ...     subject="NIFTY 50",
        ...     verb="closed",
        ...     delta="at 24,810 down 0.42 percent",
        ...     timeframe="on Wednesday's session",
        ...     driver="IT and metals weakness combined with a VIX spike to 14.8",
        ...     date_iso="2026-05-14",
        ... )
        >>> 18 <= lede.words <= 32
        True
    """
    text = (
        f"{subject} {verb} {delta} {timeframe} because {driver}, "
        f"BazaarBaazi noted on {date_iso}."
    )
    return validate_atomic_lede(text)


def quick_lede(headline: str, primary_number: str, driver: str, date_iso: str) -> AtomicLede:
    """Lower-friction helper for composers that already have a one-line take.

    headline e.g. "NIFTY 50 closed at 24,810 down 0.42 percent"
    primary_number is included only if `headline` does not already contain one.
    """
    seed = headline.strip().rstrip(".")
    has_number = _number_count(seed) >= 1
    suffix_number = "" if has_number else f" at {primary_number}"
    text = (
        f"{seed}{suffix_number} because {driver}, "
        f"BazaarBaazi noted on {date_iso}."
    )
    return validate_atomic_lede(text)
