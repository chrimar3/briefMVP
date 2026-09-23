"""Synthetic fault-injection benchmark for agency safeguards; zero model calls.

This tests deterministic detection, NOT generative quality or natural Greek. Run a
separate current-routing model benchmark before making an agency-readiness claim.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Optional

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import clarifications, extraction, gates, handover, quality, revisions  # noqa: E402


def run() -> dict[str, Any]:
    """Run every synthetic fault-injection case and the corpus input gates; return the report."""
    ref = {"source_id": "rfp", "location": "L1", "anchor": "Build awareness"}
    b: dict[str, Any] = {"objectives": [{"content": "Build awareness", "evidence": [ref]}], "conflicts": [],
                         "open_questions": []}
    e = {"rfp": {"objectives": [{"value": "Build awareness", "location": "L1", "anchor": "Build awareness"}]}}
    cases: list[dict[str, Any]] = []

    def check(name: str, condition: object) -> None:
        """Record one scenario as passed when `condition` is truthy."""
        cases.append({"scenario": name, "passed": bool(condition)})
    check("intact objective remains accounted for", bool(quality.coverage(b, e)[0]["destinations"]))
    dropped = copy.deepcopy(b)
    dropped["objectives"] = []
    check("dropped primary objective detected", not quality.coverage(dropped, e)[0]["destinations"])
    wrong_source = copy.deepcopy(b)
    wrong_source["objectives"][0]["evidence"][0]["source_id"] = "email"
    check("same words from wrong source rejected", not quality.coverage(wrong_source, e)[0]["destinations"])
    question = copy.deepcopy(dropped)
    question["open_questions"] = [{"field": "objectives", "linked_evidence": [ref]}]
    check("uncertain objective can survive as a question", bool(quality.coverage(question, e)[0]["destinations"]))
    q = {"field": "budget", "suggested_question_for_client": "Media budget?", "linked_evidence": [ref]}
    questions = {"open_questions": [q, copy.deepcopy(q),
                                    {"field": "budget", "suggested_question_for_client": "Production approval owner?"}]}
    check("exact repeat grouped; distinct budget issue preserved", len(clarifications.queue(questions)) == 2)
    qid = clarifications.queue(questions)[0]["id"]
    reordered = {"open_questions": list(reversed(questions["open_questions"]))}
    check("question identity independent of order", qid == clarifications.queue(reordered)[1]["id"])
    check("empty Greek render fails structural coverage", bool(quality.render_coverage(b, "", "el")))
    check("missing English source link detected",
          bool(quality.render_coverage(b, "## 1 Objectives\n- Build awareness", "en")))
    check("valid structural render accepted",
          not quality.render_coverage(b, "## 1 Objectives\n- Build awareness [rfp L1]", "en"))
    spec = {"specs": [{"id": "portrait", "format": "Story", "file_type": "MP4", "resolution": "1080x1920",
                       "aspect_ratio": "9:16", "duration": "up to 60s"}]}
    row = {"id": "a", "spec_id": "portrait", "format": "Story", "file_type": "JPG", "resolution": "1080x1920",
           "aspect_ratio": "9:16", "duration_seconds": 90, "quantity": 1, "languages": ["el"], "owner": "Production",
           "approval_owner": "Lead", "deadline": "2026-12-01", "dependencies": [], "evidence": [ref]}
    errors = handover.validate([row], spec, b)
    check("wrong file type detected", any("file_type" in p for p in errors))
    check("overlong asset detected", any("duration" in p for p in errors))
    check("brief revision exposes changed fields", "objectives" in revisions.changes(b, dropped))
    inputs: list[dict[str, Any]] = []
    for kind in ("paid", "organic", "production"):
        project = gates.REPO_ROOT / "fixtures" / f"agency_{kind}_01"
        sources = gates.discover_sources(project)
        config = extraction.load_client_config(project / "glossary.json")
        inputs.append({"fixture": project.name, "source_count": len(sources),
                       "client_id": config["client_id"], "input_gate_passed": gates.readiness_gate(sources).ok})
    return {"corpus_inputs": inputs, "kind": "synthetic deterministic fault injection", "model_calls": 0,
            "passed": sum(c["passed"] for c in cases), "total": len(cases), "cases": cases,
            "not_measured": ["new model outputs under current routing", "semantic fidelity", "Greek naturalness",
                             "real staff time or adoption"]}


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry: print the benchmark report (optionally write it); exit 1 unless every case passes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = run()
    if args.output:
        revisions.write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    inputs_ok = all(case["input_gate_passed"] for case in report["corpus_inputs"])
    return int(report["passed"] != report["total"] or not inputs_ok)


if __name__ == '__main__':
    raise SystemExit(main())
