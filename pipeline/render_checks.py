"""The render gate shared by the render stage and the agency audit: citations, coverage, no-invention.

`check_render` runs over every render — new ones inside the render stage's repair loop, and
historical ones in the agency audit — so it checks only what any faithful render must satisfy.
The template contract for new renders is `pipeline.render_template.check_render_template`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline import gates
from pipeline.money import money_figures

CITATION_TAG_RE = re.compile(r"\[([^\]]+)\]")
CLAIM_SECTION_RE = re.compile(r"^##\s+(\d)\.")
STRUCTURAL_PREFIXES = ("#", ">", "|", "---", "**Client:**", "**Input coverage:**", "**Sources used:**")


#: Mirrors the frozen harness's T2.4 rule. Deliberately a second implementation: the runner
#: gates the artifact, the harness grades it independently, and an independent grader that
#: shares its subject's code is not independent.
def claim_lines(render: str) -> list:
    """Non-structural lines inside the numbered claim sections (`## 1.` … `## 7.`)."""
    lines, in_claim_section = [], False
    for raw in render.splitlines():
        line = raw.strip()
        if line.startswith("##"):
            in_claim_section = bool(CLAIM_SECTION_RE.match(line))
            continue
        if not in_claim_section or not line or line.startswith(STRUCTURAL_PREFIXES):
            continue
        lines.append(line)
    return lines


def _digit_runs(text: str) -> set:
    """Digit sequences (≥2 digits) — the translation-invariant number fingerprint used by the
    render no-invention check. Separators are joined ONLY in true thousands grouping
    (1–3 digits then groups of exactly 3: "12,500" → "12500"); anything else splits on the
    separator, so Greek dotted dates ("15.9.2026") yield {"15","2026"} instead of a bogus
    seven-digit "figure" that would flag a faithful render."""
    runs = set()
    for match in re.findall(r"\d(?:[\d.,]*\d)?", text or ""):
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", match):
            runs.add(re.sub(r"[.,]", "", match))
        else:
            runs.update(part for part in re.split(r"[.,]", match) if len(part) >= 2)
    return runs


def _warning_region(render: str) -> str:
    """The body of every ⚠ section — where open questions and conflicts must land."""
    kept, in_warn = [], False
    for line in render.splitlines():
        if line.strip().startswith("##"):
            in_warn = "⚠" in line
            continue
        if in_warn:
            kept.append(line)
    return "\n".join(kept)


def _content_blob(brief: dict) -> str:
    """Every brief CONTENT string: entries, conflict statements and resolutions, open questions.

    The whole-object JSON is deliberately not the whitelist: evidence locations and meta dates
    would launder any small number as a "known" figure.
    """
    return "\n".join(
        [(e.get("content") or "") for f in gates.BRIEF_FIELDS for e in (brief.get(f) or [])]
        + [(p.get("statement") or "") for c in (brief.get("conflicts") or [])
           for p in (c.get("positions") or [])]
        + [(c.get("resolution") or "") for c in (brief.get("conflicts") or [])]
        + [(q.get(k) or "") for q in (brief.get("open_questions") or [])
           for k in ("gap", "why_it_matters", "suggested_question_for_client")]
    )


def _citation_violations(lang: str, render: str, known: set) -> list:
    """Every claim line carries a citation tag, and some tag names a known source."""
    violations = []
    for line in claim_lines(render):
        tags = CITATION_TAG_RE.findall(line)
        if not tags:
            violations.append(f"{lang}: claim line with no citation tag — {line[:80]!r}")
        elif not any(any(sid in tag for sid in known) for tag in tags):
            violations.append(f"{lang}: citation tag names no known source — {line[:80]!r}")
    return violations


def _glossary_presence_violations(lang: str, render: str, protected: list, brief_blob: str) -> list:
    """A keep-Latin glossary term the brief uses reaches the render."""
    return [f"{lang}: glossary term {term!r} is in the brief but missing from the render"
            for term in protected if term in brief_blob and term not in render]


def _no_invention_violations(lang: str, render: str, brief: dict, known: set, protected: list) -> list:
    """Rendering adds a language, never content (TRANSLATION.md rule 3, machine-checked).

    Free prose can be legitimately rephrased, so this check pins the token classes that survive
    translation byte-for-byte — protected glossary terms, digit runs, and currency marks — and
    requires each one appearing in a claim or ⚠ line to exist in the brief's CONTENT strings.
    Only citation tags naming a known source are stripped — stripping every bracketed span
    would let an invented figure hide inside a gloss.
    """
    violations = []
    content_blob = _content_blob(brief)
    claim_text = "\n".join(claim_lines(render)) + "\n" + _warning_region(render)
    bare_claims = CITATION_TAG_RE.sub(
        lambda m: " " if any(sid in m.group(0) for sid in known) else m.group(0), claim_text)
    for term in protected:
        if term.lower() in bare_claims.lower() and term.lower() not in content_blob.lower():
            violations.append(
                f"{lang}: render claims glossary term {term!r} but no brief content string "
                f"uses it — a render adds no content the brief does not carry "
                f"(TRANSLATION.md rule 3)"
            )
    content_digits = _digit_runs(content_blob)
    content_money = money_figures(content_blob)
    for line in bare_claims.splitlines():
        stripped = line.strip()
        if (not stripped or stripped.startswith(STRUCTURAL_PREFIXES)
                or re.fullmatch(r"\*\*[^*]+\*\*:?", stripped)):
            # Structural micro-headers ("**OQ-11 — Audiences**") are labels, not claims —
            # their ordinals are render plumbing, exactly like list numbering.
            continue
        body = re.sub(r"^\s*\d{1,3}[.)]\s+", "", line)
        for run in sorted(_digit_runs(body) - content_digits):
            violations.append(
                f"{lang}: figure {run!r} appears in a render claim but in no brief content "
                f"string — remove the figure; renders never introduce numbers, in digits "
                f"or in words (TRANSLATION.md rule 3): {line[:80]!r}"
            )
        for figure in sorted(money_figures(body) - content_money):
            violations.append(
                f"{lang}: currency-marked figure (≈{figure}) in a render claim has no such "
                f"mark in any brief content string — remove the mark or the figure "
                f"(TRANSLATION.md rule 3): {line[:80]!r}"
            )
    return violations


def _warning_section_violations(lang: str, render: str, brief: dict) -> list:
    """Open questions and conflicts land, complete, in the render's ⚠ sections.

    Language-neutral on purpose. The first version of this check looked for "?" and failed a
    perfectly good Greek render, because Greek marks a question with ";". The template gives
    both special sections a "⚠" heading, so that marker is the signal — it survives
    translation, which is exactly what a bilingual gate needs. Coverage inside the region is
    checked the same way: open questions are numbered (template contract), so the
    numbered-item count is translation-invariant; conflict positions carry source_ids, which
    survive translation character-exact. Both checks are ≥-shaped — a render may elaborate, it
    may not omit.
    """
    violations: list[str] = []
    open_qs = brief.get("open_questions") or []
    brief_conflicts = brief.get("conflicts") or []
    if not (open_qs or brief_conflicts):
        return violations
    if not any(line.startswith("##") and "⚠" in line for line in render.splitlines()):
        violations.append(
            f"{lang}: brief has open questions or conflicts but the render has no '⚠' "
            f"section heading — open questions and conflicts are the product, not an appendix"
        )
        return violations
    region = _warning_region(render)
    if open_qs:
        numbered = len(re.findall(r"^\s*\d{1,3}[.)]\s", region, re.MULTILINE))
        if numbered < len(open_qs):
            violations.append(
                f"{lang}: render numbers {numbered} item(s) in the ⚠ sections but the "
                f"brief carries {len(open_qs)} open question(s) — every question "
                f"reaches both renders"
            )
    for idx, conflict in enumerate(brief_conflicts):
        for p_idx, position in enumerate(conflict.get("positions") or []):
            sid = ((position.get("evidence") or {}).get("source_id") or "")
            if sid and sid not in region:
                violations.append(
                    f"{lang}: conflicts[{idx}] position {p_idx} cites source {sid!r} "
                    f"but that source never appears in the ⚠ region — both sides of "
                    f"a conflict render with their citations"
                )
    return violations


def check_render(out_el: Path, out_en: Path, brief: dict, glossary: dict) -> list:
    """Gate both renders: citations, glossary terms, no invented content, complete ⚠ sections."""
    violations = []
    for lang, path in (("el", out_el), ("en", out_en)):
        if not path.is_file():
            violations.append(f"no {lang} render at {path}")
    if violations:
        return violations

    known = {s["source_id"] for s in (brief.get("meta") or {}).get("sources") or []}
    brief_blob = json.dumps(brief, ensure_ascii=False)
    protected = [t["term"] for t in (glossary.get("terms") or [])
                 if t.get("rule") == "keep_latin" and t.get("term")]

    for lang, path in (("el", out_el), ("en", out_en)):
        render = path.read_text(encoding="utf-8")
        violations.extend(_citation_violations(lang, render, known))
        violations.extend(_glossary_presence_violations(lang, render, protected, brief_blob))
        violations.extend(_no_invention_violations(lang, render, brief, known, protected))
        violations.extend(_warning_section_violations(lang, render, brief))
    return violations
