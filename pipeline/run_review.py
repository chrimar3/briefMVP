"""Run Review Page — deterministic walkthrough of one pipeline run.

The companion to pipeline/review.py: where brief_review.html shows the account lead the
RESULT (the canonical brief), run_review.html shows how the ingested material — RFP,
email thread, transcripts, background docs — travelled through the pipeline: what each
source contributed, what the fidelity gate flagged, which cross-source candidates the
conflict pass surfaced, and where the run stopped or completed.

Same rules as the brief page: pure rendering, zero model calls, self-contained single
file, every artifact string html-escaped. It reads only the run's own artifact files —
never `attempts` payloads — so run cost and model information cannot reach the page.

Usage:
    python3 pipeline/run_review.py runs/<id>    # emits runs/<id>/run_review.html
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow `python3 pipeline/run_review.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.review import (
    BRIEF_FIELDS,
    CONFIDENCE_LABELS,
    FIELD_LABELS,
    PAGE_JS,
    QUALIFIER_LABELS,
    THEME_CSS,
    ReviewInputError,
    _PAGE_CSS,
    _bil,
    _e,
    _pct,
    _prettify,
)

#: Raw source documents are embedded for reference; huge files are truncated with a note.
RAW_SOURCE_CHAR_CAP = 20000

STEP_LABELS = {
    "readiness_gate": ("Έλεγχος επάρκειας", "Readiness gate"),
    "classification": ("Ταξινόμηση", "Classification"),
    "fidelity_check": ("Έλεγχος πιστότητας", "Fidelity check"),
    "extraction": ("Εξαγωγή", "Extraction"),
    "conflict_pass": ("Διασταύρωση πηγών", "Conflict pass"),
    "synthesis": ("Σύνθεση", "Synthesis"),
    "render": ("Απόδοση ΕΛ/EN", "Render EL/EN"),
    "creative_shadow": ("Δημιουργικό (σκιά)", "Creative (shadow)"),
}

SOURCE_TYPE_LABELS = {
    "rfp": ("RFP", "RFP", "📄"),
    "email_thread": ("Αλληλογραφία", "Email thread", "✉️"),
    "transcript": ("Απομαγνητοφώνηση", "Transcript", "🎙️"),
    "background": ("Υλικό υποβάθρου", "Background", "📚"),
}

OUTCOME_LABELS = {
    "complete": ("Ολοκληρώθηκε", "Complete", "ok"),
    "insufficient_input": ("Αρνήθηκε — ανεπαρκή στοιχεία", "Refused — insufficient input", "bad"),
    "halted_for_human": ("Σταμάτησε — απαιτείται άνθρωπος", "Halted — human required", "warn"),
    "stage_failed": ("Απέτυχε σε στάδιο", "A stage failed", "bad"),
}

#: The only step keys the page may carry. `kind` and `attempts` stay out by design —
#: attempts hold run cost and model information, which never reaches a review page.
_SAFE_STEP_KEYS = ("number", "name", "description", "status")


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def collect_run(run_dir) -> dict:
    """Gather the run's artifact files into one plain dict for the pure renderer."""
    run_dir = Path(run_dir)
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.is_file():
        raise ReviewInputError(
            f"no run_manifest.json in {run_dir} — the run review renders a runner "
            "manifest plus its artifact files; point it at a pipeline run directory"
        )
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ReviewInputError(f"{manifest_path} is not a valid run manifest")

    steps = [
        {key: step.get(key) for key in _SAFE_STEP_KEYS}
        for step in manifest.get("steps") or []
        if isinstance(step, dict)
    ]
    sources = [dict(s) for s in manifest.get("sources") or [] if isinstance(s, dict)]

    extracts = {}
    extracts_dir = run_dir / "extracts"
    if extracts_dir.is_dir():
        for path in sorted(extracts_dir.glob("*.json")):
            data = _load_json(path)
            if isinstance(data, dict):
                extracts[path.stem] = data

    fidelity = {}
    fidelity_dir = run_dir / "fidelity"
    if fidelity_dir.is_dir():
        for path in sorted(fidelity_dir.glob("*.report.json")):
            data = _load_json(path)
            if isinstance(data, dict):
                fidelity[path.name.replace(".report.json", "")] = data

    known = {s.get("source_id") for s in sources}
    for source_id in sorted(extracts):
        if source_id not in known:  # extraction ran on a source the manifest missed
            sources.append({"source_id": source_id, "source_type": "", "source_date": ""})

    raw_sources = {}
    project_dir = Path(str(manifest.get("project_dir") or ""))
    if project_dir.is_dir():
        for source in sources:
            source_id = str(source.get("source_id") or "")
            doc = project_dir / f"{source_id}.md"
            if source_id and doc.is_file():
                try:
                    raw_sources[source_id] = doc.read_text(encoding="utf-8")
                except OSError:
                    pass

    return {
        "run": {
            "run_id": manifest.get("run_id"),
            "pipeline_version": manifest.get("pipeline_version"),
            "project_name": Path(str(manifest.get("project_dir") or "")).name,
            "started_ts": manifest.get("started_ts"),
            "finished_ts": manifest.get("finished_ts"),
            "outcome": manifest.get("outcome"),
            "stage": manifest.get("stage"),
            "demo_profile": bool(manifest.get("demo_profile")),
            "sources": sources,
            "steps": steps,
        },
        "classification": _load_json(run_dir / "classification.json"),
        "fidelity": fidelity,
        "extracts": extracts,
        "conflicts": _load_json(run_dir / "conflict_candidates.json"),
        "brief": _load_json(run_dir / "brief.json"),
        "raw_sources": raw_sources,
        "has_brief_page": (run_dir / "brief_review.html").is_file(),
        "renders": {
            "el": (run_dir / "brief_el.md").is_file(),
            "en": (run_dir / "brief_en.md").is_file(),
            "el_view": (run_dir / "brief_el.html").is_file(),
            "en_view": (run_dir / "brief_en.html").is_file(),
        },
    }


# ------------------------------------------------------------------- sections


def _outcome_chip(outcome: str, demo_profile: bool) -> str:
    label_el, label_en, tone = OUTCOME_LABELS.get(
        outcome, (outcome or "—", outcome or "—", "")
    )
    demo = (
        ' <span class="chip chip-demo">' + _bil("προφίλ demo", "demo profile") + "</span>"
        if demo_profile
        else ""
    )
    return f'<span class="chip outcome-{_e(tone or "other")}">{_bil(_e(label_el), _e(label_en))}</span>' + demo


def _step_status(status: str) -> tuple[str, str]:
    """Map a manifest step status to (tone class, bilingual label html)."""
    status = str(status or "")
    if status == "pass":
        return "ok", _bil("πέρασε", "pass")
    if "refused" in status and "overridden" in status:
        return "warn", _bil("αρνήθηκε · παράκαμψη demo", "refused · demo override")
    if "refused" in status:
        return "bad", _bil("αρνήθηκε", "refused")
    if "fail" in status or "error" in status:
        return "bad", _bil("απέτυχε", "failed")
    return "other", f'<span class="mono">{_e(status)}</span>'


def _journey(run: dict) -> str:
    cards = []
    for step in run.get("steps") or []:
        name = str(step.get("name") or "")
        label_el, label_en = STEP_LABELS.get(name, (name, name))
        tone, status_html = _step_status(step.get("status"))
        cards.append(
            f'<li class="jstep {tone}">'
            f'<span class="jstep-no">{_e(step.get("number", ""))}</span>'
            '<span class="jstep-body">'
            f'<span class="jstep-name">{_bil(_e(label_el), _e(label_en))}</span>'
            f'<span class="jstep-status">{status_html}</span>'
            "</span></li>"
        )
    return (
        '<section id="journey"><h2>'
        + _bil("Η διαδρομή του υλικού", "How the material travelled")
        + f'</h2><ol class="journey">{"".join(cards)}</ol></section>'
    )


def _extract_item(item: dict) -> str:
    item = item or {}
    confidence = str(item.get("confidence", ""))
    qualifier = str(item.get("qualifier", ""))
    conf_el, conf_en = CONFIDENCE_LABELS.get(confidence, (confidence, confidence))
    qual_el, qual_en = QUALIFIER_LABELS.get(qualifier, (qualifier, qualifier))
    return (
        '<div class="x-item">'
        '<div class="x-head">'
        f'<p class="x-value">{_e(item.get("value", ""))}</p>'
        '<p class="entry-badges">'
        f'<span class="pill conf-{_e(confidence)}">{_bil(_e(conf_el), _e(conf_en))}</span>'
        f'<span class="badge qual-{_e(qualifier)}">{_bil(_e(qual_el), _e(qual_en))}</span>'
        "</p></div>"
        f'<blockquote class="ev-anchor">{_e(item.get("anchor", ""))}</blockquote>'
        '<p class="ev-meta">'
        f'<span class="ev-loc">{_e(item.get("location", ""))}</span>'
        f'<span class="ev-speaker">{_e(item.get("speaker_or_author", ""))}</span>'
        "</p></div>"
    )


def _source_card(source: dict, extract: dict | None, fidelity: dict | None, raw: str | None) -> str:
    source_id = str(source.get("source_id") or "")
    source_type = str(source.get("source_type") or "")
    type_el, type_en, icon = SOURCE_TYPE_LABELS.get(
        source_type, (source_type or "πηγή", source_type or "source", "🗂️")
    )
    head = (
        '<div class="src-head">'
        f'<span class="src-icon" aria-hidden="true">{icon}</span>'
        '<div class="src-id">'
        f"<h3>{_bil(_e(type_el), _e(type_en))}</h3>"
        f'<p class="src-meta"><span class="mono">{_e(source_id)}</span>'
        + (f' · {_e(source.get("source_date"))}' if source.get("source_date") else "")
        + "</p></div></div>"
    )

    chips = []
    if fidelity:
        tone = "chip-resolved" if fidelity.get("verdict") == "pass" else "chip-open"
        flagged = fidelity.get("tokens_flagged", 0)
        chips.append(
            f'<span class="chip {tone}">'
            + _bil("πιστότητα: ", "fidelity: ")
            + _e(fidelity.get("verdict", ""))
            + (
                f" · {_e(flagged)} " + _bil("όροι επισημάνθηκαν", "tokens flagged")
                if flagged
                else ""
            )
            + "</span>"
        )
    body = ""
    if extract is not None:
        item_count = sum(len(extract.get(f) or []) for f in BRIEF_FIELDS)
        question_count = len(extract.get("open_questions") or [])
        note_count = len(extract.get("extraction_notes") or [])
        internal_count = len(extract.get("internal_conflicts") or [])
        chips.append(
            f'<span class="stat"><strong>{item_count}</strong> '
            + _bil("αποσπάσματα με παραπομπή", "cited excerpts")
            + "</span>"
        )
        chips.append(
            f'<span class="stat"><strong>{question_count}</strong> '
            + _bil("κενά → ερωτήσεις", "gaps → questions")
            + "</span>"
        )
        if note_count:
            chips.append(
                f'<span class="stat stat-warn"><strong>{note_count}</strong> '
                + _bil("σημειώσεις εξαγωγής", "extraction notes")
                + "</span>"
            )
        if internal_count:
            chips.append(
                f'<span class="stat stat-warn"><strong>{internal_count}</strong> '
                + _bil("εσωτερικές αντιφάσεις", "internal contradictions")
                + "</span>"
            )

        groups = []
        for field in BRIEF_FIELDS:
            items = extract.get(field) or []
            if not items:
                continue
            label_el, label_en = FIELD_LABELS.get(field, (field, field))
            groups.append(
                f"<h4>{_bil(label_el, label_en)}"
                f' <span class="field-count">{len(items)}</span></h4>'
                + "".join(_extract_item(item) for item in items)
            )
        if groups:
            body += (
                '<details class="evidence"><summary>'
                + _bil("Τι εξήχθη", "What was extracted")
                + f' <span class="ev-count">({item_count})</span></summary>'
                + "".join(groups)
                + "</details>"
            )
        notes = extract.get("extraction_notes") or []
        if notes:
            body += (
                '<details class="evidence"><summary>'
                + _bil("Σημειώσεις εξαγωγής", "Extraction notes")
                + f' <span class="ev-count">({len(notes)})</span></summary><ul class="notes">'
                + "".join(f"<li>{_e(note)}</li>" for note in notes)
                + "</ul></details>"
            )
    else:
        body += (
            '<p class="empty-field">'
            + _bil("Δεν υπάρχει εξαγωγή για αυτή την πηγή.", "No extract for this source.")
            + "</p>"
        )
    if raw is not None:
        shown = raw[:RAW_SOURCE_CHAR_CAP]
        truncated = (
            '<p class="ev-meta">'
            + _bil("…το έγγραφο συνεχίζεται", "…document continues")
            + "</p>"
            if len(raw) > RAW_SOURCE_CHAR_CAP
            else ""
        )
        body += (
            '<details class="evidence"><summary>'
            + _bil("Πρωτότυπο έγγραφο", "Original document")
            + "</summary>"
            + f'<pre class="raw-doc">{_e(shown)}</pre>'
            + truncated
            + "</details>"
        )
    stats = f'<div class="src-stats">{"".join(chips)}</div>' if chips else ""
    return f'<article class="src-card">{head}{stats}{body}</article>'


def _sources_section(data: dict) -> str:
    run = data["run"]
    cards = "".join(
        _source_card(
            source,
            data["extracts"].get(str(source.get("source_id"))),
            data["fidelity"].get(str(source.get("source_id"))),
            data["raw_sources"].get(str(source.get("source_id"))),
        )
        for source in run.get("sources") or []
    )
    if not cards:
        cards = (
            '<p class="empty-field">'
            + _bil("Καμία πηγή δεν καταγράφηκε.", "No sources were recorded.")
            + "</p>"
        )
    return (
        '<section id="sources"><h2>'
        + _bil("Τι εισήλθε — πηγή προς πηγή", "What came in — source by source")
        + f'</h2><div class="src-grid">{cards}</div></section>'
    )


def _candidate_card(candidate: dict) -> str:
    candidate = candidate or {}
    field = str(candidate.get("field", ""))
    label_el, label_en = FIELD_LABELS.get(field, (field, field))
    positions = "".join(
        '<div class="position">'
        f'<p class="ev-meta"><span class="ev-source">{_e((p or {}).get("source_id", ""))}</span></p>'
        f'<p class="pos-statement">{_e((p or {}).get("value", ""))}</p>'
        f'<blockquote class="ev-anchor">{_e((p or {}).get("anchor", ""))}</blockquote>'
        '<p class="ev-meta">'
        f'<span class="ev-loc">{_e((p or {}).get("location", ""))}</span>'
        f'<span class="ev-speaker">{_e((p or {}).get("speaker_or_author", ""))}</span>'
        "</p></div>"
        for p in candidate.get("positions") or []
    )
    return (
        '<article class="conflict"><header class="conflict-head">'
        f"<h3>{_bil(_e(label_el), _e(label_en))}</h3>"
        f'<span class="chip">{len(candidate.get("sources") or [])} '
        + _bil("πηγές", "sources")
        + "</span></header>"
        f'<div class="positions">{positions}</div></article>'
    )


def _conflict_section(data: dict) -> str:
    conflicts = data.get("conflicts") or {}
    candidates = conflicts.get("cross_source_candidates") or []
    internal = conflicts.get("internal_conflicts") or []
    note = conflicts.get("note")
    if not data.get("conflicts"):
        body = (
            '<p class="empty-field">'
            + _bil("Η διασταύρωση δεν έτρεξε σε αυτό το run.", "The conflict pass did not run.")
            + "</p>"
        )
    else:
        body = (f'<p class="sec-note">{_e(note)}</p>' if note else "") + (
            "".join(_candidate_card(c) for c in candidates)
            or '<p class="empty-field">'
            + _bil("Καμία υποψήφια σύγκρουση.", "No conflict candidates.")
            + "</p>"
        )
        if internal:
            body += (
                f"<h3>{_bil('Εντός μίας πηγής', 'Within a single source')}"
                f' <span class="field-count">{len(internal)}</span></h3>'
            )
            for item in internal:
                item = item or {}
                field = str(item.get("field", ""))
                label_el, label_en = FIELD_LABELS.get(field, (field, field))
                pair = "".join(
                    '<div class="position">'
                    f'<p class="pos-statement">{_e((v or {}).get("value", ""))}</p>'
                    f'<blockquote class="ev-anchor">{_e((v or {}).get("anchor", ""))}</blockquote>'
                    '<p class="ev-meta">'
                    f'<span class="ev-loc">{_e((v or {}).get("location", ""))}</span>'
                    f'<span class="ev-speaker">{_e((v or {}).get("speaker_or_author", ""))}</span>'
                    "</p></div>"
                    for v in (item.get("value_a"), item.get("value_b"))
                )
                body += (
                    '<article class="conflict"><header class="conflict-head">'
                    f"<h3>{_bil(_e(label_el), _e(label_en))}</h3>"
                    f'<span class="chip">{_e(item.get("source_id", ""))}</span>'
                    f"</header><div class=\"positions\">{pair}</div></article>"
                )
    return (
        '<section id="conflict-pass"><h2>'
        + _bil(
            "Διασταύρωση πηγών — υποψήφιες συγκρούσεις",
            "Cross-source pass — conflict candidates",
        )
        + "</h2>"
        + body
        + "</section>"
    )


def _synthesis_section(data: dict) -> str:
    brief = data.get("brief")
    if not isinstance(brief, dict):
        body = (
            '<p class="empty-field">'
            + _bil(
                "Η σύνθεση δεν έτρεξε σε αυτό το run — δεν υπάρχει brief.",
                "Synthesis did not run — there is no brief for this run.",
            )
            + "</p>"
        )
        return (
            '<section id="synthesis"><h2>'
            + _bil("Σύνθεση & ετοιμότητα", "Synthesis & readiness")
            + "</h2>"
            + body
            + "</section>"
        )
    readiness = brief.get("readiness") or {}
    ready = readiness.get("verdict") == "ready_for_review"
    verdict = (
        _bil("ΕΤΟΙΜΟ ΓΙΑ ΕΛΕΓΧΟ", "READY FOR REVIEW")
        if ready
        else _bil("ΑΝΕΠΑΡΚΗ ΣΤΟΙΧΕΙΑ", "THIN INPUT")
    )
    stats = (
        f'<span class="verdict {"ok" if ready else "warn"}">{verdict}</span>'
        f'<span class="stat"><strong>{_e(readiness.get("fields_with_evidence", "—"))}/7</strong> '
        + _bil("πεδία με τεκμηρίωση", "fields evidenced")
        + "</span>"
        f'<span class="stat"><strong>{_pct(readiness.get("low_confidence_share", 0))}%</strong> '
        + _bil("χαμηλής βεβαιότητας", "low-confidence")
        + "</span>"
        f'<span class="stat"><strong>{len(brief.get("conflicts") or [])}</strong> '
        + _bil("συγκρούσεις", "conflicts")
        + "</span>"
        f'<span class="stat"><strong>{len(brief.get("open_questions") or [])}</strong> '
        + _bil("ανοιχτές ερωτήσεις", "open questions")
        + "</span>"
    )
    links = ""
    if data.get("has_brief_page"):
        links += (
            '<a class="cta" href="brief_review.html">'
            + _bil("Άνοιγμα σελίδας ελέγχου brief", "Open the brief review page")
            + "</a>"
        )
    renders = data["renders"]
    if renders.get("el_view"):
        links += '<a class="doc-link" href="brief_el.html">' + _bil(
            "Έγγραφο πελάτη (ΕΛ)", "Client document (EL)"
        ) + "</a>"
    elif renders.get("el"):
        links += '<a class="doc-link" href="brief_el.md"><span class="mono">brief_el.md</span></a>'
    if renders.get("en_view"):
        links += '<a class="doc-link" href="brief_en.html">' + _bil(
            "Έγγραφο πελάτη (EN)", "Client document (EN)"
        ) + "</a>"
    elif renders.get("en"):
        links += '<a class="doc-link" href="brief_en.md"><span class="mono">brief_en.md</span></a>'
    return (
        '<section id="synthesis"><h2>'
        + _bil("Σύνθεση & ετοιμότητα", "Synthesis & readiness")
        + f'</h2><div class="health synth-health">{stats}</div>'
        + (f'<div class="cta-row">{links}</div>' if links else "")
        + "</section>"
    )


def _run_header(data: dict) -> str:
    run = data["run"]
    classification = data.get("classification") or {}
    brief_meta = (data.get("brief") or {}).get("meta") or {}
    client = (
        _prettify(brief_meta.get("client_id") or classification.get("client_id") or "")
        or _prettify(run.get("run_id") or "")
        or "Run"
    )
    started = _e(str(run.get("started_ts") or "")[:10])
    return (
        '<header class="masthead"><div class="mast-top"><div class="mast-id">'
        '<p class="kicker">'
        + _bil("Εσωτερικο εγγραφο · διαδρομη του run", "Internal document · run walkthrough")
        + "</p>"
        f"<h1>{client}</h1>"
        '<p class="mast-sub">'
        + _bil("Από τις πηγές στο brief", "From the sources to the brief")
        + f' · <span class="mono">{_e(run.get("run_id", ""))}</span> · {started}</p>'
        "</div>"
        '<div class="lang-switch" role="group" aria-label="language">'
        '<button type="button" class="lang-btn" data-set-lang="el" aria-pressed="true">ΕΛ</button>'
        '<button type="button" class="lang-btn" data-set-lang="en" aria-pressed="false">EN</button>'
        "</div></div>"
        '<div class="health">'
        + _outcome_chip(str(run.get("outcome") or ""), bool(run.get("demo_profile")))
        + f'<span class="stat"><strong>{len(run.get("sources") or [])}</strong> '
        + _bil("πηγές", "sources")
        + "</span>"
        + (
            f'<span class="stat">{_e(classification.get("project_type", ""))}'
            f' · {_e(classification.get("sensitivity_tier", ""))}</span>'
            if classification
            else ""
        )
        + "</div></header>"
    )


def _run_footer(data: dict) -> str:
    run = data["run"]
    return (
        '<footer><p class="colophon">'
        + _bil(
            "Παρήχθη ντετερμινιστικά από τα αρχεία του run — η σελίδα δεν μπορεί να "
            "πει τίποτα που δεν λένε τα αρχεία.",
            "Generated deterministically from the run's artifact files — this page "
            "cannot say anything the files do not say.",
        )
        + f' <span class="mono">{_e(run.get("project_name", ""))}'
        f' · {_e(run.get("pipeline_version", ""))}</span></p></footer>'
    )


_RUN_CSS = """
.journey { margin: 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap;
  gap: 0.6rem; }
.jstep { display: flex; align-items: center; gap: 0.6rem; background: var(--card);
  border: 1px solid var(--line); border-radius: 999px; padding: 0.45rem 0.95rem 0.45rem 0.5rem; }
.jstep-no { width: 1.7rem; height: 1.7rem; border-radius: 999px; background: var(--bg-soft);
  color: var(--ink-2); font-size: 0.8rem; font-weight: 700; display: flex;
  align-items: center; justify-content: center; flex: none; }
.jstep.ok .jstep-no { background: var(--ok-bg); color: var(--ok); }
.jstep.warn .jstep-no { background: var(--warn-bg); color: var(--warn); }
.jstep.bad .jstep-no { background: var(--bad-bg); color: var(--bad); }
.jstep-body { display: flex; flex-direction: column; line-height: 1.25; }
.jstep-name { font-size: 0.85rem; font-weight: 600; }
.jstep-status { font-size: 0.72rem; color: var(--ink-2); }
.jstep.warn .jstep-status { color: var(--warn); }
.jstep.bad .jstep-status { color: var(--bad); }
.chip.outcome-ok { background: var(--ok-bg); color: var(--ok); }
.chip.outcome-warn { background: var(--warn-bg); color: var(--warn); }
.chip.outcome-bad { background: var(--bad-bg); color: var(--bad); }
.chip.outcome-other, .chip-demo { border: 1px solid var(--line); color: var(--ink-2); }
.src-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(21rem, 1fr));
  gap: 1rem; }
.src-card { background: var(--card); border: 1px solid var(--line); border-radius: 16px;
  padding: 1.05rem 1.15rem; box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  transition: box-shadow 0.15s ease; min-width: 0; }
.src-card:hover { box-shadow: 0 5px 16px rgba(0,0,0,0.1); }
.src-head { display: flex; gap: 0.75rem; align-items: center; }
.src-icon { width: 2.6rem; height: 2.6rem; border-radius: 12px; background: var(--bg-soft);
  display: flex; align-items: center; justify-content: center; font-size: 1.2rem;
  flex: none; }
.src-id h3 { margin: 0; font-size: 1.02rem; font-weight: 700; }
.src-meta { margin: 0.1rem 0 0; font-size: 0.8rem; color: var(--ink-2); }
.src-stats { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.8rem 0 0.2rem; }
.x-item { border-top: 1px solid var(--line); padding: 0.65rem 0; }
.x-head { display: flex; justify-content: space-between; gap: 0.7rem;
  align-items: flex-start; flex-wrap: wrap; }
.x-value { margin: 0; font-size: 0.9rem; font-weight: 600; flex: 1 1 14rem; }
#sources h4 { margin: 1rem 0 0.2rem; font-size: 0.82rem; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--ink-2); display: flex; align-items: baseline;
  gap: 0.45rem; }
.notes { margin: 0.5rem 0 0; padding-left: 1.1rem; }
.notes li { font-size: 0.85rem; color: var(--ink-2); margin-bottom: 0.35rem; }
.raw-doc { background: var(--bg-soft); border: 1px solid var(--line); border-radius: 12px;
  padding: 0.9rem 1rem; font-size: 0.78rem; line-height: 1.5; white-space: pre-wrap;
  overflow-wrap: anywhere; max-height: 24rem; overflow-y: auto; }
.sec-note { color: var(--ink-2); font-size: 0.88rem; max-width: 46rem;
  margin: -0.4rem 0 1.1rem; }
.synth-health { padding: 0 0 0.4rem; max-width: none; }
.cta-row { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: center;
  margin-top: 0.6rem; }
.cta { background: var(--brand); color: #ffffff; text-decoration: none; font-weight: 600;
  font-size: 0.9rem; border-radius: 999px; padding: 0.7rem 1.25rem; }
.cta:hover { filter: brightness(0.94); }
.doc-link { color: var(--ink); font-size: 0.85rem; text-decoration: underline;
  text-underline-offset: 3px; border: 1px solid var(--line); border-radius: 999px;
  padding: 0.55rem 0.95rem; text-decoration: none; }
.doc-link:hover { background: var(--bg-soft); }
"""


def render_run_review(data: dict) -> str:
    """Pure function: collected run-artifact dict in, complete HTML document out."""
    run = data.get("run") or {}
    classification = data.get("classification") or {}
    brief_meta = (data.get("brief") or {}).get("meta") or {}
    client = (
        _prettify(brief_meta.get("client_id") or classification.get("client_id") or "")
        or _prettify(run.get("run_id") or "")
        or "Run"
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="el" data-lang="el">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{client} — Run review</title>\n"
        f"<style>{THEME_CSS}{_PAGE_CSS}{_RUN_CSS}</style>\n</head>\n<body>\n"
        + _run_header(data)
        + "<main>"
        + _journey(run)
        + _sources_section(data)
        + _conflict_section(data)
        + _synthesis_section(data)
        + "</main>"
        + _run_footer(data)
        + f"<script>{PAGE_JS}</script>\n</body>\n</html>\n"
    )


def write_run_review(run_dir) -> Path:
    """Collect ``run_dir``'s artifacts, emit ``run_dir/run_review.html``, return its path."""
    run_dir = Path(run_dir)
    page = render_run_review(collect_run(run_dir))
    out_path = run_dir / "run_review.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Emit the deterministic pipeline walkthrough page for one run."
    )
    parser.add_argument("run_dir", help="run directory containing run_manifest.json")
    args = parser.parse_args(argv)
    try:
        out_path = write_run_review(args.run_dir)
    except ReviewInputError as exc:
        print(f"run-review: {exc}", file=sys.stderr)
        return 1
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
