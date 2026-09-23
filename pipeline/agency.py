"""Companion review workflow: python -m pipeline.agency --help.

All decisions are explicit human commands. No network, integrations, schema changes,
or permission to ingest real data. Reports are evidence checks plus human attestations.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import copy
import json
import sys
from pathlib import Path
from typing import Optional

from pipeline import approval, clarifications, client_pack, gates, handover, quality, revisions, stages, review, docview

PROFILES = gates.CONFIG_DIR / "campaign_profiles.json"

#: The project folder's data declaration (owner decision 2026-09-22 #4; W6 owns the gate).
DATA_DECLARATION = "data_declaration.json"


class SeparationOfDutiesError(ValueError):
    """One person tried to hold two roles that must be held by different people."""


def same_person(a, b) -> bool:
    """Actors are typed names, so compare them the way a reviewer would read them."""
    norm = lambda s: " ".join(str(s or "").casefold().split())
    return bool(norm(a)) and norm(a) == norm(b)


def project_data_class(run):
    """The data_class declared by the project this run was made from, or None.

    The project folder is where the run's recorded sources live (input_snapshot.json). No
    snapshot, sources spread over several folders, or a missing/invalid declaration all mean
    "not known to be synthetic" — the safe reading.
    """
    snapshot = revisions.load(Path(run) / "input_snapshot.json", {}) or {}
    folders = {Path(item["path"]).parent for key, item in snapshot.items()
               if key.startswith("source:") and isinstance(item, dict) and item.get("path")}
    if len(folders) != 1:
        return None
    try:
        declaration = json.loads((folders.pop() / DATA_DECLARATION).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return declaration.get("data_class") if isinstance(declaration, dict) else None


def solo_rehearsal_waiver(run, role_pair):
    """The recorded waiver for `--solo-rehearsal`, refused unless the project is synthetic."""
    data_class = project_data_class(run)
    if data_class != "synthetic":
        raise SeparationOfDutiesError(
            f"--solo-rehearsal is only for synthetic rehearsals; this project declares "
            f"data_class={data_class!r} (a missing declaration counts as non-synthetic)")
    return {"waived": "solo_rehearsal", "roles": list(role_pair), "data_class": data_class,
            "at": revisions.timestamp()}


def require_distinct(role_a, actor_a, role_b, actor_b):
    if same_person(actor_a, actor_b):
        raise SeparationOfDutiesError(
            f"Separation of duties: the {role_b} ({actor_b!r}) must be a different person from the "
            f"{role_a}. Use a second reviewer, or --solo-rehearsal on a synthetic rehearsal only.")


def brief_binding(brief) -> str:
    """What a coverage exclusion is bound to: the brief's content, not its sign-off state."""
    return revisions.digest({k: v for k, v in brief.items() if k not in ("signoff", "readiness")})


def _question_removal_allowed(run, old, candidate):
    """Problems with open questions the candidate drops. A question may leave the brief only
    after a human triage decision closed it (answered / duplicate / not worth asking)."""
    kept = candidate.get("open_questions") or []
    removed = [q for q in old.get("open_questions") or [] if q not in kept]
    if not removed:
        return []
    decided = {item["id"]: item["decision"] for item in clarifications.queue(
        old, revisions.load(run / "clarifications.json", {}))}
    problems = []
    for question in removed:
        qid = clarifications.queue({"open_questions": [question]})[0]["id"]
        decision = decided.get(qid) or {}
        if decision.get("status") not in ("answered", "duplicate", "not_worth_asking"):
            problems.append(f"open question {question.get('suggested_question_for_client', '')!r} is removed "
                            f"or reworded without a human triage decision closing it (`agency answer`)")
    return problems


def _conflict_changes(old, candidate):
    """Problems with conflict edits. Existing conflicts are evidence plus a human-only
    resolution: they stay exactly as they are here and change only through `agency resolve`."""
    before, after = old.get("conflicts") or [], candidate.get("conflicts") or []
    problems = []
    if len(after) < len(before):
        problems.append(f"the candidate drops {len(before) - len(after)} conflict(s)")
    for i, (was, now) in enumerate(zip(before, after)):
        if was != now:
            fields = sorted(k for k in set(was) | set(now) if was.get(k) != now.get(k))
            problems.append(f"conflict {i} changes {fields}")
    for i, added in enumerate(after[len(before):], len(before)):
        if added.get("status") != "open" or added.get("resolution") or added.get("resolved_by"):
            problems.append(f"new conflict {i} must be added as status 'open' with no resolution")
    return problems


def read_run(run):
    brief = revisions.load(run / "brief.json")
    if not brief:
        raise ValueError("Run has no brief.json")
    gates.validate_brief(brief)
    gates.enforce_sensitivity_tier(brief["meta"]["sensitivity_tier"])
    return brief


def extract_records(run):
    return {p.stem: revisions.load(p) for p in sorted((run / "extracts").glob("*.json"))}


def campaign_check(inputs, brief):
    profiles = revisions.load(PROFILES)["profiles"]
    if inputs.get("campaign_profile") not in profiles:
        return ["Select a recognized campaign_profile"]
    known = {quality.ref_key(ref) for _, _, refs in quality.destinations(brief) for ref in refs}
    problems = []
    answers = inputs.get("checklist", {})
    for key in profiles[inputs["campaign_profile"]]:
        answer = answers.get(key, {})
        if not answer.get("value", "").strip() or not answer.get("owner", "").strip():
            problems.append(f"campaign.{key}: needs a sourced answer and an owner")
        refs = answer.get("evidence") or []
        if not refs or any(quality.ref_key(ref) not in known for ref in refs):
            problems.append(f"campaign.{key}: evidence must reference the canonical brief; record new evidence as input first")
    return problems


def audit(run, *, persist=True):
    run = Path(run)
    brief = read_run(run)
    inputs = revisions.load(run / "agency_inputs.json", {})
    problems, notices = [], []
    if not (run / "input_snapshot.json").exists():
        problems.append("No input baseline; initialize with explicit project/glossary and human attribution")
    else:
        try:
            revisions.verify_inputs(run)
            revisions.verify_evidence(run)
        except ValueError as exc:
            problems.append(str(exc))
    extracts = extract_records(run)
    if not extracts:
        problems.append("No validated extracts available for coverage review")
    records = quality.coverage(brief, extracts)
    exclusions = revisions.load(run / "coverage_decisions.json", {})
    binding = brief_binding(brief)
    for record in records:
        decision = exclusions.get(record["id"], {})
        # An exclusion holds only for the brief content it was decided against: amend the
        # brief and the human looks again. An unbound (legacy or hand-written) entry counts
        # for nothing.
        excluded = (decision.get("actor") and decision.get("reason")
                    and decision.get("brief_binding") == binding)
        if not record["destinations"] and not excluded:
            stale = " (exclusion was made against an earlier brief revision)" if decision else ""
            problems.append(f"coverage.{record['id']}: {record['field']} fact has no destination{stale}")
    # Re-run structural synthesis checks as draft without erasing stored human decisions.
    # Schema, evidence, render fidelity and human semantic reviews are separate checks.
    known_sources = {s["source_id"] for s in brief["meta"]["sources"]}
    extracted_refs = {quality.ref_key(r["evidence"]) for r in records}
    for _, destination, refs in quality.destinations(brief):
        for ref in refs:
            if ref.get("source_id") not in known_sources or quality.ref_key(ref) not in extracted_refs:
                problems.append(f"{destination}: evidence absent from extract ledger")
    snapshot = revisions.load(run / "input_snapshot.json", {})
    for source_id, extract in extracts.items():
        source_record = snapshot.get(f"source:{source_id}")
        if not source_record or not Path(source_record["path"]).is_file():
            problems.append(f"{source_id}: source unavailable for citation verification")
        else:
            source_text = Path(source_record["path"]).read_text(encoding="utf-8")
            problems.extend(f"{source_id}: {p}" for p in gates.verify_citations(extract, source_text))
            problems.extend(f"{source_id}: {p}" for p in gates.verify_internal_conflict_citations(extract, source_text))
    if gates.compute_readiness_block(brief)["verdict"] != "ready_for_review":
        problems.append("Canonical brief is below the existing readiness threshold")
    glossary_item = snapshot.get("glossary")
    glossary = revisions.load(glossary_item["path"], {}) if glossary_item else {}
    problems.extend(stages.check_render(run / "brief_el.md", run / "brief_en.md", brief, glossary))
    for lang in ("el", "en"):
        path = run / f"brief_{lang}.md"
        if path.exists():
            problems.extend(quality.render_coverage(brief, path.read_text(encoding="utf-8"), lang))
    q = clarifications.queue(brief, revisions.load(run / "clarifications.json", {}))
    if (run / 'question_exchange' / 'proposals').exists():
        from pipeline.question_exchange import pending_proposals
        if pending_proposals(run):
            problems.append('Unreviewed clarification replies; ingest relevant answers into a revised brief or explicitly dismiss irrelevant proposals')
    for item in q:
        decision = item["decision"]
        if not decision:
            problems.append(f"question.{item['id']}: needs human triage")
        elif decision["status"] == "answered":
            # Stored answers are a log, not new canonical evidence. Do not pretend the
            # brief changed merely because someone filled in a companion record.
            problems.append(f"question.{item['id']}: answer recorded; update sources/brief and remove the answered question before approval")
        elif decision["status"] == "open" and decision["priority"] == "blocking":
            problems.append(f"question.{item['id']}: unresolved blocker")
    for i, conflict in enumerate(brief.get("conflicts") or []):
        if conflict.get("status") != "resolved_by_human" or not all(conflict.get(k, "").strip() for k in ("resolution", "resolved_by")):
            problems.append(f"conflict.{i}: needs a human resolution")
    problems.extend(campaign_check(inputs, brief))
    spec_path = snapshot.get("channel_specs", {}).get("path", str(gates.CONFIG_DIR / "channel_specs.json"))
    specs = revisions.load(spec_path)
    if not inputs.get("deliverables"):
        problems.append("A sourced deliverables matrix is required")
    else:
        problems.extend(handover.validate(inputs["deliverables"], specs, brief))
    if specs.get("_stub_notice"):
        notices.append("Channel specs are a synthetic stub. Release requires a verified traffic catalog; no production readiness claim.")
    attestation = revisions.load(run / "language_review.json", {})
    if (attestation.get("fingerprint") != revisions.fingerprint(run)
            or not attestation.get("actor")
            or not all(attestation.get("checks", {}).get(key) is True for key in quality.field_review_checklist())
            or type(attestation.get("greek_register")) is not int
            or not 1 <= attestation["greek_register"] <= 5):
        problems.append("Current source-completeness, bilingual meaning, qualifiers and brand-voice human review required")
    result = {"fingerprint": revisions.fingerprint(run), "checked_at": revisions.timestamp(),
              "status": "blocked" if problems else "reviewed", "blockers": problems, "notices": notices,
              "coverage": records, "questions": q,
              "boundary": "Evidence links and structure checked automatically. Semantic judgments are human attestations. Fixtures-only data; creative delivery requires separate human approval."}
    if persist:
        revisions.write_json(run / "agency_audit.json", result)
    lines = ["# Agency review", "", result["boundary"], "", f"Status: {result['status']}", ""]
    lines += [f"- {p}" for p in problems + notices]
    lines += ["", "## Fact coverage", ""] + [f"- {r['id']} · {r['field']}: {r['value']} → {', '.join(r['destinations']) or 'no destination; review exclusion if recorded'}" for r in records]
    lines += ["", "## Clarification queue", ""] + [f"- {item['id']}: {item['question']} ({(item['decision'] or {}).get('status', 'untriaged')})" for item in q]
    if persist:
        (run / "agency_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def initialize(run, project, glossary, profile, actor):
    brief = read_run(run)
    if not actor.strip():
        raise ValueError("Human actor required")
    if (run / "agency_inputs.json").exists():
        raise ValueError("Agency inputs already exist; edit the companion record, do not overwrite it")
    sources = gates.discover_sources(project)
    config = revisions.load(glossary)
    if config.get("client_id") != brief["meta"]["client_id"]:
        raise ValueError("Glossary client does not match brief")
    if {s.source_id for s in sources} != {s['source_id'] for s in brief['meta']['sources']}:
        raise ValueError("Project sources do not match the brief")
    paths = {f"source:{s.source_id}": s.path for s in sources}
    paths.update({"glossary": glossary, "channel_specs": gates.CONFIG_DIR / "channel_specs.json", "campaign_profiles": PROFILES})
    prior = revisions.load(run / "input_snapshot.json", {})
    current = revisions.input_state(paths)
    if prior:
        revisions.verify_inputs(run)
        for key, value in current.items():
            if key in prior and prior[key] != value:
                raise ValueError("Inputs changed; create a new run")
        current = {**prior, **current}
    revisions.write_json(run / "input_snapshot.json", current)
    profiles = revisions.load(PROFILES)["profiles"]
    revisions.write_json(run / "agency_inputs.json", {
        "campaign_profile": profile, "initialized_by": actor,
        "baseline_origin": "runner snapshot" if prior else "human-adopted legacy evidence; source completeness review required",
        "checklist": {k: {"prompt": v, "value": "", "owner": "", "evidence": []} for k, v in profiles[profile].items()},
        "deliverables": []})
    revisions.capture_evidence(run, {key: value["path"] for key, value in current.items()})


def resolve(run, index, actor, resolution):
    brief = read_run(run)
    if not actor.strip() or not resolution.strip():
        raise ValueError("Named human and resolution are required")
    if not 0 <= index < len(brief["conflicts"]):
        raise ValueError("Conflict index does not exist")
    candidate = copy.deepcopy(brief)
    candidate["conflicts"][index].update(status="resolved_by_human", resolved_by=actor, resolution=resolution)
    candidate["signoff"] = {"status": "draft"}
    gates.validate_brief(candidate)
    # Preserve the actual pre-review draft for scoring and history.
    revisions.archive(run, ["brief.json", "approval.json", "language_review.json", "brief_el.md", "brief_en.md", "brief_el.html", "brief_en.html", "brief_review.html", "creative"])
    revisions.write_json(run / "brief.json", candidate)
    revisions.append_audit(run, "conflict_resolved", actor, record="brief.json",
                           details={"conflict": index, "resolution": resolution})


def apply_candidate(run, candidate_path, actor, reason):
    old = read_run(run)
    candidate = revisions.load(candidate_path)
    if not actor.strip() or not reason.strip():
        raise ValueError("Named human and amendment reason required")
    gates.validate_brief(candidate)
    if candidate["meta"] != old["meta"]:
        raise ValueError("Amendments cannot change project/source identity; create a new run")
    # Conflict resolution and question closure have their own attributed commands; an
    # amendment cannot do either on the side (PRD DR-10: resolution is human-only, by name).
    guarded = _conflict_changes(old, candidate) + _question_removal_allowed(run, old, candidate)
    if guarded:
        raise ValueError("Amendment refused — conflicts change only through `agency resolve`, and open "
                         "questions leave the brief only after `agency answer` closes them: " + "; ".join(guarded))
    candidate["signoff"] = {"status": "draft"}
    candidate["readiness"] = gates.compute_readiness_block(candidate)
    revisions.archive(run, ["brief.json", "approval.json", "language_review.json", "brief_el.md", "brief_en.md",
                            "brief_el.html", "brief_en.html", "brief_review.html", "creative"])
    revisions.write_json(run / "brief.json", candidate)
    history = revisions.load(run / "amendments.json", [])
    entry = {"actor": actor, "reason": reason, "at": revisions.timestamp(), "changes": revisions.changes(old, candidate)}
    history.append(entry)
    revisions.write_json(run / "amendments.json", history)
    revisions.append_audit(run, "brief_amended", actor, record={"file": "amendments.json", "entry": entry},
                           details={"reason": reason})


def approve(run, actor, summary, solo_rehearsal=False):
    if not actor.strip() or not summary.strip():
        raise ValueError("Human actor and edit/review summary are required")
    result = audit(run)
    if result["blockers"]:
        raise ValueError("Approval blocked: " + "; ".join(result["blockers"]))
    attester = revisions.load(run / "language_review.json", {}).get("actor")
    if solo_rehearsal:
        separation = solo_rehearsal_waiver(run, ("language_attester", "brief_signer"))
    else:
        require_distinct("language/source reviewer", attester, "brief signer", actor)
        separation = {"enforced": ["language_attester != brief_signer"]}
    revisions.require_intact_audit_log(run)
    brief = read_run(run)
    revisions.archive(run, ["brief.json", "approval.json", "language_review.json", "brief_review.html", "brief_el.html", "brief_en.html"], copy_only=True)
    brief["signoff"] = {"status": "signed_off", "signed_by": actor, "signed_ts": revisions.timestamp(), "edits_summary": summary}
    gates.validate_brief(brief)
    revisions.write_json(run / "brief.json", brief)
    review.write_review(run)
    docview.write_documents(run)
    # Only signoff metadata changed. Transfer the existing human attestation to this
    # exact signed snapshot, never to a change in content, renders or companion data.
    attestation = revisions.load(run / "language_review.json")
    attestation["fingerprint"] = revisions.fingerprint(run)
    revisions.write_json(run / "language_review.json", attestation)
    revisions.write_json(run / "approval.json", {"actor": actor, "signed_at": revisions.timestamp(), "fingerprint": revisions.fingerprint(run), "language_review_sha256": revisions.file_hash(run / "language_review.json"),
                                                 "separation_of_duties": separation})
    revisions.append_audit(run, "brief_approved", actor, record="approval.json",
                           details={"summary": summary, "separation_of_duties": separation})


def main(argv: Optional[list] = None) -> int:
    """The `python -m pipeline.agency` command line: one explicit human command per call."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "audit", "queue", "answer", "resolve", "exclude", "attest", "approve", "diff", "handover", "apply", "carry-decisions"):
        p = commands.add_parser(name)
        p.add_argument("run", type=Path)
        if name in ("init", "answer", "resolve", "exclude", "attest", "approve", "apply", "carry-decisions"):
            p.add_argument("--actor", required=True)
        if name == "init":
            p.add_argument("--project", type=Path, required=True)
            p.add_argument("--glossary", type=Path, required=True)
            p.add_argument("--profile", choices=list(revisions.load(PROFILES)["profiles"]), required=True)
        if name == "answer":
            p.add_argument("--id", required=True)
            p.add_argument("--status", choices=["answered", "duplicate", "not_worth_asking", "open"], required=True)
            p.add_argument("--text", required=True)
            p.add_argument("--evidence", default="")
            p.add_argument("--owner", required=True)
            p.add_argument("--priority", choices=["blocking", "nonblocking"], required=True)
        if name == "carry-decisions":
            p.add_argument("--parent", type=Path, required=True)
        if name == "apply":
            p.add_argument("--candidate", type=Path, required=True)
            p.add_argument("--reason", required=True)
        if name == "resolve":
            p.add_argument("--index", type=int, required=True)
            p.add_argument("--text", required=True)
        if name == "exclude":
            p.add_argument("--fact", required=True)
            p.add_argument("--reason", required=True)
        if name == "attest":
            p.add_argument("--checks", nargs="+", choices=quality.field_review_checklist(), required=True)
            p.add_argument("--greek-register", type=int, choices=range(1, 6), required=True)
            p.add_argument("--notes", required=True)
        if name == "approve":
            p.add_argument("--summary", required=True)
            p.add_argument("--solo-rehearsal", action="store_true",
                           help="Waive attester≠signer for a SYNTHETIC rehearsal only; recorded in "
                                "approval.json and the audit log, refused for non-synthetic projects")
        if name == "diff":
            p.add_argument("--before", type=Path, required=True, help="Earlier brief.json")
    p = commands.add_parser("client-pack")
    p.add_argument("pack", type=Path)
    p.add_argument("--client", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with revisions.run_lock(args.run) if hasattr(args, "run") else nullcontext():
            if args.command == "client-pack":
                print(client_pack.materialize(revisions.load(args.pack), args.client, args.output))
                return 0
            run = args.run.resolve()
            if args.command == "init":
                initialize(run, args.project, args.glossary, args.profile, args.actor)
            elif args.command == "audit":
                result = audit(run)
                print(json.dumps({k: result[k] for k in ("status", "blockers", "notices")}, ensure_ascii=False, indent=2))
                return 2 if result["blockers"] else 0
            elif args.command in ("queue", "answer"):
                q = clarifications.queue(read_run(run), revisions.load(run / "clarifications.json", {}))
                if args.command == "queue":
                    print(json.dumps(q, ensure_ascii=False, indent=2))
                else:
                    clarifications.record(run, q, args.id, args.status, args.actor, args.text, args.evidence, args.owner, args.priority)
                    revisions.append_audit(run, "question_triaged", args.actor, record="clarifications.json",
                                           details={"question": args.id, "status": args.status})
            elif args.command == "carry-decisions":
                with revisions.run_lock(args.parent):
                    print(json.dumps(clarifications.carry_decisions(args.parent, run, args.actor), indent=2))
            elif args.command == "apply":
                apply_candidate(run, args.candidate, args.actor, args.reason)
            elif args.command == "resolve":
                resolve(run, args.index, args.actor, args.text)
            elif args.command == "exclude":
                brief = read_run(run)
                records = quality.coverage(brief, extract_records(run))
                if args.fact not in {r["id"] for r in records} or not args.reason.strip() or not args.actor.strip():
                    raise ValueError("Existing fact ID, human actor and reason are required")
                decisions = revisions.load(run / "coverage_decisions.json", {})
                decisions[args.fact] = {"actor": args.actor, "reason": args.reason, "at": revisions.timestamp(),
                                        "brief_binding": brief_binding(brief)}
                revisions.write_json(run / "coverage_decisions.json", decisions)
                revisions.append_audit(run, "coverage_excluded", args.actor, record="coverage_decisions.json",
                                       details={"fact": args.fact, "reason": args.reason})
            elif args.command == "attest":
                read_run(run)
                if not args.actor.strip() or not args.notes.strip():
                    raise ValueError("Named reviewer and review notes required")
                revisions.write_json(run / "language_review.json", {"actor": args.actor, "notes": args.notes,
                    "greek_register": args.greek_register, "checks": {k: k in args.checks for k in quality.field_review_checklist()},
                    "fingerprint": revisions.fingerprint(run), "reviewed_at": revisions.timestamp()})
                revisions.append_audit(run, "language_attested", args.actor, record="language_review.json",
                                       details={"checks": sorted(args.checks), "greek_register": args.greek_register})
            elif args.command == "approve":
                approve(run, args.actor, args.summary, solo_rehearsal=args.solo_rehearsal)
            elif args.command == "diff":
                print(json.dumps(revisions.changes(revisions.load(args.before), read_run(run)), ensure_ascii=False, indent=2))
            elif args.command == "handover":
                approval.require_current_approval(run)
                result = audit(run)
                if result["blockers"]:
                    raise ValueError("Handover blocked; inspect agency_audit.md")
                rows = revisions.load(run / "agency_inputs.json")["deliverables"]
                revisions.write_json(run / "handover.json", {"mode": "APPROVED BRIEF HANDOVER", "creative_release": "requires separate creative approval", "fingerprint": revisions.fingerprint(run), "deliverables": rows, "notices": result["notices"]})
            return 0
    except (ValueError, OSError, KeyError, TypeError, gates.GateError) as exc:
        print(f"agency: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
