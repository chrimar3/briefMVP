"""Language lint over the renders — warnings only (a blocking refusal needs owner approval).

The human language attestation stays the Greek quality gate; these findings are recorded in the
render step for that reviewer. Term preferences and banned calques live in
`config/greek_style.json`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from pipeline import gates
from pipeline.render_checks import CITATION_TAG_RE

GREEK_STYLE_PATH = gates.CONFIG_DIR / "greek_style.json"

_EL_VOWELS = "αεηιουωάέήίόύώϊϋΐΰ"
#: Feminine accusative article (and σε + article) and the negation δε keep their final ν before
#: a vowel and κ π τ ξ ψ (which also covers τσ, τζ) and the clusters μπ ντ γκ. «μη» is policed
#: only after «να»/«ας»: as a prefix («μη επιβεβαιωμένο») it correctly takes no ν.
_FINAL_NU_RE = re.compile(
    rf"(?<!\w)(τη|στη|δε|(?:να|ας)\s+μη)\s+(?=[{_EL_VOWELS}κπτξψ]|μπ|ντ|γκ)", re.IGNORECASE)
_ACCENTED_MONOSYLLABLE_RE = re.compile(
    r"(?<!\w)(ποιό|ποιά|ποιός|ποιοί|ποιές|ποιού|ποιάς|πιό|πιά|μιά|γιά|δυό)(?!\w)", re.IGNORECASE)
#: Only the unambiguous interrogative positions: the start of a question, after an opening
#: «, ( or :, or after «και»/«ή». A comma is deliberately NOT a trigger — «…, που σημαίνει…»
#: is the relative pronoun and correctly unaccented.
_INTERROGATIVE_RE = re.compile(r"(?:^|[«(:]\s*|(?<!\w)(?:και|ή)\s+)(που|πως)(?!\w)", re.IGNORECASE)
_QUOTED_RE = re.compile(r"«([^«»]*)»|\"([^\"]*)\"")


def load_greek_style(path: Path = None) -> dict:
    """The render-stage style table ({} when the file is absent)."""
    path = Path(path) if path else GREEK_STYLE_PATH
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _anchor_texts(brief: dict) -> list:
    refs = [ref for f in gates.BRIEF_FIELDS for e in (brief.get(f) or []) for ref in (e.get("evidence") or [])]
    refs += [p.get("evidence") or {} for c in (brief.get("conflicts") or []) for p in (c.get("positions") or [])]
    refs += [ref for q in (brief.get("open_questions") or []) for ref in (q.get("linked_evidence") or [])]
    return [(r or {}).get("anchor") or "" for r in refs if (r or {}).get("anchor")]


def _lintable(line: str, anchors: list) -> str:
    """The line minus citation tags and minus verbatim source quotations.

    A quoted span that is a substring of some evidence anchor is the source's own wording —
    its grammar belongs to the speaker and is never "fixed". Quoted text the agency wrote (a
    suggested question in «…») stays in scope; that is where the errors were found.
    """
    line = CITATION_TAG_RE.sub(" ", line)

    def _blank(match):
        inner = match.group(1) if match.group(1) is not None else match.group(2)
        return " " if inner.strip() and any(inner.strip() in a for a in anchors) else match.group(0)
    return _QUOTED_RE.sub(_blank, line)


def _phrase_re(phrase: str):
    return re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", re.IGNORECASE)


def render_language_warnings(out_el: Path, out_en: Path, brief: dict, glossary: dict,
                             style: Optional[dict] = None) -> list:
    """High-precision language lint over both renders. Returns warnings; never blocks.

    Greek: final-ν before vowels and stops, accented monosyllables, unaccented interrogative
    πού/πώς in a question, neuter/masculine article before a company name, calques listed in
    config/greek_style.json, and time words carried from a source. English: time words and a
    spoken hedge widened into a decade range. The human language attestation stays the Greek
    quality gate; these findings are recorded in the render step for that reviewer.
    """
    style = load_greek_style() if style is None else style
    anchors = _anchor_texts(brief)
    organisations = list(style.get("organisation_names") or []) + [
        t["term"] for t in (glossary.get("terms") or [])
        if t.get("term") and "company" in (t.get("note") or "").lower()]
    avoid = [(bad, term.get("el", ""), term.get("why", ""))
             for term in (style.get("preferred_terms") or []) for bad in (term.get("avoid") or [])]
    deixis = style.get("temporal_deixis") or {}
    warnings = []

    def _warn(lang, lineno, message, line):
        warnings.append(f"{lang}:{lineno}: {message} — {line.strip()[:90]!r}")

    for lang, path in (("el", out_el), ("en", out_en)):
        if not Path(path).is_file():
            continue
        for lineno, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
            if raw.strip().startswith("<!--"):
                continue
            line = _lintable(raw, anchors)
            for word in deixis.get(lang) or []:
                if _phrase_re(word).search(line):
                    _warn(lang, lineno, f"time word {word!r} carried from a source — name the meeting "
                                        f"and its date (TRANSLATION.md rule 13)", raw)
            if lang == "en":
                for phrase in style.get("range_drift_en") or []:
                    if _phrase_re(phrase).search(line):
                        _warn(lang, lineno, f"{phrase!r} widens a spoken figure into a decade range — "
                                            f"keep the hedge's width (TRANSLATION.md rule 5)", raw)
                continue
            for match in _FINAL_NU_RE.finditer(line):
                word = match.group(1).split()[-1]
                _warn(lang, lineno, f"«{word}» before a vowel or κ/π/τ/ξ/ψ/μπ/ντ/γκ takes a final ν "
                                    f"(«{word}ν»)", raw)
            for match in _ACCENTED_MONOSYLLABLE_RE.finditer(line):
                _warn(lang, lineno, f"monosyllable «{match.group(1)}» takes no accent", raw)
            for sentence in re.findall(r"[^.;!·]*;", line):
                for match in _INTERROGATIVE_RE.finditer(sentence.strip()):
                    word = match.group(1)
                    _warn(lang, lineno, f"interrogative «{word}» in a question takes the accent "
                                        f"(«{'πού' if word.lower() == 'που' else 'πώς'}»)", raw)
            for name in organisations:
                if re.search(rf"(?<!\w)(?:το|ο|του|τον)\s+{re.escape(name)}(?!\w)", line, re.IGNORECASE):
                    _warn(lang, lineno, f"company name {name!r} takes the feminine article agreeing "
                                        f"with «εταιρεία» («η {name}», «της {name}»)", raw)
            for bad, preferred, why in avoid:
                if _phrase_re(bad).search(line):
                    _warn(lang, lineno, f"«{bad}» is on the avoid list — use «{preferred}» ({why})", raw)
    return warnings
