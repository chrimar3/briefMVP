"""Which gate violations recur across runs — the "should we teach the skeleton?" report.

    python eval/repair_analysis.py runs/                 # every run under a directory
    python eval/repair_analysis.py runs/20260724-021459  # one run
    python eval/repair_analysis.py runs/ --json

Every repair round costs a model call. If the *same rule* fails first-attempt every time, that
is not the gate being fussy — it is the skeleton failing to teach something once, and paying a
retry for it on every source forever. This tool reads the per-attempt violations the runner
already records in each `run_manifest.json`, normalises each free-text violation down to the
rule that produced it, and counts how often each rule recurs.

It is NOT part of the frozen grader (`eval/harness.py`) and never touches the answer key — it
reads run manifests only. A recurring rule here is a prompt-engineering lead, not a pass/fail.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

#: Ordered signature → (rule_id, human title). First match wins, so put the specific rules
#: (which quote a stable tail phrase from the violation message) before the schema buckets.
#: Every phrase here is copied from an actual violation string in pipeline/gates.py or
#: pipeline/stages.py — when a message changes there, its signature changes here, on purpose.
_SIGNATURES = (
    # Extraction / citation discipline
    ("does not occur in the source", "citation-unresolvable",
     "Citation (location/anchor) not found verbatim in the source"),
    ("never appears in Latin script", "glossary-term-repaired",
     "Glossary term written in a value the source never had in Latin (silent repair/translation)"),
    (re.compile(r"empty (location|anchor)"), "citation-empty",
     "Item with an empty location or anchor"),
    # Synthesis discipline
    ("computed by the runner", "readiness-populated",
     "Model populated the readiness block (runner-only field)"),
    ("human act", "agent-signed-off",
     "Model set signoff to something other than draft"),
    ("resolution is human-only", "conflict-resolved",
     "Conflict emitted as resolved rather than open"),
    ("copied verbatim", "anchor-altered",
     "Evidence anchor altered during assembly (breaks the Greek round-trip)"),
    # 'a routing call with no citation' must be matched before the generic 'no evidence' below,
    # because the classification message contains both phrases.
    ("a routing call with no citation", "classification-uncited",
     "Classification with no evidence for the project_type decision"),
    ("no evidence", "entry-without-evidence",
     "Brief entry with no supporting evidence ref"),
    ("at least two positions", "conflict-underspecified",
     "Conflict with fewer than two positions"),
    # Render discipline
    ("no citation tag", "render-uncited-line",
     "Rendered claim line with no citation tag"),
    ("no known source", "render-unknown-source",
     "Citation tag naming a source the brief does not cite"),
    ("missing from the render", "render-glossary-lost",
     "Glossary term in the brief not character-exact in a render"),
    ("section heading", "render-missing-section",
     "Open questions exist but the render has no ⚠ section"),
    # Classification discipline
    ("never inferred", "tier-inferred",
     "Classifier returned a tier differing from client config"),
    # Fidelity discipline
    ("never repairs", "fidelity-repaired",
     "Annotated transcript altered a token instead of only inserting annotations"),
    ("more than", "fidelity-altered",
     "Annotated transcript differs from the original beyond annotations"),
    # Infrastructure
    ("not valid JSON", "malformed-json", "Artifact was not valid JSON"),
    ("no file written", "no-output-file", "No artifact file was written"),
    # Schema buckets — jsonschema wording, matched last
    ("is a required property", "schema-missing-required", "Schema: a required property is missing"),
    ("Additional properties", "schema-additional-properties", "Schema: additional properties present"),
    ("is not one of", "schema-invalid-enum", "Schema: value not in the allowed enum"),
    ("is not of type", "schema-wrong-type", "Schema: value of the wrong type"),
    ("is too short", "schema-too-short", "Schema: string/array below minimum length"),
    ("does not match", "schema-pattern", "Schema: value fails a pattern constraint"),
)


def classify_violation(text: str) -> tuple:
    """Map one free-text violation to (rule_id, rule_title). Unknown → ('other', <trimmed text>)."""
    for signature, rule_id, title in _SIGNATURES:
        if isinstance(signature, re.Pattern):
            if signature.search(text):
                return rule_id, title
        elif signature in text:
            return rule_id, title
    # Keep an unclassified violation legible without letting its specifics fragment the count.
    trimmed = re.sub(r"\[\d+\]", "[]", text).split(" — ")[0][:80]
    return "other", f"Unclassified: {trimmed}"


@dataclass
class RuleStat:
    rule_id: str
    title: str
    occurrences: int = 0                       # total times the rule fired
    first_attempt_hits: int = 0                # times it fired on a first attempt (the teachable ones)
    sources: set = field(default_factory=set)  # distinct (run, stage, source) it fired on
    example: str = ""

    def as_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "occurrences": self.occurrences,
            "first_attempt_hits": self.first_attempt_hits,
            "distinct_sites": len(self.sources),
            "example": self.example,
        }


def _iter_attempts(manifest: dict, repair_log: list):
    """Yield (stage, site, attempt_number, violations) for every gated attempt in a run.

    Prefers the durable repair log (written per attempt, survives stage failure and manifest
    truncation) and falls back to the manifest's own records for runs that predate the sink.
    """
    if repair_log:
        for record in repair_log:
            yield (record.get("stage", "?"), record.get("site", "?"),
                   record.get("attempt"), record.get("violations") or [])
        return

    for step in manifest.get("steps") or []:
        stage = step.get("name", "?")
        for extract in step.get("extracts") or []:
            site = extract.get("source_id", "?")
            for attempt in extract.get("attempts") or []:
                yield stage, site, attempt.get("attempt"), attempt.get("violations") or []
        for attempt in step.get("attempts") or []:
            yield stage, stage, attempt.get("attempt"), attempt.get("violations") or []


def analyse(manifests: list) -> dict:
    stats: dict = {}
    totals = {"runs": 0, "attempts": 0, "repair_rounds": 0, "clean_first_attempts": 0}

    for entry in manifests:
        run_id, manifest = entry[0], entry[1]
        repair_log = entry[2] if len(entry) > 2 else []
        totals["runs"] += 1
        for stage, site, attempt_no, violations in _iter_attempts(manifest, repair_log):
            totals["attempts"] += 1
            if attempt_no and attempt_no > 1:
                totals["repair_rounds"] += 1
            if attempt_no == 1 and not violations:
                totals["clean_first_attempts"] += 1
            for text in violations:
                rule_id, title = classify_violation(text)
                stat = stats.setdefault(rule_id, RuleStat(rule_id, title))
                stat.occurrences += 1
                if attempt_no == 1:
                    stat.first_attempt_hits += 1
                stat.sources.add((run_id, stage, site))
                if not stat.example:
                    stat.example = text

    ranked = sorted(stats.values(), key=lambda s: (s.first_attempt_hits, s.occurrences), reverse=True)
    return {"totals": totals, "rules": [s.as_dict() for s in ranked]}


def load_manifests(path: Path) -> list:
    path = Path(path)
    if path.is_file() and path.name == "run_manifest.json":
        files = [path]
    elif (path / "run_manifest.json").is_file():
        files = [path / "run_manifest.json"]
    else:
        files = sorted(path.glob("*/run_manifest.json"))
    out = []
    for f in files:
        try:
            manifest = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[repair-analysis] skipping {f}: {exc}", file=sys.stderr)
            continue
        repair_log = _load_repair_log(f.parent)
        out.append((f.parent.name, manifest, repair_log))
    return out


def _load_repair_log(run_dir: Path) -> list:
    """Read the durable per-attempt log if present. Kept local so the analyser has no import
    dependency on the pipeline package — it grades run directories, wherever they live."""
    path = run_dir / "diagnostics" / "repair_log.jsonl"
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def report(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    t = result["totals"]
    print(f"\nRepair-loop analysis · {t['runs']} run(s) · {t['attempts']} gated attempt(s)")
    print(f"  {t['clean_first_attempts']} clean on first attempt · {t['repair_rounds']} repair round(s)\n")

    rules = result["rules"]
    if not rules:
        print("  No violations recorded. (Either every artifact passed first try, or the")
        print("  manifests predate per-attempt violation logging.)\n")
        return

    print(f"  {'rule':<28} {'1st-att':>7} {'total':>6} {'sites':>6}  title")
    print(f"  {'-'*28} {'-'*7} {'-'*6} {'-'*6}  {'-'*40}")
    for r in rules:
        print(f"  {r['rule_id']:<28} {r['first_attempt_hits']:>7} {r['occurrences']:>6} "
              f"{r['distinct_sites']:>6}  {r['title'][:52]}")
    print()

    teachable = [r for r in rules if r["rule_id"] != "other" and r["distinct_sites"] >= 2]
    if teachable:
        top = teachable[0]
        print(f"  ▸ Most recurrent teachable rule: {top['rule_id']} — {top['distinct_sites']} distinct sites.")
        print(f"    Example: {top['example'][:110]}")
        print(f"    If this keeps recurring, teach it once in the skeleton rather than paying a retry per source.\n")


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate recurring gate violations across runs.")
    parser.add_argument("path", help="A run directory, a runs/ parent, or a run_manifest.json")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    manifests = load_manifests(Path(args.path))
    if not manifests:
        print(f"[repair-analysis] no run manifests found under {args.path}", file=sys.stderr)
        return 2
    report(analyse(manifests), args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
