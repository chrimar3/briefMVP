"""Live demo: one document in, verified facts out.

Runs the pipeline's evidence layer only — classify → extract → deterministic verification
gates — on a single text file (or stdin). No synthesis, no renders: what this shows is the
part that makes everything downstream trustworthy, in a couple of minutes:

    python demo/run_demo.py fixtures/northlight_01/transcript_kickoff.md
    cat some_meeting_notes.txt | python demo/run_demo.py -

Every printed fact carries its exact source quote; anything the document does not state
becomes an open question, never a plausible value. Uses the same subagent transport as the
graded tier-3 run — needs only that transport configured (no keys are read or printed here).

Input is capped at ~800 words (the demo is a conversation, not a batch job). A file whose
type cannot be inferred from strong signals is refused with instructions, not guessed —
same ethos as the pipeline (`--type transcript|rfp|email_thread|background` overrides).
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import agents, extraction, gates, intake, stages  # noqa: E402

MAX_WORDS = 800


def _read_input(arg: str) -> tuple[str, str]:
    if arg == "-":
        return sys.stdin.read(), "stdin"
    path = Path(arg)
    if not path.is_file():
        sys.exit(f"[demo] no such file: {arg}")
    return path.read_text(encoding="utf-8"), path.name


def _cap_words(text: str, limit: int) -> tuple[str, int, bool]:
    """Cap the body at `limit` words, never cutting a header line."""
    lines = text.splitlines()
    head: list[str] = []
    if lines and lines[0].startswith("#"):
        head.append(lines.pop(0))
    while lines and ("source_id:" in lines[0] or not lines[0].strip()):
        head.append(lines.pop(0))
    body = "\n".join(lines)
    words = body.split()
    if len(words) <= limit:
        return text, len(words), False
    kept, count = [], 0
    for line in lines:
        line_words = len(line.split())
        if count + line_words > limit:
            break
        kept.append(line)
        count += line_words
    return "\n".join(head + kept), count, True


def _stamp(text: str, name: str, type_override: str | None) -> tuple[str, dict]:
    """Return (stamped_text, header_meta) — existing compliant headers pass through."""
    try:
        meta = gates.parse_source_header(text, Path(name))
        return text, meta
    except gates.InputContractError:
        pass
    fake = Path(name if name != "stdin" else "demo_input.txt")
    stype = type_override or intake.infer_source_type(fake, text)
    if stype is None:
        sys.exit(
            "[demo] cannot infer what this document is (no transcript timestamps, no email "
            "headers, no RFP marker) — the pipeline refuses to guess. "
            "Re-run with --type transcript|rfp|email_thread|background."
        )
    if stype not in gates.VALID_SOURCE_TYPES:
        sys.exit(f"[demo] --type must be one of {list(gates.VALID_SOURCE_TYPES)}")
    sdate = intake._ISO_DATE_RE.search(text[:2000])
    meta = {
        "source_id": "demo_input",
        "source_type": stype,
        "source_date": sdate.group(1) if sdate else datetime.now().strftime("%Y-%m-%d"),
    }
    header = (f"# Demo input\nsource_id: {meta['source_id']} · source_type: "
              f"{meta['source_type']} · source_date: {meta['source_date']}\n\n")
    return header + text, meta


def _cell(text: str, width: int) -> str:
    text = " ".join((text or "").split())
    return (text[: width - 1] + "…") if len(text) > width else text.ljust(width)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="One document in, verified facts out.")
    parser.add_argument("input", help="a text/markdown file, or '-' for stdin")
    parser.add_argument("--type", default=None, help="source type when it cannot be inferred")
    parser.add_argument("--glossary", default=None,
                        help="client config path (default: the single file in glossary/)")
    parser.add_argument("--max-words", type=int, default=MAX_WORDS)
    parser.add_argument("--retries", type=int, default=2,
                        help="extra extraction legs after a gate refusal (each leg already "
                             "carries one internal repair attempt); refusals are printed, "
                             "never hidden — a refusal is the citation gate rejecting a "
                             "fabricated quote, i.e. the product working")
    args = parser.parse_args(argv)

    started = time.monotonic()
    raw, name = _read_input(args.input)
    stamped, meta = _stamp(raw, name, args.type)
    stamped, word_count, capped = _cap_words(stamped, args.max_words)

    run_dir = gates.REPO_ROOT / "runs" / f"demo-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    source_path = run_dir / f"{meta['source_id']}.md"
    source_path.write_text(stamped, encoding="utf-8")

    glossary_path = extraction.resolve_glossary(Path(args.glossary) if args.glossary else None)
    client_config = extraction.load_client_config(glossary_path)
    source = gates.SourceDoc(meta["source_id"], meta["source_type"], meta["source_date"],
                             source_path, stamped)
    access_dirs = [str(run_dir), str(gates.SCHEMA_DIR), str(Path(glossary_path).parent),
                   str(gates.REPO_ROOT / "templates"), str(gates.CONFIG_DIR)]

    print(f"Brief Builder — live demo · {name} ({meta['source_type']}, {word_count} words"
          + (f", capped at {args.max_words}" if capped else "") + f")\n  output: {run_dir}\n")

    cost = 0.0
    print("[1/2] classify — what is this project, which onboarding tier applies…")
    try:
        classification = stages.classify([source], run_dir, "demo", client_config,
                                         glossary_path, access_dirs)
    except stages.HaltForHuman as exc:
        print(f"      HALTED FOR HUMAN (by design — it asks instead of guessing): {exc}")
        return 3
    except (gates.GateError, agents.SubagentError) as exc:
        print(f"      classification failed: {exc}")
        return 2
    cost += sum(a["subagent"].get("cost_usd") or 0 for a in classification["attempts"])
    print(f"      {classification['project_type']} · tier {classification['sensitivity_tier']} "
          f"(copied from client config, never inferred) · "
          f"confidence {classification['classification_confidence']}\n")

    print("[2/2] extract — every value must carry a verbatim quote or it does not exist…")
    outcome = None
    for leg in range(1, args.retries + 2):
        try:
            outcome = extraction.extract_source(source=source, run_dir=run_dir,
                                                project_id="demo", client_config=client_config,
                                                glossary_path=glossary_path,
                                                access_dirs=access_dirs)
            break
        except (gates.GateError, agents.SubagentError) as exc:
            print(f"      REFUSED by the verification gate, leg {leg}/{args.retries + 1} — a "
                  f"near-miss quote was rejected; this is the product working:\n      {exc}")
            if leg <= args.retries:
                print("      re-running the leg with a fresh model call…")
    if outcome is None:
        return 2
    cost += sum(a["subagent"].get("cost_usd") or 0 for a in outcome["attempts"])

    import json
    extract = json.loads(Path(outcome["output_file"]).read_text(encoding="utf-8"))

    # -- deterministic verification, recomputed here in front of the viewer ----------------
    gates.validate_extract(extract)
    items = [(f, item) for f in gates.BRIEF_FIELDS for item in (extract.get(f) or [])]
    resolved = sum(1 for _, i in items
                   if (i.get("anchor") or "") in stamped and (i.get("location") or "") in stamped)
    notes = [n for n in (extract.get("extraction_notes") or []) if n]
    notes += [i.get("extraction_note") for _, i in items if i.get("extraction_note")]

    print(f"\nFACTS the document actually states ({len(items)}):")
    header = (f"  {_cell('field', 12)} {_cell('value', 34)} {_cell('exact quote (anchor)', 34)} "
              f"{_cell('where', 14)} {_cell('conf', 6)} qualifier")
    print(header + "\n  " + "-" * (len(header) - 2))
    for fieldname, item in items:
        print(f"  {_cell(fieldname, 12)} {_cell(item.get('value'), 34)} "
              f"{_cell(item.get('anchor'), 34)} {_cell(item.get('location'), 14)} "
              f"{_cell(item.get('confidence'), 6)} {item.get('qualifier')}")

    print(f"\nVERIFICATION GATES (deterministic, no model):")
    print(f"  ✅ schema: extract validates against schema/extract_schema.json")
    print(f"  {'✅' if resolved == len(items) else '❌'} citations: {resolved}/{len(items)} "
          f"anchor+location strings occur verbatim in the source")
    if notes:
        print(f"  ⚠  {len(notes)} extraction note(s) — garbled/ambiguous tokens carried AS-IS, "
              f"never silently 'fixed':")
        for note in notes[:4]:
            print(f"       · {_cell(note, 100)}")

    questions = extract.get("open_questions") or []
    print(f"\nOPEN QUESTIONS created instead of guesses ({len(questions)}):")
    for q in questions:
        print(f"  · [{q.get('field')}] {q.get('suggested_question_for_client') or q.get('gap')}")

    # -- visual payoff: the same walkthrough page every full run gets ----------------------
    # The demo bypasses the runner, so write the minimal manifest the page renders from.
    # Best-effort by design: the view must never turn a successful demo into a failure.
    try:
        import os
        import subprocess
        from pipeline import run_review

        (run_dir / "run_manifest.json").write_text(json.dumps({
            "run_id": run_dir.name,
            "pipeline_version": "demo",
            "project_dir": str(run_dir),  # the stamped source lives here → page embeds it
            "started_ts": datetime.now().isoformat(timespec="seconds"),
            "finished_ts": datetime.now().isoformat(timespec="seconds"),
            "outcome": "complete",
            "exit_code": 0,
            "stage": "extraction",
            "demo_profile": None,
            "sources": [dict(meta)],
            "steps": [
                {"number": 2, "name": "classification", "kind": "model", "agent": "classify",
                 "description": "Project type + onboarding sensitivity tier", "status": "pass"},
                {"number": 4, "name": "extraction", "kind": "model", "agent": "extract",
                 "description": "Per-source citation-bearing extracts", "status": "pass"},
            ],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        page = run_review.write_run_review(run_dir)
        print(f"\nWALKTHROUGH PAGE — what just happened, as the account team sees it: {page}")
        if sys.platform == "darwin" and not os.environ.get("DEMO_NO_OPEN") and sys.stdout.isatty():
            subprocess.run(["open", str(page)], check=False)
    except Exception as exc:
        print(f"\n(walkthrough page skipped: {exc})")

    elapsed = time.monotonic() - started
    print(f"\ndone in {elapsed:.1f}s · model cost ${cost:.3f} · artifacts in {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
