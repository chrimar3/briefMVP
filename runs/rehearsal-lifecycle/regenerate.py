"""Deterministic agency-lifecycle rehearsal on a synthetic copy of runs/tier3 (zero model calls).

    python3 runs/rehearsal-lifecycle/regenerate.py            # rewrite the committed evidence here
    python3 runs/rehearsal-lifecycle/regenerate.py --out DIR  # write it somewhere else (tests)

What it does, in a temporary directory, with fictional actors in distinct roles:

    prepare → init → audit (blocked) → resolve → render replay → triage → checklist →
    catalog bind → deliverables → attest → audit (clean) → approve → handover →
    register creative → creative approve → release → verify → withdraw → verify (withdrawn) →
    verify-log (the hash-chained audit log covers every decision) → retention inventory →
    retention purge --dry-run (previews the pilot-end deletion, audit-log tombstone included)

Every step is the real CLI a champion would type (`python3 -m pipeline.<module> ...`), run as a
subprocess from the repository root; the transcript records each command, its exit code and
the lines of output that matter. Nothing here calls a model, the network or the `claude` CLI.

Preparation (recorded in PREPARATION.json, stated in TRANSCRIPT.md) is a rehearsal device, not
how a live brief is handled:
  * the committed tier3 artifacts are copied; the developer's real name (signer and resolver of
    record) is replaced by a fictional actor, and sign-off is reset to draft;
  * the timeline conflict is reset to open so the lifecycle can resolve it again (same text);
  * the question blocks in the stored renders get their exact linked-evidence tags — a
    deterministic stand-in for a current-template re-render, which would need a model call.
    All ten questions stay in the brief: until go-live precondition T-01 was fixed
    (pipeline/quality.py tag_location) the six whose evidence is a bracketed transcript
    timestamp could never pass the render citation check and had to be moved out; the script
    now refuses, rather than works around, any question the check cannot verify;
  * the "render replay" step copies those prepared renders back after `resolve` archived them.
The creative draft is text written for this exercise (not model output). The spec catalog is
a synthetic catalog on a reserved `.invalid` domain with the stub's invented values.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline import gates, quality  # noqa: E402

HERE = Path(__file__).resolve().parent
TIER3 = REPO / "runs" / "tier3"
PROJECT = REPO / "fixtures" / "northlight_01"
GLOSSARY = REPO / "glossary" / "meltemi.json"

#: Fictional role-holders. Distinct people in every role the separation-of-duties policy
#: names (brief signer, language attester, creative registrant, creative approver).
ACCOUNT_LEAD = "Synthetic Account Lead A"
BILINGUAL = "Synthetic Bilingual Reviewer B"
OPERATOR = "Synthetic Operator O"
CREATIVE_LEAD = "Synthetic Creative Lead C"
TRAFFIC = "Synthetic Traffic Reviewer T"



def real_names() -> list:
    """The person of record in the committed tier3 run, read from it (never hardcoded here):
    the English signer, plus the Greek forms the Greek render uses for the same person."""
    brief = json.loads((TIER3 / "brief.json").read_text(encoding="utf-8"))
    names = {re.sub(r"\s*\(.*\)$", "", brief["signoff"]["signed_by"]).strip()}
    names |= {re.sub(r"\s*\(.*\)$", "", c["resolved_by"]).strip() for c in brief["conflicts"] if c.get("resolved_by")}
    greek = (TIER3 / "brief_el.md").read_text(encoding="utf-8")
    names |= set(re.findall(r"Επιλύθηκε από: ([^(\n]+?) \(", greek))
    names |= set(re.findall(r"από τον ([^(\n]+?) \(", greek))
    return sorted((n for n in names if n), key=len, reverse=True)

PREPARED_FILES = ("brief.json", "brief_el.md", "brief_en.md", "classification.json", "conflict_candidates.json")
PREPARED_DIRS = ("extracts", "fidelity")


class RehearsalError(RuntimeError):
    pass


# -- preparation ---------------------------------------------------------------------------

def _pseudonymise(text: str, names: list) -> str:
    for name in names:
        text = text.replace(name, ACCOUNT_LEAD)
    return text


def _probes(names: list) -> set:
    """Surname stems: catch any inflected form the replacement missed."""
    return {name.split()[-1][:6] for name in names if name.split()}


def _tags(question: dict) -> str:
    """The question's exact linked-evidence tags, in the render order's `[source_id location]` form."""
    return " ".join(f"[{r.get('source_id', '')} {quality.tag_location(r.get('location'))}]"
                    for r in question.get("linked_evidence") or [])


def _verifiable(question: dict) -> bool:
    """Can ANY render satisfy quality.render_coverage for this question? Asked of the gate itself."""
    tags = _tags(question)
    probe = {"open_questions": [question]}
    return not quality.render_coverage(probe, f"## ⚠ Q\n\n1. Probe {tags}\n", "en")


def _question_blocks(render: str):
    """(head, [block, ...], tail) for the ⚠ open-questions section of a render."""
    sections = re.split(r"(?m)^(?=## )", render)
    for i, section in enumerate(sections):
        if section.startswith("## ⚠") and re.search(r"(?m)^1\.\s", section):
            lines = section.splitlines(keepends=True)
            head, blocks = [], []
            for line in lines:
                if re.match(r"^\d+\.\s", line):
                    blocks.append([line])
                elif blocks:
                    blocks[-1].append(line)
                else:
                    head.append(line)
            return "".join(sections[:i]) + "".join(head), ["".join(b) for b in blocks], "".join(sections[i + 1:])
    raise RehearsalError("render has no numbered open-questions section")


def _rewrite_questions(render: str, keep: list, questions: list) -> str:
    head, blocks, tail = _question_blocks(render)
    if len(blocks) != len(questions):
        raise RehearsalError(f"render has {len(blocks)} question blocks for {len(questions)} questions")
    out = []
    for new_number, index in enumerate(keep, 1):
        block = re.sub(r"^\d+\.", f"{new_number}.", blocks[index], count=1)
        first, _, rest = block.partition("\n")
        tags = _tags(questions[index])
        out.append(f"{first.rstrip()} {tags}\n{rest}")
    return head + "".join(out) + tail


def prepare(run: Path, renders_aside: Path) -> dict:
    run.mkdir(parents=True)
    for name in PREPARED_FILES:
        shutil.copy2(TIER3 / name, run / name)
    for name in PREPARED_DIRS:
        shutil.copytree(TIER3 / name, run / name)
    names = real_names()
    if not names:
        raise RehearsalError("could not read the person of record from runs/tier3")
    for path in [run / n for n in PREPARED_FILES] + sorted(run.glob("extracts/*.json")) + sorted(run.glob("fidelity/*")):
        path.write_text(_pseudonymise(path.read_text(encoding="utf-8"), names), encoding="utf-8")

    brief = json.loads((run / "brief.json").read_text(encoding="utf-8"))
    original_questions = copy.deepcopy(brief["open_questions"])
    unverifiable = [i for i, q in enumerate(original_questions) if not _verifiable(q)]
    if unverifiable:
        raise RehearsalError(f"open questions {unverifiable} cannot satisfy pipeline/quality.py render_coverage "
                             f"with their exact evidence tags; fix the check, never drop the questions")
    keep = list(range(len(original_questions)))
    timestamped = sum(any(str(r.get("location", "")).startswith("[") for r in q.get("linked_evidence") or [])
                      for q in original_questions)
    timeline = next(i for i, c in enumerate(brief["conflicts"]) if c["field"] == "timeline")
    reset_resolution = brief["conflicts"][timeline]["resolution"]
    brief["conflicts"][timeline] = {k: v for k, v in brief["conflicts"][timeline].items()
                                    if k not in ("resolution", "resolved_by")}
    brief["conflicts"][timeline]["status"] = "open"
    brief["signoff"] = {"status": "draft"}
    brief["readiness"] = gates.compute_readiness_block(brief)
    gates.validate_brief(brief)
    (run / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    renders_aside.mkdir(parents=True)
    for lang in ("el", "en"):
        render = (run / f"brief_{lang}.md").read_text(encoding="utf-8")
        render = "".join(line for line in render.splitlines(keepends=True)
                         if not re.match(r"^> \*\*(SIGNED OFF|ΥΠΟΓΕΓΡΑΜΜΕΝΟ)", line))
        render = _rewrite_questions(render, keep, original_questions)
        (renders_aside / f"brief_{lang}.md").write_text(render, encoding="utf-8")
        (run / f"brief_{lang}.md").unlink()

    for path in list(run.rglob("*")) + list(renders_aside.rglob("*")):
        if path.is_file() and any(p in path.read_text(encoding="utf-8") for p in _probes(names)):
            raise RehearsalError(f"real name survived pseudonymisation in {path.name}")
    return {
        "source": "runs/tier3 (committed graded run), copied; the original is never modified",
        "pseudonymised": "the developer's name (signer and resolver of record) → " + ACCOUNT_LEAD,
        "signoff_reset": "signed_off → draft (sign-off is what this rehearsal exercises)",
        "conflict_reset": {"field": "timeline", "index": timeline, "resolution_text_reused": reset_resolution},
        "questions_kept": len(keep),
        "questions_with_timestamp_evidence": timestamped,
        "questions_note": ("every open question stays in the brief. Before go-live precondition T-01 was fixed "
                           "(pipeline/quality.py tag_location), render_coverage could not verify a question whose "
                           "evidence is a bracketed transcript timestamp such as [00:03:41], and earlier versions "
                           "of this rehearsal moved those questions out. The script now refuses any question the "
                           "check cannot verify instead of working around it."),
        "render_patch": "stored tier3 renders: sign-off banner line removed, and each question block given its "
                        "exact [source_id location] tags (a transcript timestamp written without its own brackets)",
    }


# -- the lifecycle ----------------------------------------------------------------------------

class Transcript:
    def __init__(self, work: Path, run: Path, package: Path):
        self.steps = []
        self.subs = [(str(run), "$RUN"), (str(package), "$PACKAGE"), (str(work), "$WORK"), (str(REPO), "$REPO")]

    def norm(self, text: str) -> str:
        for real, placeholder in self.subs:
            text = text.replace(real, placeholder)
        return text

    def record(self, step: str, argv: list, code: int, highlights: list, expect: int):
        shown = " ".join(_quote(self.norm(a)) for a in argv)
        self.steps.append({"step": step, "command": shown.replace(sys.executable, "python3"),
                           "exit_code": code, "expected_exit_code": expect,
                           "highlights": [self.norm(h) for h in highlights]})
        if code != expect:
            raise RehearsalError(f"{step}: exit {code}, expected {expect}\n" + "\n".join(highlights))


def _quote(arg: str) -> str:
    return arg if re.fullmatch(r"[A-Za-z0-9_./:$=-]+", arg) else "'" + arg.replace("'", "'\\''") + "'"


def cli(transcript: Transcript, step: str, module: str, *args, expect: int = 0, pick=None) -> str:
    argv = [sys.executable, "-m", module, *map(str, args)]
    result = subprocess.run(argv, cwd=REPO, capture_output=True, text=True, timeout=300)
    output = (result.stdout or "") + (result.stderr or "")
    highlights = pick(output) if pick else [line for line in output.strip().splitlines()[-3:]]
    transcript.record(step, ["python3", "-m", module, *map(str, args)], result.returncode, highlights, expect)
    return result.stdout


def _json_lines(keys):
    def pick(output):
        try:
            data = json.loads(output[output.index("{"):]) if "{" in output else {}
        except ValueError:
            return output.strip().splitlines()[-3:]
        return [f"{k}: {json.dumps(data.get(k), ensure_ascii=False)[:300]}" for k in keys if k in data]
    return pick


def _inventory(output):
    data = json.loads(output)
    areas = {}
    for source in data["sources"]:
        for item in source["copies"]:
            areas[item["area"]] = areas.get(item["area"], 0) + 1
    run = data["runs"][0]
    return [f"runs: {data['run_count']}", f"sources: {len(data['sources'])}",
            f"byte copies by area: {json.dumps(dict(sorted(areas.items())))}",
            f"personal records: {len(run['personal_records'])}", f"release packages: {len(run['release_packages'])}"]


def _purge_preview(output):
    data = json.loads(output)
    stone = data.get("audit_log_deleted") or {}
    return [f"dry_run: {json.dumps(data['dry_run'])}",
            f"audit_log_deleted: entries {stone.get('entries')}, verified_intact {json.dumps(stone.get('verified_intact'))}",
            f"release_packages_not_deleted: {len(data['release_packages_not_deleted'])}"]


def _blockers(output):
    try:
        data = json.loads(output[output.index("{"):])
    except ValueError:
        return output.strip().splitlines()[-3:]
    blockers = data.get("blockers") or []
    kinds = {}
    for b in blockers:
        kind = "missing render" if b.startswith("no ") and " render at " in b else b.split(":")[0].split(".")[0][:60]
        kinds[kind] = kinds.get(kind, 0) + 1
    return [f"status: {data.get('status')}", f"blockers: {len(blockers)} {json.dumps(kinds, ensure_ascii=False)}"] + \
           [f"notice: {n}" for n in data.get("notices") or []]


def write_catalog(path: Path, spec_ids: list) -> None:
    stub = json.loads((REPO / "config" / "channel_specs.json").read_text(encoding="utf-8"))
    today = date.today()
    rows = []
    for row in stub["specs"]:
        if row["id"] in spec_ids:
            rows.append({**{k: v for k, v in row.items() if not k.startswith("_")},
                         "source_url": f"https://specs.example.invalid/synthetic/{row['id']}",
                         "checked_by": TRAFFIC, "checked_on": (today - timedelta(days=1)).isoformat(),
                         "review_due": (today + timedelta(days=180)).isoformat()})
    path.write_text(json.dumps({"owner": TRAFFIC, "_rehearsal": "Synthetic catalog: invented values on a reserved "
                                "domain; no platform verification is claimed.", "specs": rows},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_creative_draft(path: Path, brief: dict) -> None:
    lines = ["> CREATIVE DRAFT — rehearsal text written for the synthetic lifecycle exercise (not model output).", "",
             "# Creative brief — synthetic rehearsal", "",
             "## What the work must achieve", ""]
    lines += [f"- Campaign objective {i + 1}, as signed off. [brief:objectives:{i}]" for i in range(len(brief["objectives"]))]
    lines += ["", "## Messages to carry", ""]
    lines += [f"- Key message {i + 1}, as signed off. [brief:key_messages:{i}]" for i in range(len(brief["key_messages"]))]
    lines += ["", "## Mandatories (verbatim from the signed brief)", ""]
    lines += [f"- {entry['content']} [brief:mandatories:{i}]" for i, entry in enumerate(brief["mandatories"])]
    lines += ["", "## Strategic tensions (questions for the creative team)", "",
              "- The resolved audience differs from the RFP's original audience; which executions change? [brief:objectives:0]",
              ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def lifecycle(work: Path) -> tuple:
    run, aside, package = work / "run", work / "prepared_renders", work / "packages" / "release-01"
    preparation = prepare(run, aside)
    t = Transcript(work, run, package)

    cli(t, "init", "pipeline.agency", "init", run, "--project", PROJECT, "--glossary", GLOSSARY,
        "--profile", "creative_production", "--actor", OPERATOR)
    cli(t, "audit (before review)", "pipeline.agency", "audit", run, expect=2, pick=_blockers)

    brief = json.loads((run / "brief.json").read_text(encoding="utf-8"))
    timeline = preparation["conflict_reset"]["index"]
    cli(t, "resolve timeline conflict", "pipeline.agency", "resolve", run, "--index", timeline,
        "--actor", ACCOUNT_LEAD, "--text", preparation["conflict_reset"]["resolution_text_reused"])
    for lang in ("el", "en"):
        shutil.copy2(aside / f"brief_{lang}.md", run / f"brief_{lang}.md")
    t.steps.append({"step": "render replay", "command": "(copy the prepared renders into $RUN; live runs use "
                    "`python3 pipeline/runner.py ... --stage render`, a model call)", "exit_code": 0,
                    "expected_exit_code": 0, "highlights": ["brief_el.md", "brief_en.md"]})

    queue = json.loads(cli(t, "question queue", "pipeline.agency", "queue", run,
                           pick=lambda out: [f"{len(json.loads(out))} question group(s)"]))
    for item in queue:
        cli(t, f"triage {item['id']}", "pipeline.agency", "answer", run, "--id", item["id"], "--status", "open",
            "--text", "Put to the client in the question pack; does not block the agreed creative work.",
            "--owner", "Account lead", "--priority", "nonblocking", "--actor", ACCOUNT_LEAD)

    answers = {
        "objective_and_audience": ("Launch objectives as signed off; audience per the resolved conflict.", ["objectives:0", "objectives:1"]),
        "deliverables_and_variants": ("Deliverables as listed in the signed brief.", ["deliverables:0", "deliverables:1"]),
        "mandatories_and_rights": ("Brand mandatories apply verbatim.", ["mandatories:0", "mandatories:4"]),
        "dependencies": ("Brand guidelines version stated in the brief govern the work.", ["mandatories:7"]),
        "approvals_and_dates": ("Launch date per the resolved timeline conflict.", ["timeline:0"]),
    }
    for key, (value, refs) in answers.items():
        cli(t, f"checklist {key}", "pipeline.agency_edit", "checklist", run, "--key", key, "--value", value,
            "--owner", "Account lead", "--actor", ACCOUNT_LEAD, *[x for r in refs for x in ("--ref", r)])

    catalog = work / "synthetic-traffic-catalog-v1.json"
    write_catalog(catalog, ["key_visual_digital_master", "tiktok_infeed_video"])
    cli(t, "bind traffic catalog", "pipeline.spec_catalog", run, catalog, "--actor", TRAFFIC)
    cli(t, "deliverable key-visual", "pipeline.agency_edit", "deliverable", run, "--id", "key-visual",
        "--spec-id", "key_visual_digital_master", "--quantity", "1", "--language", "el", "--language", "en",
        "--deadline", "2026-09-08", "--owner", "Production lead", "--approval-owner", "Account lead",
        "--actor", TRAFFIC, "--ref", "deliverables:0")
    cli(t, "deliverable tiktok-cut (depends on key-visual)", "pipeline.agency_edit", "deliverable", run,
        "--id", "tiktok-cut", "--spec-id", "tiktok_infeed_video", "--quantity", "2", "--language", "el",
        "--deadline", "2026-09-12", "--owner", "Production lead", "--approval-owner", "Account lead",
        "--actor", TRAFFIC, "--ref", "deliverables:0", "--dependency", "key-visual", "--duration-seconds", "15")

    audit = cli(t, "audit (before language review)", "pipeline.agency", "audit", run, expect=2, pick=_blockers)
    remaining = json.loads(audit[audit.index("{"):])["blockers"]
    if any(not b.startswith("Current source-completeness") for b in remaining):
        raise RehearsalError("unexpected blockers before attestation: " + "; ".join(remaining))
    cli(t, "attest (bilingual reviewer)", "pipeline.agency", "attest", run, "--actor", BILINGUAL,
        "--greek-register", "4", "--notes", "Rehearsal attestation on synthetic renders; Greek checked against the sources.",
        "--checks", *quality.field_review_checklist())
    cli(t, "audit (clean)", "pipeline.agency", "audit", run, pick=_blockers)
    cli(t, "approve brief (account lead)", "pipeline.agency", "approve", run, "--actor", ACCOUNT_LEAD,
        "--summary", "Rehearsal: timeline conflict resolved; questions triaged non-blocking; checklist and matrix reviewed.")
    cli(t, "handover", "pipeline.agency", "handover", run)

    brief = json.loads((run / "brief.json").read_text(encoding="utf-8"))
    draft = work / "creative-draft-rehearsal.md"
    write_creative_draft(draft, brief)
    cli(t, "register creative (operator)", "pipeline.delivery", "register", run, "--draft", draft,
        "--actor", OPERATOR, pick=_json_lines(["registered_by", "revision"]))
    cli(t, "approve creative (creative lead)", "pipeline.delivery", "approve", run, "--actor", CREATIVE_LEAD,
        "--notes", "Rehearsal review: references, mandatories and deliverables checked on synthetic material.",
        "--checks", "all_facts_cited", "qualifiers", "mandatories", "brand_voice", "deliverables",
        "rights_and_permissions", "client_safe", pick=_json_lines(["actor", "approved_at"]))
    cli(t, "release package", "pipeline.delivery", "release", run, "--output", package, "--actor", OPERATOR)
    cli(t, "verify package against the run", "pipeline.release_control", "verify", package, "--run", run,
        pick=_json_lines(["valid", "receipt_matched", "withdrawn", "errors"]))
    cli(t, "withdraw approval (account lead)", "pipeline.release_control", "withdraw", run, "--actor", ACCOUNT_LEAD,
        "--reason", "Rehearsal: client asked to pause the campaign; withdrawal exercised end to end.",
        pick=_json_lines(["actor", "reason"]))
    cli(t, "verify package after withdrawal", "pipeline.release_control", "verify", package, "--run", run,
        expect=2, pick=_json_lines(["valid", "receipt_matched", "withdrawn", "errors"]))
    cli(t, "verify audit log", "pipeline.release_control", "verify-log", run,
        pick=_json_lines(["valid", "entries", "errors"]))
    cli(t, "retention inventory", "pipeline.retention", "inventory", "--runs", run, pick=_inventory)
    cli(t, "retention purge (dry run)", "pipeline.retention", "purge", "--run", run, "--dry-run",
        "--actor", OPERATOR, "--reason", "Rehearsal: pilot-end deletion previewed, nothing deleted.",
        pick=_purge_preview)
    return preparation, t, run, package


RECORDS = ("brief.json", "agency_inputs.json", "clarifications.json", "language_review.json", "creative_draft.json",
           "releases.json", "approval_withdrawals.json", "handover.json", "agency_audit.md", "input_snapshot.json",
           "audit_log.jsonl", "amendments.json", "coverage_decisions.json")


def write_evidence(out: Path, preparation: dict, t: Transcript, run: Path, package: Path) -> None:
    if (out / "records").exists():
        shutil.rmtree(out / "records")
    records = out / "records"
    (records / "package").mkdir(parents=True)
    for name in RECORDS:
        if (run / name).is_file():
            (records / name).write_text(t.norm((run / name).read_text(encoding="utf-8")), encoding="utf-8")
    # The approvals the withdrawal archived, found by the hashes it recorded.
    withdrawn = {sha: name for event in json.loads((run / "approval_withdrawals.json").read_text(encoding="utf-8"))
                 for name, sha in event["approval_hashes"].items()}
    for path in sorted((run / "history").glob("*/*approval.json")):
        name = withdrawn.get(hashlib.sha256(path.read_bytes()).hexdigest())
        if name:
            (records / f"withdrawn_{name}").write_text(t.norm(path.read_text(encoding="utf-8")), encoding="utf-8")
    for path in sorted(package.iterdir()):
        (records / "package" / path.name).write_text(t.norm(path.read_text(encoding="utf-8")), encoding="utf-8")
    (out / "PREPARATION.json").write_text(json.dumps(preparation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "transcript.json").write_text(json.dumps(t.steps, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Agency lifecycle rehearsal — transcript", "",
             "Generated by `python3 runs/rehearsal-lifecycle/regenerate.py` on a synthetic copy of `runs/tier3`.",
             "Zero model calls. Fictional actors in distinct roles: "
             f"{ACCOUNT_LEAD} (brief signer, resolver, withdrawal), {BILINGUAL} (language attestation), "
             f"{OPERATOR} (init, creative registration, release), {CREATIVE_LEAD} (creative approval), "
             f"{TRAFFIC} (catalog, deliverables).", "",
             "What this proves: the deterministic governance path runs end to end as a champion would type it. "
             "What it does not prove: model output quality, Greek quality, real staff time, or that the "
             "preparation steps below reflect a live brief (they are a rehearsal device).", "",
             "## Preparation", ""]
    lines += [f"- **{k}**: {json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v}" for k, v in preparation.items()]
    lines += ["", "## Steps", "", "| # | Step | Exit | Command |", "|---|---|---|---|"]
    for i, step in enumerate(t.steps, 1):
        lines.append(f"| {i} | {step['step']} | {step['exit_code']} | `{step['command'][:220]}{'…' if len(step['command']) > 220 else ''}` |")
    lines += ["", "## Output that matters", ""]
    for i, step in enumerate(t.steps, 1):
        if step["highlights"]:
            lines.append(f"**{i}. {step['step']}**")
            lines += [f"    {h}" for h in step["highlights"]]
            lines.append("")
    lines += ["Records: `records/` (final run records and the delivered package, paths normalised to $RUN / $PACKAGE / $WORK).", ""]
    (out / "TRANSCRIPT.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE, help="Where TRANSCRIPT.md, transcript.json and records/ go")
    parser.add_argument("--keep-workdir", action="store_true", help="Do not delete the temporary working directory")
    args = parser.parse_args(argv)
    work = Path(tempfile.mkdtemp(prefix="bb-rehearsal-")).resolve()
    try:
        preparation, transcript, run, package = lifecycle(work)
        args.out.mkdir(parents=True, exist_ok=True)
        write_evidence(args.out, preparation, transcript, run, package)
        print(f"rehearsal complete: {len(transcript.steps)} steps → {args.out}")
        return 0
    except RehearsalError as exc:
        print(f"rehearsal FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        if args.keep_workdir:
            print(f"workdir kept: {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
