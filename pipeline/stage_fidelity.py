"""Pipeline step 3 — transcript fidelity gate.

`fidelity-check` annotates and never rewrites — verified here by stripping annotations and
requiring byte-equality with the original (TRANSCRIPTS.md §5).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline import agents
from pipeline.stage_common import HaltForHuman, stage_failure

#: An annotation is inserted *with* its separating whitespace, so the whitespace is part of the
#: insertion and comes out with it. Without the leading `\s*`, an annotation placed before
#: punctuation ("ογδόντα πέντε [FIDELITY: ...], αλλά") strips back to "πέντε , αλλά" and a
#: correctly-annotated transcript gets rejected for a stray space. The body tolerates one level
#: of nested brackets ("[FIDELITY: glossary-match [key visual]]") — an annotation quoting a
#: bracketed term must strip whole, not leave its own residue. The check this serves is
#: "no character of the transcript was altered", and that still holds exactly.
FIDELITY_ANNOTATION_RE = re.compile(r"\s*\[FIDELITY:(?:[^\[\]]|\[[^\]]*\])*\]")
FIDELITY_REPORT_KEYS = ("source_id", "tokens_flagged", "glossary_matches", "fidelity_score", "verdict")
FIDELITY_VERDICTS = ("pass", "pass_with_flags", "escalate_to_human")


def build_fidelity_order(source, report_file: Path, annotated_file: Path, glossary_path: Path) -> str:
    """The fidelity work order for one transcript: two output files, annotations only."""
    return f"""FIDELITY WORK ORDER — Brief Builder pipeline step 3.

Score and annotate one transcript. You never rewrite it.

INPUT
  source_file      : {source.path}
  source_id        : {source.source_id}
  client_glossary  : {glossary_path}

READ ONLY those two files. Any file named `answer_key.json` is off limits.

OUTPUT — two files, at exactly these paths:
  report    : {report_file}
  annotated : {annotated_file}

  The annotated transcript must be the original text with `[FIDELITY: ...]` annotations
  INSERTED and nothing else changed. The runner strips every annotation and requires the
  result to equal the original exactly — one altered character fails the run. Do not
  reformat, do not fix spelling, do not normalise whitespace, do not translate.

  The report is the JSON object defined in your instructions; `verdict` must be one of
  {list(FIDELITY_VERDICTS)}.

Reply with one line: tokens flagged and the verdict.
"""


FIDELITY_SCORES = ("high", "medium", "low")


def check_fidelity(report_file: Path, annotated_file: Path, original: str) -> list:
    """Gate one fidelity-check output.

    The comparison is byte-exact after stripping annotations, exactly as the work order says
    ("one altered character fails the run… do not normalise whitespace"). It used to compare
    whitespace-collapsed text, which let a re-flowed or re-indented transcript through while
    the instruction promised otherwise; every stored annotated transcript (runs/tier3,
    runs/voreas-prep-02, runs/voreas-prep-03) strips back to its source byte-for-byte, so the
    gate was tightened rather than the instruction loosened.
    """
    violations = []
    if not annotated_file.is_file():
        violations.append(f"no annotated transcript at {annotated_file}")
    else:
        stripped = FIDELITY_ANNOTATION_RE.sub("", annotated_file.read_text(encoding="utf-8"))
        if stripped != original:
            if " ".join(stripped.split()) == " ".join(original.split()):
                violations.append(
                    "annotated transcript differs from the original in whitespace or line breaks "
                    "once the [FIDELITY: ...] insertions are stripped — insert annotations only; "
                    "do not re-flow, re-indent or normalise whitespace (TRANSCRIPTS.md §3)"
                )
            else:
                violations.append(
                    "annotated transcript differs from the original by more than [FIDELITY: ...] "
                    "insertions — this stage annotates, it never repairs (TRANSCRIPTS.md §3)"
                )

    if not report_file.is_file():
        violations.append(f"no fidelity report at {report_file}")
        return violations
    try:
        report = json.loads(report_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        violations.append(f"report is not valid JSON: {exc}")
        return violations

    violations.extend(f"report missing key: {k}" for k in FIDELITY_REPORT_KEYS if k not in report)
    if report.get("verdict") not in FIDELITY_VERDICTS:
        violations.append(f"verdict {report.get('verdict')!r} not in {list(FIDELITY_VERDICTS)}")
    if "fidelity_score" in report and report.get("fidelity_score") not in FIDELITY_SCORES:
        violations.append(f"fidelity_score {report.get('fidelity_score')!r} not in {list(FIDELITY_SCORES)}")
    # TRANSCRIPTS.md §4, machine-checked: a low score or a summary-not-transcript suspicion
    # escalates. Before this, a report reading score 'low' + verdict 'pass' went straight on
    # to extraction — the silent consumption of a bad transcript DR-12 exists to prevent.
    if ((report.get("fidelity_score") == "low" or report.get("summary_suspicion") is True)
            and report.get("verdict") != "escalate_to_human"):
        reasons = [r for r, hit in (("fidelity_score is 'low'", report.get("fidelity_score") == "low"),
                                    ("summary_suspicion is true", report.get("summary_suspicion") is True)) if hit]
        violations.append(
            f"{' and '.join(reasons)} but verdict is {report.get('verdict')!r} — a low score or a "
            f"summary suspicion must escalate: set verdict to 'escalate_to_human' (TRANSCRIPTS.md §4)"
        )
    return violations


def fidelity_check(source, run_dir: Path, glossary_path: Path, access_dirs) -> dict:
    """Run the fidelity-check subagent on one transcript; halt for a human on escalation."""
    out_dir = Path(run_dir) / "fidelity"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / f"{source.source_id}.report.json"
    annotated_file = out_dir / f"{source.source_id}.annotated.md"

    order = build_fidelity_order(source, report_file, annotated_file, glossary_path)
    attempts, failed = agents.run_gated(
        "fidelity-check", order,
        lambda: check_fidelity(report_file, annotated_file, source.text),
        lambda v: agents.repair_order("fidelity output", v, "Fix exactly these and rewrite both files."),
        access_dirs, stage="fidelity-check", site=source.source_id, run_dir=Path(run_dir),
    )
    if failed:
        raise stage_failure("fidelity-check", failed)

    report = json.loads(report_file.read_text(encoding="utf-8"))
    if report["verdict"] == "escalate_to_human":
        raise HaltForHuman(
            f"transcript {source.source_id} scored {report.get('fidelity_score')!r} — "
            f"escalated to human. Silent consumption of a bad transcript poisons every "
            f"downstream citation (PRD DR-12); the run continues only by explicit human choice."
        )
    return {
        "source_id": source.source_id,
        "report_file": str(report_file),
        "annotated_file": str(annotated_file),
        "verdict": report["verdict"],
        "fidelity_score": report.get("fidelity_score"),
        "tokens_flagged": report.get("tokens_flagged"),
        "attempts": attempts,
    }
