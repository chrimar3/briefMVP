"""eval/supplementary.py — an unfrozen, report-only scorer for the frozen harness's blind spots.

    python3 eval/supplementary.py runs/tier3 [runs/voreas-prep-03 ...] [--json]

eval/harness.py is frozen (CLAUDE.md rule 2) and grades recall against an answer key. Several of
its checks can pass while a reader-visible defect ships (docs/EVAL_RECORD.md §4). This tool looks
at exactly those gaps, from the run's own artifacts and the project's sources — it NEVER reads an
answer key (sources come from pipeline.gates.discover_sources, which skips HARNESS_ONLY_FILES).

Checks (each is a heuristic and reports; none is a gate):

  S1 speculative_coverage   conditional extract items that never reach the brief as conditional —
                            frozen X2 passes "not present in draft" when the item is simply dropped
  S2 stale_questions        open questions in a field whose conflict a human already resolved
  S3 garble_visibility      ASR-garbled tokens (fidelity annotations) resolved silently in brief
                            content, or absent from both renders — frozen T3.3 also greps anchors
  S4 citation_content       distinctive content (hyphenated compounds, quoted phrases, glossary
                            terms) absent from the cited source line(s) — cross-source or unsourced
  S5 duplicate_questions    open questions that duplicate each other, or re-ask an open conflict
  S6 creative_currency      currency/unit amounts in creative drafts absent from the brief's text
  S7 creative_spec_tokens   spec tokens on `[spec: id]` lines (ratio, resolution, duration, file
                            type) not byte-identical to the cited row of config/channel_specs.json
  S8 glossary_coverage      protected (keep_latin) terms from the project's own glossary checked
                            char-exact in both renders; zero terms checked = vacuous (frozen T2.5
                            reads only glossary/*.json)
  S9 hedge_drift            decade-range phrasing ("in the eighties") for a spoken figure, which
                            SYNTHESIS.md rule 2 renders as "around <n> (units unstated)"

Exit code: 0 whenever the run could be read (findings never fail the command); 2 on unreadable input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from pipeline import gates  # noqa: E402

SPEC_TABLE = REPO_ROOT / "config" / "channel_specs.json"
CREATIVE_BANNERS = ("SHADOW MODE", "CREATIVE DRAFT", "APPROVED FOR DELIVERY")
FIDELITY_MATCH_RE = re.compile(r'\[FIDELITY:\s*glossary-match\s+"([^"]+)"[^\]]*\]')
QUOTED_RE = re.compile(r"(?<![A-Za-z])'([^']{3,})'(?![A-Za-z])|\"([^\"]{3,})\"|«([^»]{3,})»|“([^”]{3,})”")
HYPHENATED_RE = re.compile(r"\b[A-Za-z]{2,}(?:-[A-Za-z]{2,})+\b")
DECADE_RE = re.compile(r"\bin the (twenties|thirties|forties|fifties|sixties|seventies|eighties|nineties)\b",
                       re.IGNORECASE)
_NUM = r"\d(?:[\d.,]*\d)?"
MONEY_RE = re.compile(
    rf"(?:€|EUR\s?)\s?{_NUM}(?:\s?[–—-]\s?{_NUM})?\s?(?:k|K|m|M|χιλ\.?)?(?![\w])"
    rf"|\b{_NUM}(?:\s?[–—-]\s?{_NUM})?\s?(?:k|K)\b"
    rf"|\b{_NUM}(?:\s?[–—-]\s?{_NUM})?\s?(?:EUR|euros?|ευρώ)\b"
)
SPEC_REF_RE = re.compile(r"\[spec:\s*([^\]\s]+)\s*\]")
SPEC_TOKEN_RES = (
    ("resolution", re.compile(r"\b\d{3,4}\s?[x×]\s?\d{3,4}\b")),
    ("aspect_ratio", re.compile(r"(?<![\d:])\d{1,2}:\d{1,2}(?![\d:])")),
    ("duration", re.compile(r"\b(?:up to\s)?\d+(?:\s?[-–—]\s?\d+)?\s?s\b")),
)
FILE_TYPES = ("MP4", "MOV", "PNG", "JPG", "JPEG", "GIF", "PDF", "TIFF", "PSD", "WEBP", "SVG")


# --------------------------------------------------------------------------------------
# Loading a run (answer keys are never read)
# --------------------------------------------------------------------------------------


def resolve_project(manifest: dict, override: Optional[Path] = None) -> Optional[Path]:
    if override:
        return Path(override)
    raw = manifest.get("project_dir")
    if not raw:
        return None
    path = Path(raw)
    candidates = [path] if path.is_absolute() else [REPO_ROOT / path]
    parts = path.parts
    if len(parts) >= 2:
        candidates.append(REPO_ROOT / parts[-2] / parts[-1])  # a manifest written on another checkout
    return next((c for c in candidates if c.is_dir()), None)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def load_run(run_dir: Path, project: Optional[Path] = None) -> dict:
    run_dir = Path(run_dir)
    manifest = _load_json(run_dir / "run_manifest.json") or {}
    project_dir = resolve_project(manifest, project)
    sources = {s.source_id: s.text for s in gates.discover_sources(project_dir)} if project_dir else {}
    creative = {}
    for path in sorted((run_dir / "creative").glob("*.md")) if (run_dir / "creative").is_dir() else []:
        text = path.read_text(encoding="utf-8")
        first = text.splitlines()[0] if text.splitlines() else ""
        if any(b in first for b in CREATIVE_BANNERS):
            creative[path.name] = text
    annotated = {}
    fid = run_dir / "fidelity"
    for path in sorted(fid.glob("*.annotated.md")) if fid.is_dir() else []:
        annotated[path.name[: -len(".annotated.md")]] = path.read_text(encoding="utf-8")
    return {
        "run_dir": run_dir, "manifest": manifest, "project_dir": project_dir, "sources": sources,
        "brief": _load_json(run_dir / "brief.json"),
        "renders": {lang: (run_dir / f"brief_{lang}.md").read_text(encoding="utf-8")
                    for lang in ("el", "en") if (run_dir / f"brief_{lang}.md").is_file()},
        "extracts": {p.stem: json.loads(p.read_text(encoding="utf-8"))
                     for p in sorted((run_dir / "extracts").glob("*.json"))} if (run_dir / "extracts").is_dir() else {},
        "annotated": annotated, "creative": creative,
        "glossary": load_glossary(project_dir, (_load_json(run_dir / "brief.json") or {}).get("meta", {})),
    }


def load_glossary(project_dir: Optional[Path], meta: dict) -> dict:
    """The project's own glossary: a client_*.json / glossary.json in the project folder, else the
    repo glossary whose client_id matches the brief. Returns {} when none applies."""
    if project_dir:
        for pattern in ("client_*.json", "glossary.json"):
            for path in sorted(project_dir.glob(pattern)):
                data = _load_json(path)
                if isinstance(data, dict) and data.get("terms"):
                    return {**data, "_path": str(path)}
    client = meta.get("client_id")
    for path in sorted((REPO_ROOT / "glossary").glob("*.json")):
        data = _load_json(path)
        if isinstance(data, dict) and client and data.get("client_id") == client:
            return {**data, "_path": str(path)}
    return {}


def _norm(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("‐", "-").replace("-", " ")
    return " ".join(re.sub(r"[^\w' ]+", " ", text.lower()).split())


def _entries(brief: dict) -> list:
    return [(f, i, e) for f in gates.BRIEF_FIELDS for i, e in enumerate(brief.get(f) or [])]


def brief_text(brief: dict) -> str:
    """Every reader-facing string in the brief: entry content, conflicts, questions, sign-off."""
    parts = [e.get("content") or "" for _f, _i, e in _entries(brief)]
    for c in brief.get("conflicts") or []:
        parts += [p.get("statement") or "" for p in c.get("positions") or []]
        parts += [c.get("resolution") or ""]
    for q in brief.get("open_questions") or []:
        parts += [q.get(k) or "" for k in ("gap", "why_it_matters", "suggested_question_for_client")]
    parts.append((brief.get("signoff") or {}).get("edits_summary") or "")
    return "\n".join(parts)


def cited_span(source_text: str, anchor: str) -> str:
    """The full source line(s) holding a verbatim anchor; the anchor itself if it is not found."""
    idx = source_text.find(anchor) if anchor else -1
    if idx < 0:
        return anchor or ""
    start = source_text.rfind("\n", 0, idx) + 1
    end = source_text.find("\n", idx + len(anchor))
    return source_text[start: end if end >= 0 else len(source_text)]


def _finding(check: str, status: str, detail: str, items: Optional[list] = None, **extra) -> dict:
    return {"check": check, "status": status, "detail": detail, "items": items or [], **extra}


# --------------------------------------------------------------------------------------
# S1–S9
# --------------------------------------------------------------------------------------


def check_speculative_coverage(run: dict) -> dict:
    name = "S1 speculative_coverage"
    brief = run["brief"]
    if not brief or not run["extracts"]:
        return _finding(name, "n/a", "needs extracts and a brief")
    conditional = [(sid, f, i, it) for sid, ex in run["extracts"].items() for f in gates.BRIEF_FIELDS
                   for i, it in enumerate(ex.get(f) or []) if it.get("qualifier") == "conditional"]
    brief_cond = [(f, i, e) for f, i, e in _entries(brief) if e.get("qualifier") == "conditional"]
    missing, demoted = [], []
    for sid, f, i, it in conditional:
        carriers = [(bf, bi, be) for bf, bi, be in _entries(brief)
                    if any(r.get("source_id") == sid and (r.get("location") == it.get("location")
                           or (r.get("anchor") and r.get("anchor") in (it.get("anchor") or "")))
                           for r in be.get("evidence") or [])]
        in_conflict = any((pos.get("evidence") or {}).get("source_id") == sid
                          and (pos.get("evidence") or {}).get("location") == it.get("location")
                          for c in brief.get("conflicts") or [] for pos in c.get("positions") or [])
        if not carriers and not in_conflict:
            missing.append(f"{sid}.{f}[{i}] {it.get('location')}: no brief entry or conflict position cites it")
        elif carriers and not any(be.get("qualifier") == "conditional" for _bf, _bi, be in carriers):
            demoted.append(f"{sid}.{f}[{i}] {it.get('location')}: reaches "
                           f"{', '.join(f'{bf}[{bi}]' for bf, bi, _ in carriers)} without the conditional qualifier")
    items = missing + demoted
    detail = (f"{len(conditional)} conditional extract item(s); {len(brief_cond)} conditional brief entr(ies); "
              f"{len(missing)} dropped, {len(demoted)} de-hedged")
    if items:
        return _finding(name, "flag", detail, items)
    if not conditional:
        return _finding(name, "vacuous", detail + " — nothing speculative to check")
    return _finding(name, "ok", detail)


def check_stale_questions(run: dict) -> dict:
    name = "S2 stale_questions"
    brief = run["brief"]
    if not brief:
        return _finding(name, "n/a", "needs a brief")
    resolved = {c.get("field") for c in brief.get("conflicts") or [] if c.get("status") == "resolved_by_human"}
    items = [f"open_questions[{i}] ({q.get('field')}): {(q.get('gap') or '')[:110]}"
             for i, q in enumerate(brief.get("open_questions") or []) if q.get("field") in resolved]
    signed = (brief.get("signoff") or {}).get("status") == "signed_off"
    detail = (f"{len(resolved)} field(s) with a human-resolved conflict; {len(items)} question(s) still "
              f"open in them{' under a signed-off brief' if signed else ''}")
    return _finding(name, "flag" if items else ("ok" if resolved else "vacuous"), detail, items)


def garbled_tokens(run: dict) -> dict:
    """{source_id: [(token, proposal)]} from the fidelity annotations. The token is the longest
    run of 1–4 words before the annotation that an extraction note quotes; failing that, the two
    words before it (labelled heuristic in the output)."""
    out: dict = {}
    for sid, text in run["annotated"].items():
        notes = " ".join((run["extracts"].get(sid) or {}).get("extraction_notes") or [])
        for m in FIDELITY_MATCH_RE.finditer(text):
            proposal = m.group(1)
            before = text[: m.start()].splitlines()[-1] if text[: m.start()].splitlines() else ""
            words = re.findall(r"[^\s«»\"'().,;:!?—]+", before)
            token, basis = None, "heuristic: two words before the annotation"
            for k in (4, 3, 2, 1):
                cand = " ".join(words[-k:])
                if cand and len(words) >= k and re.search(rf"['«\"]{re.escape(cand)}['»\"]", notes):
                    token, basis = cand, "quoted in an extraction note"
                    break
            if token is None:
                token = " ".join(words[-2:])
            out.setdefault(sid, []).append({"token": token, "proposal": proposal, "basis": basis})
    return out


def check_garble_visibility(run: dict) -> dict:
    name = "S3 garble_visibility"
    brief = run["brief"]
    garbles = garbled_tokens(run)
    if not brief or not garbles:
        return _finding(name, "n/a" if not brief else "vacuous", "needs a brief and fidelity annotations"
                        if not brief else "no fidelity glossary-match annotations in this run")
    items, checked = [], 0
    for sid, found in garbles.items():
        for g in found:
            checked += 1
            tok = g["token"]
            anchored = [(f, i, e) for f, i, e in _entries(brief)
                        if any(r.get("source_id") == sid and tok in (r.get("anchor") or "")
                               for r in e.get("evidence") or [])]
            in_conflict = any(tok in ((pos.get("evidence") or {}).get("anchor") or "")
                              for c in brief.get("conflicts") or [] for pos in c.get("positions") or [])
            if not anchored and not in_conflict:
                items.append(f"«{tok}» ({g['proposal']!r}): no brief entry or conflict carries the garbled line")
            for f, i, e in anchored:
                if tok not in (e.get("content") or ""):
                    items.append(f"{f}[{i}] (confidence {e.get('confidence')}): content drops ASR token "
                                 f"«{tok}» for {g['proposal']!r} with no visible flag")
            for lang, text in run["renders"].items():
                if tok not in text:
                    items.append(f"brief_{lang}.md: «{tok}» absent — reader sees only the normalised term")
    return _finding(name, "flag" if items else "ok", f"{checked} garbled token(s) from fidelity annotations",
                    items, tokens=garbles)


def check_citation_content(run: dict) -> dict:
    name = "S4 citation_content"
    brief = run["brief"]
    if not brief or not run["sources"]:
        return _finding(name, "n/a", "needs a brief and the project sources")
    keep_latin = [t["term"] for t in (run["glossary"].get("terms") or []) if t.get("rule") == "keep_latin"]
    garbles = garbled_tokens(run)
    all_sources = {sid: _norm(text) for sid, text in run["sources"].items()}
    items, checked = [], 0
    for f, i, e in _entries(brief):
        refs = e.get("evidence") or []
        spans = [cited_span(run["sources"].get(r.get("source_id"), ""), r.get("anchor") or "") for r in refs]
        cited = _norm(" ".join(spans))
        cited_ids = {r.get("source_id") for r in refs}
        content = e.get("content") or ""
        probes = [("compound", h) for h in HYPHENATED_RE.findall(content)]
        for groups in QUOTED_RE.findall(content):
            quote = next(g for g in groups if g)
            probes += [("quote", frag) for frag in re.split(r"[,;:—–!?.…]+", quote)
                       if len(frag.split()) >= 3]
        # Single lowercase glossary words ("launch") are ordinary vocabulary in English content;
        # only names, acronyms and multi-word terms are distinctive enough to probe.
        # A term present in at least half of the sources (the client or product name) is project
        # context, not a clause borrowed from somewhere else.
        probes += [("glossary", t) for t in keep_latin if t.lower() in content.lower()
                   and (" " in t or not t.islower())
                   and sum(_norm(t) in text for text in all_sources.values()) * 2 < len(all_sources)]
        for kind, probe in probes:
            np = _norm(probe)
            if not np:
                continue
            checked += 1
            if np in cited:
                continue
            if kind == "glossary" and any(g["proposal"].lower() == probe.lower() and g["token"] in " ".join(spans)
                                          for sid in cited_ids for g in garbles.get(sid, [])):
                continue  # an ASR garble of this term sits in the cited line — S3 reports visibility
            elsewhere = sorted(sid for sid, text in all_sources.items() if np in text and sid not in cited_ids)
            if kind == "compound" and not elsewhere:
                continue  # an English compound translating Greek source text — not evidence of a mix-up
            where = (f"found only in {', '.join(elsewhere)}" if elsewhere else
                     "verbatim in no source (a translation shown in quotation marks, or invented)"
                     if kind == "quote" else "found in no source")
            items.append(f"{f}[{i}] cites {sorted(cited_ids)}: {kind} {probe!r} is not in the cited line(s); {where}")
    return _finding(name, "flag" if items else "ok", f"{checked} distinctive phrase(s) probed (heuristic)", items)


def _words(text: str) -> set:
    return {w for w in _norm(text).split() if len(w) > 3}


def check_duplicate_questions(run: dict, threshold: float = 0.6) -> dict:
    name = "S5 duplicate_questions"
    brief = run["brief"]
    if not brief:
        return _finding(name, "n/a", "needs a brief")
    qs = brief.get("open_questions") or []
    items = []
    for a in range(len(qs)):
        for b in range(a + 1, len(qs)):
            if qs[a].get("field") != qs[b].get("field"):
                continue
            wa = _words((qs[a].get("gap") or "") + " " + (qs[a].get("suggested_question_for_client") or ""))
            wb = _words((qs[b].get("gap") or "") + " " + (qs[b].get("suggested_question_for_client") or ""))
            jac = len(wa & wb) / len(wa | wb) if wa | wb else 0.0
            if jac >= threshold:
                items.append(f"open_questions[{a}] ~ open_questions[{b}] ({qs[a].get('field')}): word overlap {jac:.2f}")
    for i, q in enumerate(qs):
        q_refs = {(r.get("source_id"), r.get("anchor")) for r in q.get("linked_evidence") or q.get("evidence") or []}
        for c_idx, c in enumerate(brief.get("conflicts") or []):
            if c.get("status") != "open" or c.get("field") != q.get("field"):
                continue
            c_refs = {((p.get("evidence") or {}).get("source_id"), (p.get("evidence") or {}).get("anchor"))
                      for p in c.get("positions") or []}
            if q_refs & c_refs:
                items.append(f"open_questions[{i}] re-asks open conflicts[{c_idx}] ({c.get('field')}) — shared evidence")
    return _finding(name, "flag" if items else "ok",
                    f"{len(qs)} question(s); near-duplicate threshold {threshold} word overlap within a field", items)


def _money_norm(token: str) -> str:
    return re.sub(r"\s+", "", token).replace("—", "-").replace("–", "-")


def check_creative_currency(run: dict) -> dict:
    name = "S6 creative_currency"
    if not run["creative"]:
        return _finding(name, "n/a", "no creative drafts in this run")
    if not run["brief"]:
        return _finding(name, "n/a", "needs the brief the drafts were made from")
    allowed = {_money_norm(m) for m in MONEY_RE.findall(brief_text(run["brief"]))}
    items, checked = [], 0
    for fname, text in run["creative"].items():
        for n, line in enumerate(text.splitlines(), 1):
            for m in MONEY_RE.findall(line):
                checked += 1
                if _money_norm(m) not in allowed:
                    items.append(f"{fname}:{n}: {m.strip()!r} — no such amount in the brief")
    return _finding(name, "flag" if items else "ok", f"{checked} currency/unit amount(s) in creative drafts", items)


def check_creative_spec_tokens(run: dict, spec_table: Optional[dict] = None) -> dict:
    name = "S7 creative_spec_tokens"
    if not run["creative"]:
        return _finding(name, "n/a", "no creative drafts in this run")
    table = spec_table if spec_table is not None else json.loads(SPEC_TABLE.read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in table.get("specs") or []}
    items, checked = [], 0
    for fname, text in run["creative"].items():
        for n, line in enumerate(text.splitlines(), 1):
            refs = SPEC_REF_RE.findall(line)
            if not refs:
                continue
            values = set()
            for ref in refs:
                if ref not in rows:
                    items.append(f"{fname}:{n}: [spec: {ref}] is not a row of the spec table")
                    continue
                values |= {str(v) for k, v in rows[ref].items() if k not in ("id", "channel", "format")}
            tokens = [(kind, m) for kind, rx in SPEC_TOKEN_RES for m in rx.findall(line)]
            tokens += [("file_type", ft) for ft in FILE_TYPES if re.search(rf"\b{ft}\b", line)]
            for kind, tok in tokens:
                checked += 1
                if tok not in values:
                    items.append(f"{fname}:{n}: {kind} {tok!r} is not byte-identical to "
                                 f"[spec: {', '.join(refs)}] ({sorted(values)})")
    return _finding(name, "flag" if items else "ok", f"{checked} spec token(s) on [spec: …] lines", items)


def check_glossary_coverage(run: dict) -> dict:
    name = "S8 glossary_coverage"
    if not run["brief"] or len(run["renders"]) < 2:
        return _finding(name, "n/a", "needs a brief and both renders")
    terms = [t["term"] for t in (run["glossary"].get("terms") or []) if t.get("rule") == "keep_latin"]
    blob = brief_text(run["brief"])
    in_brief = [t for t in terms if t in blob]
    items = [f"brief_{lang}.md: {t!r} is in the brief but not character-exact in the render"
             for t in in_brief for lang, text in run["renders"].items() if t not in text]
    src = run["glossary"].get("_path", "none")
    detail = f"{len(in_brief)} of {len(terms)} keep_latin term(s) from {src} used in the brief and checked"
    if not in_brief:
        return _finding(name, "vacuous", detail + " — nothing to check")
    return _finding(name, "flag" if items else "ok", detail, items)


def check_hedge_drift(run: dict) -> dict:
    name = "S9 hedge_drift"
    if not run["brief"]:
        return _finding(name, "n/a", "needs a brief")
    texts = {"brief.json": brief_text(run["brief"]), **{f"brief_{k}.md": v for k, v in run["renders"].items()},
             **run["creative"]}
    items = [f"{where}: {m.group(0)!r}" for where, text in texts.items() for m in DECADE_RE.finditer(text)]
    return _finding(name, "flag" if items else "ok", f"{len(items)} decade-range rendering(s) of a spoken figure",
                    items)


CHECKS = (check_speculative_coverage, check_stale_questions, check_garble_visibility, check_citation_content,
          check_duplicate_questions, check_creative_currency, check_creative_spec_tokens,
          check_glossary_coverage, check_hedge_drift)


def score(run_dir: Path, project: Optional[Path] = None) -> dict:
    run = load_run(run_dir, project)
    results = [check(run) for check in CHECKS]
    return {"run": Path(run_dir).name, "project_dir": str(run["project_dir"]) if run["project_dir"] else None,
            "results": results,
            "summary": {s: sum(1 for r in results if r["status"] == s) for s in ("flag", "vacuous", "ok", "n/a")}}


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description="Report-only scorer for the frozen harness's blind spots.")
    p.add_argument("runs", nargs="+")
    p.add_argument("--project", help="project folder (default: from run_manifest.json)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    reports = []
    for run_dir in args.runs:
        if not Path(run_dir).is_dir():
            print(f"[supplementary] {run_dir} is not a directory", file=sys.stderr)
            return 2
        reports.append(score(Path(run_dir), Path(args.project) if args.project else None))
    if args.json:
        print(json.dumps(reports, indent=2, ensure_ascii=False))
        return 0
    for rep in reports:
        s = rep["summary"]
        print(f"\n{rep['run']} — supplementary (report-only): {s['flag']} flag, {s['vacuous']} vacuous, "
              f"{s['ok']} ok, {s['n/a']} n/a   [project: {rep['project_dir']}]")
        for r in rep["results"]:
            print(f"  {r['status'].upper():<8}{r['check']:<26}{r['detail']}")
            for item in r["items"]:
                print(f"            - {item}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
