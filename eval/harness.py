"""eval/harness.py — machine-checkable DoD for Tiers 1–3.

    python eval/harness.py runs/latest [--tier 1|2|3|all] [--json]

**FROZEN at the end of Tier 1** (CLAUDE.md rule 2). Everything below therefore had to be
written before the artifacts it grades exist, which inverts the usual relationship: this file
is not a description of what the pipeline produced, it is the *contract the later tiers must
satisfy*. Where a check needed a convention that did not exist yet — the citation-tag format
in the renders — that convention was written into `TRANSLATION.md` and the template in the
same tier, so Tier 2 is aiming at a published target rather than a hidden one.

This is also the only component permitted to read `fixtures/*/answer_key.json`. The pipeline
cannot reach the answer key by construction (`gates.HARNESS_ONLY_FILES`); the grader reads it
because grading is its entire job. Nothing here writes to the run except its own report.

Exit codes: 0 = every applicable check passed · 1 = at least one failed · 2 = could not grade.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline import gates  # noqa: E402  (path set above so the harness runs from anywhere)

#: A citation tag in a rendered document: square brackets containing a source_id and,
#: usually, a location — e.g. `[transcript_kickoff 00:14:32]` or `[rfp_meltemi §3]`.
#: The rule the renders must satisfy: every content line carries at least one tag naming a
#: source that the brief actually cites. This is the mechanical form of "no orphan prose".
CITATION_TAG_RE = re.compile(r"\[([^\]]+)\]")

#: Lines that are structure rather than claims, and so are exempt from the citation rule.
STRUCTURAL_PREFIXES = ("#", ">", "|", "---", "**Client:**", "**Input coverage:**", "**Sources used:**")

#: Render sections that state claims (template sections 1–7). Open questions, conflicts and
#: sign-off have their own shapes and are checked separately.
CLAIM_SECTION_RE = re.compile(r"^##\s+(\d)\.")


# --------------------------------------------------------------------------------------
# Result plumbing
# --------------------------------------------------------------------------------------


@dataclass
class CheckResult:
    check_id: str
    tier: int
    title: str
    status: str  # pass | fail | skip
    detail: str = ""
    evidence: list = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.status == "fail"

    def as_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "tier": self.tier,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "evidence": self.evidence[:20],
        }


def _ok(cid, tier, title, detail="", evidence=None):
    return CheckResult(cid, tier, title, "pass", detail, evidence or [])


def _fail(cid, tier, title, detail="", evidence=None):
    return CheckResult(cid, tier, title, "fail", detail, evidence or [])


def _skip(cid, tier, title, detail=""):
    return CheckResult(cid, tier, title, "skip", detail)


# --------------------------------------------------------------------------------------
# Loading the run under test
# --------------------------------------------------------------------------------------


class HarnessError(Exception):
    """The run cannot be graded at all."""


@dataclass
class Run:
    """Everything the grader needs, loaded once."""

    run_dir: Path
    manifest: dict
    answer_key: dict
    project_dir: Path
    sources: dict = field(default_factory=dict)  # source_id -> raw text
    extracts: dict = field(default_factory=dict)  # source_id -> extract object
    brief: Optional[dict] = None
    renders: dict = field(default_factory=dict)  # 'el'/'en' -> text
    glossary: dict = field(default_factory=dict)

    @property
    def has_extracts(self) -> bool:
        return bool(self.extracts)

    @property
    def has_brief(self) -> bool:
        return self.brief is not None

    @property
    def has_renders(self) -> bool:
        return len(self.renders) == 2


def load_run(run_path: Path) -> Run:
    run_dir = Path(run_path).resolve()
    if not run_dir.is_dir():
        raise HarnessError(f"{run_path} is not a run directory")

    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.is_file():
        raise HarnessError(f"no run_manifest.json in {run_dir} — is this a pipeline run?")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    project_dir = Path(manifest["project_dir"])
    key_path = project_dir / "answer_key.json"
    if not key_path.is_file():
        raise HarnessError(f"no answer_key.json in {project_dir} — nothing to grade against")
    answer_key = json.loads(key_path.read_text(encoding="utf-8"))

    run = Run(run_dir=run_dir, manifest=manifest, answer_key=answer_key, project_dir=project_dir)

    for source in gates.discover_sources(project_dir):
        run.sources[source.source_id] = source.text

    for path in sorted((run_dir / "extracts").glob("*.json")) if (run_dir / "extracts").is_dir() else []:
        run.extracts[path.stem] = json.loads(path.read_text(encoding="utf-8"))

    brief_path = run_dir / "brief.json"
    if brief_path.is_file():
        run.brief = json.loads(brief_path.read_text(encoding="utf-8"))

    for lang in ("el", "en"):
        render_path = run_dir / f"brief_{lang}.md"
        if render_path.is_file():
            run.renders[lang] = render_path.read_text(encoding="utf-8")

    glossaries = sorted((REPO_ROOT / "glossary").glob("*.json"))
    if len(glossaries) == 1:
        run.glossary = json.loads(glossaries[0].read_text(encoding="utf-8"))

    return run


# --------------------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------------------


def _brief_entries(brief: dict) -> list:
    return [e for f in gates.BRIEF_FIELDS for e in (brief.get(f) or [])]


def _brief_text(brief: dict) -> str:
    """Every string in the brief, for substring checks."""
    return json.dumps(brief, ensure_ascii=False)


def _conflict_text(brief: dict) -> str:
    """Only the conflict blocks — where verbatim quoting of a disputed figure is legitimate."""
    return json.dumps(brief.get("conflicts") or [], ensure_ascii=False)


def _keep_latin_terms(glossary: dict) -> list:
    return [t["term"] for t in (glossary.get("terms") or []) if t.get("rule") == "keep_latin" and t.get("term")]


def _content_lines(render: str) -> list:
    """Lines inside template sections 1–7 that assert something."""
    lines, in_claim_section = [], False
    for raw in render.splitlines():
        line = raw.strip()
        heading = CLAIM_SECTION_RE.match(line)
        if line.startswith("##"):
            in_claim_section = bool(heading)
            continue
        if not in_claim_section or not line:
            continue
        if line.startswith(STRUCTURAL_PREFIXES):
            continue
        lines.append(line)
    return lines


# --------------------------------------------------------------------------------------
# TIER 1 — extraction
# --------------------------------------------------------------------------------------


def check_extracts_validate(run: Run) -> CheckResult:
    cid, title = "T1.1", "Every extract validates against extract_schema.json"
    if not run.has_extracts:
        return _skip(cid, 1, title, "no extracts in this run")
    failures = []
    for source_id, extract in run.extracts.items():
        try:
            gates.validate_extract(extract)
        except gates.SchemaValidationError as exc:
            failures.extend(f"{source_id}: {e}" for e in exc.errors)
    if failures:
        return _fail(cid, 1, title, f"{len(failures)} schema violation(s)", failures)
    return _ok(cid, 1, title, f"{len(run.extracts)} extract(s) valid")


def check_citations_present(run: Run) -> CheckResult:
    cid, title = "T1.2", "Zero items with empty location or anchor"
    if not run.has_extracts:
        return _skip(cid, 1, title, "no extracts in this run")
    failures = []
    for source_id, extract in run.extracts.items():
        failures.extend(f"{source_id}: {v}" for v in gates.find_uncited_items(extract))
    if failures:
        return _fail(cid, 1, title, f"{len(failures)} uncited item(s)", failures)
    total = sum(len(e.get(f) or []) for e in run.extracts.values() for f in gates.BRIEF_FIELDS)
    return _ok(cid, 1, title, f"{total} item(s), all cited")


def check_citations_resolve(run: Run) -> CheckResult:
    """A citation that cannot be found in the source is worse than a missing one — it survives
    review by looking verified (PRD R2). Beyond the letter of the Tier-1 DoD, deliberately."""
    cid, title = "T1.3", "Every location and anchor occurs verbatim in its source"
    if not run.has_extracts:
        return _skip(cid, 1, title, "no extracts in this run")
    failures = []
    for source_id, extract in run.extracts.items():
        source_text = run.sources.get(source_id)
        if source_text is None:
            failures.append(f"{source_id}: extract has no matching source document")
            continue
        failures.extend(f"{source_id}: {v}" for v in gates.verify_citations(extract, source_text))
    if failures:
        return _fail(cid, 1, title, f"{len(failures)} unresolvable citation(s)", failures)
    return _ok(cid, 1, title, "all citations resolve")


def check_garbling_flagged_not_fixed(run: Run) -> CheckResult:
    """The seeded garbled terms must survive as-is AND carry a glossary-match proposal.

    Two distinct failure modes, both checked: silent correction (the corrupted token vanishes,
    replaced by the clean term) and silent consumption (the token survives but nobody flags it).
    """
    cid, title = "T1.4", "Seeded garbled terms present as-is with glossary-match proposals"
    seeded = run.answer_key.get("seeded_garbling") or []
    if not run.has_extracts or not seeded:
        return _skip(cid, 1, title, "no extracts or no seeded garbling")

    failures, confirmed = [], []
    for entry in seeded:
        source_id, corrupted, intended = entry["source_id"], entry["corrupted"], entry["intended"]
        extract = run.extracts.get(source_id)
        if extract is None:
            failures.append(f"{entry['id']}: source {source_id} not extracted in this run")
            continue

        blob = json.dumps(extract, ensure_ascii=False)
        notes = " ".join(extract.get("extraction_notes") or [])
        values = " ".join(
            (i.get("value") or "") for f in gates.BRIEF_FIELDS for i in (extract.get(f) or [])
        )

        if corrupted not in blob:
            failures.append(
                f"{entry['id']}: corrupted token {corrupted!r} absent from the extract — "
                f"silently corrected to {intended!r}" if intended in blob else
                f"{entry['id']}: corrupted token {corrupted!r} absent from the extract"
            )
            continue
        if intended not in notes:
            failures.append(
                f"{entry['id']}: {corrupted!r} survives but no extraction_note proposes the "
                f"glossary match {intended!r} — silent consumption"
            )
            continue
        if intended in values:
            failures.append(
                f"{entry['id']}: glossary term {intended!r} written into an item value — "
                f"the repair belongs in a note, not in the evidence"
            )
            continue
        confirmed.append(f"{entry['id']}: {corrupted!r} as-is + proposal {intended!r}")

    if failures:
        return _fail(cid, 1, title, f"{len(failures)}/{len(seeded)} term(s) mishandled", failures)
    return _ok(cid, 1, title, f"{len(confirmed)}/{len(seeded)} flagged, none fixed", confirmed)


# --------------------------------------------------------------------------------------
# TIER 2 — full Stage 1
# --------------------------------------------------------------------------------------


def check_brief_validates(run: Run) -> CheckResult:
    cid, title = "T2.1", "Draft validates against brief_schema.json"
    if not run.has_brief:
        return _skip(cid, 2, title, "no brief.json in this run")
    try:
        gates.validate_brief(run.brief)
    except gates.SchemaValidationError as exc:
        return _fail(cid, 2, title, f"{len(exc.errors)} schema violation(s)", exc.errors)
    return _ok(cid, 2, title)


def check_sensitivity_scope(run: Run) -> CheckResult:
    cid, title = "T2.2", "sensitivity_tier is within S0–S1"
    if not run.has_brief:
        return _skip(cid, 2, title, "no brief.json in this run")
    tier = (run.brief.get("meta") or {}).get("sensitivity_tier")
    expected = (run.answer_key.get("expected_classification") or {}).get("sensitivity_tier")
    if tier not in gates.PERMITTED_SENSITIVITY_TIERS:
        return _fail(cid, 2, title, f"tier {tier!r} is out of MVP scope")
    if expected and tier != expected:
        return _fail(cid, 2, title, f"tier {tier!r} does not match the expected {expected!r}")
    return _ok(cid, 2, title, f"tier {tier}")


def check_both_renders_exist(run: Run) -> CheckResult:
    cid, title = "T2.3", "Both GR and EN renders exist"
    missing = [lang for lang in ("el", "en") if lang not in run.renders]
    if missing == ["el", "en"]:
        return _skip(cid, 2, title, "no renders in this run")
    if missing:
        return _fail(cid, 2, title, f"missing render(s): {missing}")
    return _ok(cid, 2, title, f"el={len(run.renders['el'])} chars · en={len(run.renders['en'])} chars")


def check_no_orphan_prose(run: Run) -> CheckResult:
    """Every claim line in each render carries a citation tag naming a source the brief cites.

    The mechanical stand-in for "every rendered claim maps to a schema entry". A line that
    asserts something without pointing anywhere is exactly the prose a renderer invents.
    """
    cid, title = "T2.4", "Every rendered claim carries a resolvable citation tag"
    if not run.has_renders or not run.has_brief:
        return _skip(cid, 2, title, "needs both renders and a brief")

    known = {s["source_id"] for s in (run.brief.get("meta") or {}).get("sources") or []}
    failures = []
    for lang, render in run.renders.items():
        for line in _content_lines(render):
            tags = CITATION_TAG_RE.findall(line)
            if not tags:
                failures.append(f"{lang}: uncited claim line — {line[:90]!r}")
            elif not any(any(sid in tag for sid in known) for tag in tags):
                failures.append(f"{lang}: tag names no known source — {line[:90]!r}")
    if failures:
        return _fail(cid, 2, title, f"{len(failures)} orphan line(s)", failures)
    return _ok(cid, 2, title, "all claim lines cited")


def check_glossary_exact_in_renders(run: Run) -> CheckResult:
    cid, title = "T2.5", "Glossary terms character-exact in both renders"
    if not run.has_renders or not run.has_brief or not run.glossary:
        return _skip(cid, 2, title, "needs both renders, a brief and a glossary")

    brief_blob = _brief_text(run.brief)
    failures = []
    for term in _keep_latin_terms(run.glossary):
        if term not in brief_blob:
            continue  # the brief never makes a claim using this term
        for lang, render in run.renders.items():
            if term not in render:
                failures.append(f"{lang}: glossary term {term!r} is in the brief but not character-exact in the render")
    if failures:
        return _fail(cid, 2, title, f"{len(failures)} term(s) lost", failures)
    return _ok(cid, 2, title, "protected terms intact in both renders")


def check_readiness_recomputes(run: Run) -> CheckResult:
    """The runner's readiness block must equal the harness's independent recomputation.

    Same function, same input, no model in the path — so a mismatch means someone let a model
    populate a deterministic field (SYNTHESIS.md rule 8).
    """
    cid, title = "T2.6", "Readiness block recomputes deterministically to the same values"
    if not run.has_brief:
        return _skip(cid, 2, title, "no brief.json in this run")
    stored = run.brief.get("readiness")
    if not stored:
        return _fail(cid, 2, title, "no readiness block in the brief")
    recomputed = gates.compute_readiness_block(run.brief)
    if stored != recomputed:
        return _fail(
            cid, 2, title, "stored readiness differs from recomputation",
            [f"stored={json.dumps(stored, sort_keys=True)}", f"recomputed={json.dumps(recomputed, sort_keys=True)}"],
        )
    return _ok(cid, 2, title, json.dumps(recomputed, sort_keys=True))


# --------------------------------------------------------------------------------------
# TIER 3 — quality gates, scored against the answer key
# --------------------------------------------------------------------------------------


def check_seeded_conflicts(run: Run) -> CheckResult:
    cid, title = "T3.1", "Seeded conflicts detected with citations to both sources"
    seeded = run.answer_key.get("seeded_conflicts") or []
    required = (run.answer_key.get("scoring") or {}).get("conflicts_required", len(seeded))
    if not run.has_brief or not seeded:
        return _skip(cid, 3, title, "no brief or no seeded conflicts")

    found, missing = [], []
    for entry in seeded:
        matches = []
        for conflict in run.brief.get("conflicts") or []:
            if conflict.get("field") != entry["field"]:
                continue
            blob = json.dumps(conflict, ensure_ascii=False)
            cited = {(p.get("evidence") or {}).get("source_id") for p in conflict.get("positions") or []}
            both_cited = entry["position_a"]["source_id"] in cited and entry["position_b"]["source_id"] in cited
            signals = entry["position_a"]["signal"] in blob and entry["position_b"]["signal"] in blob
            if both_cited and signals:
                matches.append(conflict)
        (found if matches else missing).append(entry["id"])

    detail = f"{len(found)}/{required} required ({', '.join(found) or 'none'})"
    if len(found) < required:
        return _fail(cid, 3, title, detail, [f"{m}: not detected with both citations + signals" for m in missing])
    return _ok(cid, 3, title, detail)


def check_seeded_gaps(run: Run) -> CheckResult:
    cid, title = "T3.2", "Seeded gaps present as open questions"
    seeded = run.answer_key.get("seeded_gaps") or []
    required = (run.answer_key.get("scoring") or {}).get("gaps_required_min", len(seeded))
    if not run.has_brief or not seeded:
        return _skip(cid, 3, title, "no brief or no seeded gaps")

    questions = run.brief.get("open_questions") or []
    found, missing = [], []
    for entry in seeded:
        hit = False
        for question in questions:
            blob = json.dumps(question, ensure_ascii=False).lower()
            field_ok = question.get("field") in entry["field_any_of"] or any(
                f.lower() in blob for f in entry["field_any_of"]
            )
            keyword_ok = any(k.lower() in blob for k in entry["keyword_any_of"])
            if field_ok and keyword_ok:
                hit = True
                break
        (found if hit else missing).append(entry["id"])

    detail = f"{len(found)}/{len(seeded)} found, {required} required ({', '.join(found) or 'none'})"
    if len(found) < required:
        return _fail(cid, 3, title, detail, [f"{m}: no open question covers this gap" for m in missing])
    return _ok(cid, 3, title, detail)


def check_garbling_survives_to_the_brief(run: Run) -> CheckResult:
    cid, title = "T3.3", "Garbled terms still flagged (not fixed) in the brief and renders"
    seeded = run.answer_key.get("seeded_garbling") or []
    if not run.has_brief or not seeded:
        return _skip(cid, 3, title, "no brief or no seeded garbling")

    blob = _brief_text(run.brief) + " ".join(run.renders.values())
    failures, found = [], []
    for entry in seeded:
        if entry["corrupted"] in blob:
            found.append(f"{entry['id']}: {entry['corrupted']!r} carried through")
        else:
            failures.append(f"{entry['id']}: {entry['corrupted']!r} disappeared between extract and brief")
    if failures:
        return _fail(cid, 3, title, f"{len(found)}/{len(seeded)} carried through", failures)
    return _ok(cid, 3, title, f"{len(found)}/{len(seeded)} carried through")


def check_no_uncited_values(run: Run) -> CheckResult:
    cid, title = "T3.4", "Zero uncited values anywhere in the draft"
    if not run.has_brief:
        return _skip(cid, 3, title, "no brief.json in this run")
    failures = []
    for fieldname in gates.BRIEF_FIELDS:
        for idx, entry in enumerate(run.brief.get(fieldname) or []):
            refs = entry.get("evidence") or []
            if not refs:
                failures.append(f"{fieldname}[{idx}]: no evidence")
                continue
            for ref_idx, ref in enumerate(refs):
                if not (ref.get("location") or "").strip() or not (ref.get("anchor") or "").strip():
                    failures.append(f"{fieldname}[{idx}].evidence[{ref_idx}]: empty location or anchor")
    if failures:
        return _fail(cid, 3, title, f"{len(failures)} uncited value(s)", failures)
    return _ok(cid, 3, title)


def _trap(run: Run, trap_id: str) -> Optional[dict]:
    for trap in run.answer_key.get("traps") or []:
        if trap["id"] == trap_id:
            return trap
    return None


def check_trap_x1_retraction(run: Run) -> CheckResult:
    """A retracted idea must not appear as a committed deliverable. Recorded as
    retracted/conditional is fine; silently promoted to a commitment is not."""
    cid, title = "X1", "Retracted idea is not a committed deliverable"
    trap = _trap(run, "X1")
    if not run.has_brief or not trap:
        return _skip(cid, 3, title, "no brief or trap not defined")

    failures = []
    for idx, entry in enumerate(run.brief.get("deliverables") or []):
        content = entry.get("content") or ""
        hits = [k for k in trap["forbidden_as_committed_keywords"] if k.lower() in content.lower()]
        if hits and entry.get("qualifier") != "conditional":
            failures.append(f"deliverables[{idx}]: {hits} committed with qualifier={entry.get('qualifier')!r}")
    if failures:
        return _fail(cid, 3, title, f"{len(failures)} retracted item(s) committed", failures)
    return _ok(cid, 3, title)


def check_trap_x2_speculation(run: Run) -> CheckResult:
    cid, title = "X2", "Speculative remark carries the conditional qualifier"
    trap = _trap(run, "X2")
    if not run.has_brief or not trap:
        return _skip(cid, 3, title, "no brief or trap not defined")

    failures, found = [], 0
    for fieldname in gates.BRIEF_FIELDS:
        for idx, entry in enumerate(run.brief.get(fieldname) or []):
            content = (entry.get("content") or "").lower()
            if any(k.lower() in content for k in trap["keywords"]):
                found += 1
                if entry.get("qualifier") != "conditional":
                    failures.append(
                        f"{fieldname}[{idx}]: qualifier={entry.get('qualifier')!r}, expected 'conditional'"
                    )
    if failures:
        return _fail(cid, 3, title, f"{len(failures)} speculative entr(ies) not hedged", failures)
    return _ok(cid, 3, title, f"{found} matching entr(ies), all conditional" if found else "not present in draft")


def check_trap_x3_no_invented_total(run: Run) -> CheckResult:
    """No resolved numeric budget total anywhere — except verbatim inside a conflict position,
    where quoting what a source actually said is the whole point."""
    cid, title = "X3", "No resolved numeric budget total in the draft or renders"
    trap = _trap(run, "X3")
    if not run.has_brief or not trap:
        return _skip(cid, 3, title, "no brief or trap not defined")

    conflict_blob = _conflict_text(run.brief)
    outside_conflicts = _brief_text({k: v for k, v in run.brief.items() if k != "conflicts"})
    failures = []
    for pattern in trap["forbidden_patterns"]:
        if pattern in outside_conflicts:
            failures.append(f"brief: {pattern!r} appears outside a conflict position")
        for lang, render in run.renders.items():
            if pattern in render and pattern not in conflict_blob:
                failures.append(f"{lang} render: {pattern!r} appears and is not a quoted conflict position")
    if failures:
        return _fail(cid, 3, title, f"{len(failures)} invented total(s)", failures)
    return _ok(cid, 3, title)


# --------------------------------------------------------------------------------------
# Registry + CLI
# --------------------------------------------------------------------------------------

CHECKS: tuple = (
    check_extracts_validate,
    check_citations_present,
    check_citations_resolve,
    check_garbling_flagged_not_fixed,
    check_brief_validates,
    check_sensitivity_scope,
    check_both_renders_exist,
    check_no_orphan_prose,
    check_glossary_exact_in_renders,
    check_readiness_recomputes,
    check_seeded_conflicts,
    check_seeded_gaps,
    check_garbling_survives_to_the_brief,
    check_no_uncited_values,
    check_trap_x1_retraction,
    check_trap_x2_speculation,
    check_trap_x3_no_invented_total,
)

SYMBOL = {"pass": "✅", "fail": "❌", "skip": "—"}


def grade(run: Run, tier: Optional[int] = None) -> list:
    results = [check(run) for check in CHECKS]
    if tier is not None:
        results = [r for r in results if r.tier == tier]
    return results


def report(run: Run, results: list, as_json: bool = False) -> dict:
    passed = [r for r in results if r.status == "pass"]
    failed = [r for r in results if r.status == "fail"]
    skipped = [r for r in results if r.status == "skip"]
    payload = {
        "run_id": run.manifest.get("run_id"),
        "run_dir": str(run.run_dir),
        "fixture": run.answer_key.get("fixture"),
        "summary": {"passed": len(passed), "failed": len(failed), "skipped": len(skipped)},
        "verdict": "PASS" if not failed else "FAIL",
        "checks": [r.as_dict() for r in results],
    }

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"\nBrief Builder harness · run {payload['run_id']} · fixture {payload['fixture']}\n")
        for r in results:
            print(f"  {SYMBOL[r.status]} {r.check_id:<5} {r.title}")
            if r.detail:
                print(f"         {r.detail}")
            for line in r.evidence[:8] if r.status == "fail" else []:
                print(f"           · {line}")
        print(
            f"\n  {len(passed)} passed · {len(failed)} failed · {len(skipped)} skipped"
            f"   →  {payload['verdict']}\n"
        )

    (run.run_dir / "harness_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Grade a Brief Builder run against the answer key.")
    parser.add_argument("run", help="Run directory, e.g. runs/latest")
    parser.add_argument("--tier", type=int, choices=(1, 2, 3), default=None, help="Grade one tier only")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    try:
        run = load_run(Path(args.run))
    except (HarnessError, gates.GateError) as exc:
        print(f"[harness] {exc}", file=sys.stderr)
        return 2

    results = grade(run, args.tier)
    payload = report(run, results, args.json)
    return 0 if payload["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
