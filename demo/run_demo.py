"""Live demo: one document in, verified facts out.

Runs the pipeline's evidence layer only — classify → extract → deterministic verification
gates — on a single text file (or stdin). No synthesis, no renders: what this shows is the
part that makes everything downstream trustworthy, in a couple of minutes:

    python demo/run_demo.py demo_live/sources/live_transcript.md --glossary demo_live/client_demo.json --live
    BRIEF_BUILDER_CLAUDE_BIN="$PWD/tools/replay/claude" \\
        python demo/run_demo.py fixtures/northlight_01/transcript_kickoff.md --glossary glossary/meltemi.json
    cat some_meeting_notes.txt | python demo/run_demo.py - --declaration-folder demo_live/sources --live

Every printed fact carries its exact source quote; anything the document does not state
becomes an open question, never a plausible value. Uses the same subagent transport and the
same safeguards as the runner (pipeline/runner.py):

  * live model calls are opt-in (`--live` or BRIEF_BUILDER_LIVE=1; the replay binary needs none);
  * the input's folder must carry a valid `data_declaration.json` (for stdin, name the folder
    with --declaration-folder), and the data class's path rules apply (exit 6 otherwise);
  * the stamped input and the client config are staged read-only under `<run>/inputs/`, the
    agents are granted the run directory and the read-only skeleton only, and every model step
    is followed by the runner's integrity check (exit 4 on a tampered file);
  * the demo's own outputs are archived before each leg, so a retry is never judged on the
    previous leg's artifact.

Input is capped at ~800 words (the demo is a conversation, not a batch job). A file whose
type cannot be inferred from strong signals is refused with instructions, not guessed —
same ethos as the pipeline (`--type transcript|rfp|email_thread|background` overrides).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import agents, clock, data_policy, extraction, gates, intake, prescreen, runner, stages  # noqa: E402

MAX_WORDS = 800

EXIT_OK = 0
EXIT_REFUSED = 2          # input not usable, or the extraction gate refused every leg
EXIT_HALTED = 3           # the classifier asked instead of guessing
EXIT_INTEGRITY = runner.EXIT_GATE_ERROR
EXIT_DATA_DECLARATION = runner.EXIT_DATA_DECLARATION
EXIT_LIVE_NOT_ENABLED = runner.EXIT_LIVE_NOT_ENABLED


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


def _stamp(text: str, name: str, type_override: Optional[str]) -> tuple[str, dict]:
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
        "source_date": sdate.group(1) if sdate else clock.now().strftime("%Y-%m-%d"),
    }
    header = (f"# Demo input\nsource_id: {meta['source_id']} · source_type: "
              f"{meta['source_type']} · source_date: {meta['source_date']}\n\n")
    return header + text, meta


def _cell(text: str, width: int) -> str:
    text = " ".join((text or "").split())
    return (text[: width - 1] + "…") if len(text) > width else text.ljust(width)


def _declaration_folder(args: argparse.Namespace) -> Path:
    """The folder whose data_declaration.json covers the input: explicit, or the file's own."""
    if args.declaration_folder:
        return Path(args.declaration_folder)
    if args.input == "-":
        sys.exit("[demo] stdin has no folder, so no data declaration covers it — pass "
                 "--declaration-folder DIR (a folder holding data_declaration.json)")
    return Path(args.input).resolve().parent


def _stage(run_dir: Path, meta: dict, stamped: str, glossary_path: Path) -> tuple:
    """Stage the stamped input and the client config read-only under <run>/inputs/ exactly as
    the runner does; return (staged SourceDoc, staged glossary path)."""
    with tempfile.TemporaryDirectory(prefix="bb-demo-") as scratch:
        original = Path(scratch) / f"{meta['source_id']}.md"
        original.write_text(stamped, encoding="utf-8")
        doc = gates.SourceDoc(meta["source_id"], meta["source_type"], meta["source_date"], original, stamped)
        staged, staged_glossary = runner.stage_inputs(run_dir, [doc], glossary_path)
    return staged[0], staged_glossary


def _guarded(ctx: runner.RunContext, step: str, originals: list, call):
    """Run one model step the way the runner does: this step's scope, then the integrity check.

    Returns the call's result; raises gates.GateError('integrity: …') when the step changed a
    protected file (a staged input, the skeleton, an earlier step's output, the original input).
    """
    ctx.current_step = step
    before = runner.integrity_state(ctx, originals)
    try:
        result = call(runner._access_dirs(ctx))
    except stages.HaltForHuman:
        _check(ctx, before, originals)
        raise
    _check(ctx, before, originals)
    return result


def _check(ctx: runner.RunContext, before: dict, originals: list) -> None:
    tampered = runner.integrity_violations(before, runner.integrity_state(ctx, originals))
    if tampered:
        raise gates.GateError("integrity: " + "; ".join(tampered)
                              + " — runtime agents may write only their own outputs")


def main(argv=None) -> int:
    """CLI entry point: one document in, verified facts out; returns the exit code."""
    runner._line_buffered_stdout()
    parser = argparse.ArgumentParser(description="One document in, verified facts out.")
    parser.add_argument("input", help="a text/markdown file, or '-' for stdin")
    parser.add_argument("--type", default=None, help="source type when it cannot be inferred")
    parser.add_argument("--glossary", default=None,
                        help="client config path (default: the single file in glossary/)")
    parser.add_argument("--declaration-folder", default=None,
                        help="folder whose data_declaration.json covers the input (default: the "
                             "input file's folder; required for stdin)")
    parser.add_argument("--project-id", default=None,
                        help="project_id in the work orders (default: the declaration folder's name)")
    parser.add_argument("--out", default=str(runner.DEFAULT_OUT_DIR),
                        help="where the demo run directory is written (default runs/)")
    parser.add_argument("--live", action="store_true", default=None,
                        help="allow live model calls through a real Claude Code CLI (or set "
                             "BRIEF_BUILDER_LIVE=1); the offline replay binary needs no opt-in")
    parser.add_argument("--max-words", type=int, default=MAX_WORDS)
    parser.add_argument("--retries", type=int, default=2,
                        help="extra extraction legs after a gate refusal (each leg already "
                             "carries one internal repair attempt); refusals are printed, "
                             "never hidden — a refusal is the citation gate rejecting a "
                             "fabricated quote, i.e. the product working")
    args = parser.parse_args(argv)

    # Refusals that write nothing come first: a real CLI nobody opted in to, a missing or
    # invalid data declaration.
    refusal = agents.live_refusal(args.live)
    if refusal:
        print(f"[live calls] {refusal}", file=sys.stderr)
        return EXIT_LIVE_NOT_ENABLED
    folder = _declaration_folder(args)
    out_dir = Path(args.out)
    glossary_arg = Path(args.glossary) if args.glossary else None
    try:
        declaration = data_policy.require_for_run(folder, out_dir=out_dir, glossary=glossary_arg)
    except data_policy.DataDeclarationError as exc:
        print(f"[data declaration] {exc}", file=sys.stderr)
        return EXIT_DATA_DECLARATION

    started = time.monotonic()
    started_ts = clock.timestamp("seconds")
    raw, name = _read_input(args.input)
    stamped, meta = _stamp(raw, name, args.type)
    stamped, word_count, capped = _cap_words(stamped, args.max_words)
    doc = gates.SourceDoc(meta["source_id"], meta["source_type"], meta["source_date"], Path(name), stamped)
    unsafe = runner.unsafe_source_ids([doc])
    if unsafe:
        print("[demo] " + "; ".join(unsafe), file=sys.stderr)
        return EXIT_REFUSED

    try:
        glossary_path = extraction.resolve_glossary(glossary_arg)
        client_config = extraction.load_client_config(glossary_path)
    except gates.GateError as exc:
        print(f"[client config] {exc}", file=sys.stderr)
        return EXIT_REFUSED

    run_dir = out_dir.resolve() / f"demo-{clock.compact('%Y%m%d-%H%M%S-%f')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    try:
        source, staged_glossary = _stage(run_dir, meta, stamped, glossary_path)
    except (gates.GateError, OSError) as exc:
        print(f"[input staging] {exc}", file=sys.stderr)
        return EXIT_REFUSED
    originals = [glossary_path] + ([Path(args.input)] if args.input != "-" else [])
    project_id = args.project_id or folder.resolve().name
    ctx = runner.RunContext(project_dir=folder.resolve(), run_dir=run_dir, run_id=run_dir.name,
                            sources=[source], started_ts=started_ts, project_id=project_id,
                            client_config=client_config, glossary_path=staged_glossary)
    cli = agents.cli_record(args.live)
    screen = prescreen.scan(run_dir / runner.STAGED_INPUTS_DIR, files=[source.path])

    print(f"Brief Builder — live demo · {name} ({meta['source_type']}, {word_count} words"
          + (f", capped at {args.max_words}" if capped else "") + f")\n  output: {run_dir}")
    print(f"  data  : {declaration.data_class} · model: "
          + ("offline replay (no model calls)" if cli["replay"] else "LIVE" if cli["live"] else "no CLI")
          + "\n")

    usage_tokens = 0
    print("[1/2] classify — what is this project, which onboarding tier applies…")
    try:
        classification = _guarded(ctx, "classification", originals, lambda scope: stages.classify(
            [source], run_dir, project_id, client_config, staged_glossary, scope))
    except stages.HaltForHuman as exc:
        print(f"      HALTED FOR HUMAN (by design — it asks instead of guessing): {exc}")
        return EXIT_HALTED
    except (gates.GateError, agents.SubagentError) as exc:
        print(f"      classification failed: {exc}")
        return EXIT_INTEGRITY if str(exc).startswith("integrity:") else EXIT_REFUSED
    usage_tokens += sum(sum((a["subagent"].get("usage") or {}).values()) for a in classification["attempts"])
    print(f"      {classification['project_type']} · tier {classification['sensitivity_tier']} "
          f"(copied from client config, never inferred) · "
          f"confidence {classification['classification_confidence']}\n")

    print("[2/2] extract — every value must carry a verbatim quote or it does not exist…")
    outcome = None
    for leg in range(1, args.retries + 2):
        # A retried leg is judged on what THIS leg writes, never on the last leg's files.
        runner.clear_stale_outputs(run_dir, runner.model_output_paths("extraction", [source]))
        try:
            outcome = _guarded(ctx, "extraction", originals, lambda scope: extraction.extract_source(
                source=source, run_dir=run_dir, project_id=project_id, client_config=client_config,
                glossary_path=staged_glossary, access_dirs=scope))
            break
        except (gates.GateError, agents.SubagentError) as exc:
            if str(exc).startswith("integrity:"):
                print(f"      REFUSED — a model step changed a protected file: {exc}")
                return EXIT_INTEGRITY
            print(f"      REFUSED by the verification gate, leg {leg}/{args.retries + 1} — a "
                  f"near-miss quote was rejected; this is the product working:\n      {exc}")
            if leg <= args.retries:
                print("      re-running the leg with a fresh model call…")
    if outcome is None:
        return EXIT_REFUSED
    usage_tokens += sum(sum((a["subagent"].get("usage") or {}).values()) for a in outcome["attempts"])

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

    print("\nVERIFICATION GATES (deterministic, no model):")
    print("  ✅ schema: extract validates against schema/extract_schema.json")
    print(f"  {'✅' if resolved == len(items) else '❌'} citations: {resolved}/{len(items)} "
          f"anchor+location strings occur verbatim in the source")
    print("  ✅ integrity: no staged input, skeleton file or original changed during a model step")
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
        from pipeline import run_review

        (run_dir / "run_manifest.json").write_text(json.dumps({
            "run_id": run_dir.name,
            "pipeline_version": "demo",
            # The staged, stamped source lives here, so the page embeds exactly what was read.
            "project_dir": runner.repo_relative(run_dir / runner.STAGED_INPUTS_DIR),
            "started_ts": started_ts,
            "finished_ts": clock.timestamp("seconds"),
            "outcome": "complete",
            "exit_code": 0,
            "stage": "extraction",
            "demo_profile": None,
            "data_declaration": declaration.as_record(),
            "live": bool(cli["live"]),
            "cli": cli,
            "prescreen": screen,
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
    print(f"\ndone in {elapsed:.1f}s · {usage_tokens:,} tokens reported by the CLI · artifacts in {run_dir}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
