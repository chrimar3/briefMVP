"""Client brief template sets and the template contract for newly generated renders.

A template set is three files side by side under `templates/` — `<name>.md` (EN),
`<name>.el.md` (EL) and `<name>.labels.json` — chosen by the client-config key
`brief_template`. `check_render_template` pins what a model otherwise re-decides every run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from pipeline import gates
from pipeline.stage_common import StageError

#: The client-brief template set used when a client config names none. Northlight is the
#: agency; this is its house template, not a fixture-specific one.
DEFAULT_BRIEF_TEMPLATE = "northlight_client_brief"
TEMPLATES_DIR = gates.REPO_ROOT / "templates"
_TEMPLATE_KEY_RE = re.compile(r"[a-z0-9][a-z0-9_]*")


def resolve_brief_template(client_config: Optional[dict], templates_dir: Optional[Path] = None) -> dict:
    """The client's template set: English layout, Greek twin and the fixed-label table.

    Chosen by the optional client-config key `brief_template` (a template name, not a path),
    defaulting to the agency house template. A set is three files side by side —
    `<name>.md` (EN), `<name>.el.md` (EL) and `<name>.labels.json` — because the Greek
    boilerplate is fixed agency copy, never something the model translates per run. A missing
    file is a configuration error raised before any model call.
    """
    templates_dir = Path(templates_dir) if templates_dir else TEMPLATES_DIR
    key = (client_config or {}).get("brief_template") or DEFAULT_BRIEF_TEMPLATE
    if not isinstance(key, str) or not _TEMPLATE_KEY_RE.fullmatch(key):
        raise StageError(
            f"client config brief_template {key!r} is not a template name "
            f"([a-z0-9_], no path) — name a template set under templates/"
        )
    files = {"en": templates_dir / f"{key}.md", "el": templates_dir / f"{key}.el.md",
             "labels": templates_dir / f"{key}.labels.json"}
    paths: dict[str, Any] = {"key": key, **files}
    missing = [str(p) for p in files.values() if not p.is_file()]
    if missing:
        raise StageError(
            f"template set {key!r} is incomplete — missing {missing}. A client template needs "
            f"the English layout, its fixed Greek twin and the label table."
        )
    return paths


def load_template_labels(path: Path) -> dict:
    """The template's fixed-label table; a StageError when a language block is missing."""
    labels = json.loads(Path(path).read_text(encoding="utf-8"))
    for lang in ("en", "el"):
        if lang not in labels:
            raise StageError(f"{path}: label table has no {lang!r} block")
    return labels


def _position_key(ref: dict) -> tuple:
    return ((ref or {}).get("source_id") or "").strip(), ((ref or {}).get("location") or "").strip()


def resolution_links(brief: dict) -> dict:
    """Open questions that a human conflict resolution has answered: {question idx: [conflict idx]}.

    Deterministic, so the model renders the answered state rather than judging it. A question
    counts as answered by a resolved conflict when it sits on the same field and its linked
    evidence spans the disagreement itself — at least two of the conflict's distinct position
    citations (or all of them, when the positions share one citation). A question that merely
    shares a field (a KPI question beside an objectives conflict) stays a live question.
    """
    links: dict[int, Any] = {}
    conflicts = brief.get("conflicts") or []
    for q_idx, question in enumerate(brief.get("open_questions") or []):
        q_field = (question.get("field") or "").strip().lower()
        q_keys = {_position_key(ref) for ref in (question.get("linked_evidence") or [])}
        for c_idx, conflict in enumerate(conflicts):
            if conflict.get("status") != "resolved_by_human":
                continue
            if (conflict.get("field") or "").strip().lower() != q_field:
                continue
            p_keys = {_position_key(p.get("evidence")) for p in (conflict.get("positions") or [])} - {("", "")}
            if p_keys and len(q_keys & p_keys) >= min(2, len(p_keys)):
                links.setdefault(q_idx, []).append(c_idx)
    return links


def _split_sections(render: str) -> tuple:
    """(preamble lines, [(heading, [body lines])]) — headings are `## ` lines, stripped."""
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    for raw in render.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            sections.append((line, []))
        elif sections:
            sections[-1][1].append(raw)
        else:
            preamble.append(raw)
    return preamble, sections


def _numbered_items(lines: list) -> list:
    """Numbered list items with their indented continuation lines, in order of appearance."""
    items = []
    for raw in lines:
        if re.match(r"^\s*\d{1,3}[.)]\s", raw):
            items.append([raw])
        elif items and raw.strip():
            items[-1].append(raw)
    return ["\n".join(item) for item in items]


def _preamble_violations(lang: str, lab: dict, preamble: list, signed: bool) -> list:
    """The first line is the template title; the banner matches the brief's sign-off state."""
    violations = []
    content = [line.strip() for line in preamble if line.strip()]
    if not content or content[0] != lab["title"]:
        violations.append(f"{lang}: first line must be the template title {lab['title']!r} "
                          f"— fixed boilerplate is copied, never re-worded (TRANSLATION.md rule 10)")
    banner = content[1] if len(content) > 1 else ""
    if signed and not banner.startswith(lab["banner_signed_prefix"]):
        violations.append(f"{lang}: the brief is signed off; the banner must start "
                          f"{lab['banner_signed_prefix']!r}")
    if not signed and banner != lab["banner_draft"]:
        violations.append(f"{lang}: the brief is a draft; the banner must be exactly {lab['banner_draft']!r}")
    return violations


def _heading_violations(lang: str, lab: dict, headings: list, open_qs: list, conflicts: list) -> list:
    """Only template headings; each required one exactly once; the conflicts heading tells the truth."""
    violations = []
    allowed = set(lab["sections"].values()) | {lab[k] for k in (
        "open_questions", "conflicts_open", "conflicts_resolved", "signoff", "internal")}
    for heading in headings:
        if heading not in allowed:
            violations.append(f"{lang}: heading {heading!r} is not in the template — copy the "
                              f"template's headings character-exact (TRANSLATION.md rule 10)")
    required = list(lab["sections"].values()) + [lab["signoff"], lab["internal"]]
    if open_qs:
        required.append(lab["open_questions"])
    if conflicts:
        any_open = any(c.get("status") != "resolved_by_human" for c in conflicts)
        expected, wrong = (("conflicts_open", "conflicts_resolved") if any_open
                           else ("conflicts_resolved", "conflicts_open"))
        required.append(lab[expected])
        if lab[wrong] in headings:
            state = "a conflict is still open" if any_open else "every conflict is resolved"
            violations.append(f"{lang}: {state}, so the conflicts heading must be "
                              f"{lab[expected]!r}, not {lab[wrong]!r} (TRANSLATION.md rule 11)")
    for heading in required:
        count = headings.count(heading)
        if count != 1:
            violations.append(f"{lang}: template heading {heading!r} appears {count} time(s); "
                              f"expected exactly once")
    return violations


def _internal_leak_violations(lang: str, lab: dict, render: str, enum_tokens: list) -> list:
    """Nothing internal above the internal section (TRANSLATION.md rule 12)."""
    violations = []
    cut = render.find("\n" + lab["internal"])
    client_part = render if cut < 0 else render[:cut]
    for label in lab.get("internal_labels") or []:
        if label in client_part:
            violations.append(f"{lang}: internal label {label!r} appears in the client-facing part "
                              f"— it belongs in the {lab['internal']!r} section (TRANSLATION.md rule 12)")
    for token in enum_tokens:
        if token in client_part:
            violations.append(f"{lang}: raw enum or placeholder {token!r} in the client-facing part "
                              f"— render it through the template's localised label (TRANSLATION.md rule 12)")
    return violations


def _field_section_violations(lang: str, lab: dict, body: dict, brief: dict, conflicts: list) -> list:
    """Field sections: resolved conflicts surface first; the empty-note only when truly empty."""
    violations = []
    for fieldname in gates.BRIEF_FIELDS:
        heading = lab["sections"].get(fieldname)
        if heading not in body:
            continue
        lines = [ln.strip() for ln in body[heading] if ln.strip()]
        resolved = [c for c in conflicts if c.get("status") == "resolved_by_human"
                    and (c.get("field") or "").strip() == fieldname]
        resolved_lines = [ln for ln in lines if re.sub(r"^[-*]\s+", "", ln).startswith(lab["resolved_entry"])]
        if len(resolved_lines) != len(resolved):
            violations.append(
                f"{lang}: section {heading!r} carries {len(resolved_lines)} resolved-conflict "
                f"line(s) but the brief has {len(resolved)} resolved conflict(s) on {fieldname} — "
                f"each resolution renders first in its field section as "
                f"'- {lab['resolved_entry']} …' (TRANSLATION.md rule 11)")
        elif resolved and lines and lines[0] not in resolved_lines:
            violations.append(f"{lang}: section {heading!r}: resolved-conflict line(s) must come "
                              f"first (TRANSLATION.md rule 11)")
        has_content = bool(brief.get(fieldname)) or bool(resolved)
        has_empty_note = lab["empty_section"] in lines
        if has_content and has_empty_note:
            violations.append(f"{lang}: section {heading!r} has entries or a resolution but still "
                              f"shows the empty-section note")
        if not has_content and not has_empty_note:
            violations.append(f"{lang}: section {heading!r} has no entries; render exactly "
                              f"{lab['empty_section']!r} (TRANSLATION.md rule 8)")
    return violations


def _answered_question_violations(lang: str, lab: dict, body: dict, open_qs: list, links: dict) -> list:
    """Questions a resolution answered render as answered; every other question stays live."""
    violations: list[str] = []
    if not (open_qs and lab["open_questions"] in body):
        return violations
    items = _numbered_items(body[lab["open_questions"]])
    for q_idx, item in enumerate(items[:len(open_qs)]):
        first_line = item.splitlines()[0]
        marked = lab["question_answered"] in first_line
        if q_idx in links and not marked:
            violations.append(
                f"{lang}: open question {q_idx + 1} was answered by the resolution of "
                f"conflicts{links[q_idx]} — render it in the answered form "
                f"({lab['question_answered']!r}), not as a live question (TRANSLATION.md rule 11)")
        if q_idx not in links and marked:
            violations.append(
                f"{lang}: open question {q_idx + 1} is marked answered but no resolution "
                f"answers it — it must render as a live question")
    return violations


def check_render_template(out_el: Path, out_en: Path, brief: dict, labels: dict) -> list:
    """The template contract for NEWLY generated renders (blocking inside the render stage).

    Kept apart from `check_render` on purpose: `check_render` is also the agency audit's render
    check over historical runs, whose renders predate this template and must stay auditable.
    This gate pins what a model otherwise re-decides every run: the fixed boilerplate of each
    language (never re-translated), the conflicts heading that matches conflict status,
    resolved conflicts surfaced in their own field sections, questions a resolution answered
    shown as answered, and no pipeline metadata above the internal section.
    """
    violations = []
    conflicts = brief.get("conflicts") or []
    open_qs = brief.get("open_questions") or []
    links = resolution_links(brief)
    signed = (brief.get("signoff") or {}).get("status") == "signed_off"
    enum_tokens = labels.get("internal_enum_tokens") or []

    for lang, path in (("el", out_el), ("en", out_en)):
        if not Path(path).is_file():
            violations.append(f"{lang}: no render at {path}")
            continue
        lab = labels[lang]
        render = Path(path).read_text(encoding="utf-8")
        preamble, sections = _split_sections(render)
        headings = [h for h, _ in sections]
        body = dict(sections)

        violations.extend(_preamble_violations(lang, lab, preamble, signed))
        violations.extend(_heading_violations(lang, lab, headings, open_qs, conflicts))
        violations.extend(_internal_leak_violations(lang, lab, render, enum_tokens))
        violations.extend(_field_section_violations(lang, lab, body, brief, conflicts))
        violations.extend(_answered_question_violations(lang, lab, body, open_qs, links))
    return violations
