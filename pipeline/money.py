"""The one currency normaliser for the whole pipeline (synthesis, render, creative, delivery gates)."""

from __future__ import annotations

import re

#: Currency marks the money gate recognises when ATTACHED TO A FIGURE (€50.000, EUR 50k,
#: 90 €). The word «ευρώ» in prose is deliberately not a mark — asking in words is the
#: CORRECT behavior the gate must never punish (SYNTHESIS.md rule 5). Never extend these
#: with fixture-specific patterns: that would be tuning against the answer key.
MONEY_PREFIX_RE = re.compile(r"(?:€|\bEUR\b)\s*(\d[\d.,]*)\s*([kK]\b)?")
MONEY_SUFFIX_RE = re.compile(r"(\d[\d.,]*)\s*([kK])?\s*€")


def money_figures(text: str) -> set:
    """Canonical integer for every currency-marked figure in `text`.

    Separator-insensitive (€50.000 ≡ €50,000) and k-aware (€50k ≡ €50.000), so a faithful
    reformatting of a sourced figure never trips the gate. Decimal forms (€1,5 εκατ.) are
    out of scope by design — precision over recall; the frozen harness stays the backstop
    for shapes this normaliser does not know.
    """
    found = set()
    for figure, k in MONEY_PREFIX_RE.findall(text) + MONEY_SUFFIX_RE.findall(text):
        digits = re.sub(r"[.,]", "", figure)
        if digits.isdigit():
            found.add(int(digits) * (1000 if k else 1))
    return found
