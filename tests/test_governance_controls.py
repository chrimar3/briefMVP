"""Human-governance hardening (r1-W2): amendments cannot resolve or delete, exclusions are
bound to the brief, separation of duties is enforced, releases are attributed, and every
decision lands in a hash-chained audit log that detects edits and deletions.

Synthetic runs only (tests/test_agency_operations.make_review_run); no model calls.
"""

import json

import pytest
from conftest import approve_synthetic, make_review_run, prepare_release

from pipeline import agency, delivery, quality, release_control, revisions

CHECKS = quality.field_review_checklist()


def _with_conflict(run):
    brief = revisions.load(run / "brief.json")
    ref = brief["objectives"][0]["evidence"][0]
    brief["conflicts"] = [
        {
            "field": "timeline",
            "status": "open",
            "positions": [{"statement": "June", "evidence": ref}, {"statement": "July", "evidence": ref}],
        }
    ]
    brief["open_questions"] = [{"field": "budget", "gap": "Unknown", "why_it_matters": "Planning",
                                "suggested_question_for_client": "What is the production budget?"}]
    revisions.write_json(run / "brief.json", brief)
    return brief


def _apply(run, tmp_path, candidate, actor="Synthetic editor"):
    path = tmp_path / "candidate.json"
    revisions.write_json(path, candidate)
    return agency.main(["apply", str(run), "--candidate", str(path), "--actor", actor, "--reason", "Edit"])


def _declare(tmp_path, data_class):
    """make_review_run's source lives in tmp_path, so that is the project folder."""
    (tmp_path / "data_declaration.json").write_text(json.dumps({"data_class": data_class}), encoding="utf-8")


# -- amendments ----------------------------------------------------------------------------


@pytest.mark.parametrize("mutate", [
    lambda b: b["conflicts"].clear(),
    lambda b: b["conflicts"][0].update(status="resolved_by_human", resolved_by="Someone", resolution="July"),
    lambda b: b["conflicts"][0]["positions"][1].update(statement="August"),
    lambda b: b["conflicts"].append({"field": "budget", "status": "resolved_by_human", "resolved_by": "X",
                                     "resolution": "Y", "positions": b["conflicts"][0]["positions"]}),
    lambda b: b["open_questions"].clear(),
    lambda b: b["open_questions"][0].update(suggested_question_for_client="Reworded?"),
], ids=["drop-conflict", "resolve-conflict", "edit-positions", "add-resolved", "drop-question", "reword-question"])
def test_apply_refuses_to_resolve_or_delete(tmp_path, capsys, mutate):
    run = make_review_run(tmp_path)
    brief = _with_conflict(run)
    candidate = json.loads(json.dumps(brief))
    mutate(candidate)
    assert _apply(run, tmp_path, candidate) == 2
    assert "Amendment refused" in capsys.readouterr().err
    assert revisions.load(run / "brief.json") == brief
    assert not (run / "amendments.json").exists()


def test_apply_still_accepts_content_edits_and_new_open_conflicts(tmp_path):
    run = make_review_run(tmp_path)
    brief = _with_conflict(run)
    candidate = json.loads(json.dumps(brief))
    candidate["objectives"][0]["content"] = "Revised synthetic campaign"
    candidate["conflicts"].append({**candidate["conflicts"][0], "field": "budget"})
    assert _apply(run, tmp_path, candidate) == 0
    events = [e["event"] for e in revisions.read_audit_log(run)]
    assert events == ["brief_amended"] and revisions.verify_audit_log(run) == []


def test_a_question_closed_by_human_triage_may_leave_the_brief(tmp_path):
    run = make_review_run(tmp_path)
    brief = _with_conflict(run)
    q = agency.clarifications.queue(brief)[0]
    assert agency.main(["answer", str(run), "--actor", "Synthetic lead", "--id", q["id"], "--status",
                        "not_worth_asking", "--text", "Budget is agreed elsewhere", "--owner", "Account",
                        "--priority", "nonblocking"]) == 0
    candidate = json.loads(json.dumps(brief))
    candidate["open_questions"] = []
    assert _apply(run, tmp_path, candidate) == 0


# -- coverage exclusions ---------------------------------------------------------------------


def _uncovered_fact(run):
    extract = revisions.load(run / "extracts" / "rfp.json")
    extract["budget"].append({"value": "Stray campaign fact", "anchor": "campaign", "location": "L1"})
    revisions.write_json(run / "extracts" / "rfp.json", extract)
    record = next(r for r in quality.coverage(revisions.load(run / "brief.json"), agency.extract_records(run))
                  if not r["destinations"])
    return record["id"]


def test_exclusion_counts_only_for_the_brief_it_was_made_against(tmp_path):
    run = make_review_run(tmp_path)
    fact = _uncovered_fact(run)
    def blocked():
        return [b for b in agency.audit(run, persist=False)["blockers"] if b.startswith(f"coverage.{fact}")]
    assert blocked()
    assert agency.main(["exclude", str(run), "--actor", "Synthetic lead", "--fact", fact,
                        "--reason", "Duplicate of the objective"]) == 0
    assert not blocked()
    candidate = revisions.load(run / "brief.json")
    candidate["key_messages"][0]["content"] = "Changed message"
    assert _apply(run, tmp_path, candidate) == 0
    assert blocked() and "earlier brief revision" in blocked()[0]


def test_a_hand_written_unbound_exclusion_counts_for_nothing(tmp_path):
    run = make_review_run(tmp_path)
    fact = _uncovered_fact(run)
    revisions.write_json(run / "coverage_decisions.json", {fact: {"actor": "Agent", "reason": "silence it"}})
    assert any(b.startswith(f"coverage.{fact}") for b in agency.audit(run, persist=False)["blockers"])


# -- separation of duties ----------------------------------------------------------------------


def _attest(run, actor):
    assert agency.main(["attest", str(run), "--actor", actor, "--greek-register", "4",
                        "--notes", "Synthetic only", "--checks", *CHECKS]) == 0


def test_the_brief_signer_cannot_be_the_language_attester(tmp_path):
    run = make_review_run(tmp_path)
    _attest(run, "Synthetic Lead")
    with pytest.raises(agency.SeparationOfDutiesError, match="different person"):
        agency.approve(run, "  synthetic   lead ", "Same person, different spacing")
    assert agency.main(["approve", str(run), "--actor", "Synthetic Lead", "--summary", "x"]) == 2
    assert not (run / "approval.json").exists()


@pytest.mark.parametrize("declaration, allowed", [(None, False), ("approved", False), ("synthetic", True)])
def test_solo_rehearsal_waiver_only_for_synthetic_projects(tmp_path, declaration, allowed):
    run = make_review_run(tmp_path)
    if declaration:
        _declare(tmp_path, declaration)
    _attest(run, "Solo operator")
    code = agency.main(["approve", str(run), "--actor", "Solo operator", "--summary", "Rehearsal",
                        "--solo-rehearsal"])
    assert (code == 0) is allowed
    if allowed:
        approval = revisions.load(run / "approval.json")
        assert approval["separation_of_duties"]["waived"] == "solo_rehearsal"
        logged = revisions.read_audit_log(run)[-1]
        assert logged["event"] == "brief_approved" and logged["details"]["separation_of_duties"]["waived"]


def test_creative_approver_must_differ_from_registrant_and_brief_signer(tmp_path):
    run = prepare_release(tmp_path)   # signer 'Lead A', registrant 'Synthetic operator'
    for same in ("Synthetic operator", "lead a"):
        with pytest.raises(agency.SeparationOfDutiesError):
            delivery.approve(run, same, "Reviewed", delivery.CHECKS)
    assert not (run / "creative_approval.json").exists()
    delivery.approve(run, "Synthetic creative lead", "Reviewed", delivery.CHECKS)


def test_creative_solo_rehearsal_is_recorded_and_rechecked_at_release(tmp_path):
    run = prepare_release(tmp_path)
    with pytest.raises(agency.SeparationOfDutiesError, match="synthetic"):
        delivery.approve(run, "Synthetic operator", "Solo", delivery.CHECKS, solo_rehearsal=True)
    _declare(tmp_path, "synthetic")
    approval = delivery.approve(run, "Synthetic operator", "Solo", delivery.CHECKS, solo_rehearsal=True)
    assert approval["separation_of_duties"]["waived"] == "solo_rehearsal"
    _declare(tmp_path, "approved")      # the project stops being synthetic: the waiver lapses
    with pytest.raises(agency.SeparationOfDutiesError):
        delivery.release(run, tmp_path / "out", "Synthetic releaser")


def test_a_hand_edited_creative_approval_cannot_smuggle_a_same_person_release(tmp_path):
    run = prepare_release(tmp_path)
    delivery.approve(run, "Synthetic creative lead", "Reviewed", delivery.CHECKS)
    record = revisions.load(run / "creative_approval.json")
    record["actor"] = "Synthetic operator"
    revisions.write_json(run / "creative_approval.json", record)
    with pytest.raises(agency.SeparationOfDutiesError):
        delivery.release(run, tmp_path / "out", "Synthetic releaser")


# -- attributed release ----------------------------------------------------------------------------


def test_release_requires_and_records_a_named_actor(tmp_path):
    run = prepare_release(tmp_path)
    delivery.approve(run, "Synthetic creative lead", "Reviewed", delivery.CHECKS)
    with pytest.raises(ValueError, match="releasing operator"):
        delivery.release(run, tmp_path / "out", "  ")
    with pytest.raises(SystemExit):
        delivery.main(["release", str(run), "--output", str(tmp_path / "out")])
    assert delivery.main(["release", str(run), "--output", str(tmp_path / "out"), "--actor", "Traffic lead"]) == 0
    assert revisions.load(tmp_path / "out" / "release.json")["released_by"] == "Traffic lead"
    assert revisions.load(run / "releases.json")[0]["released_by"] == "Traffic lead"
    assert release_control.verify(tmp_path / "out", run)["valid"]


# -- audit log -----------------------------------------------------------------------------------------


def _released(tmp_path):
    run = prepare_release(tmp_path)
    delivery.approve(run, "Synthetic creative lead", "Reviewed", delivery.CHECKS)
    delivery.release(run, tmp_path / "out", "Traffic lead")
    return run


def test_every_decision_is_chained_in_order(tmp_path):
    run = _released(tmp_path)
    log = revisions.read_audit_log(run)
    events = [e["event"] for e in log]
    assert events[-5:] == ["language_attested", "brief_approved", "creative_registered",
                           "creative_approved", "creative_released"]
    assert [e["seq"] for e in log] == list(range(1, len(log) + 1))
    assert log[0]["prev_sha256"] == revisions.GENESIS_SHA256
    assert revisions.verify_audit_log(run) == []
    assert release_control.main(["verify-log", str(run)]) == 0


@pytest.mark.parametrize("tamper, expected", [
    (lambda lines: lines.__setitem__(1, lines[1].replace("Lead A", "Lead B")), "previous-entry hash"),
    (lambda lines: lines.pop(1), "sequence"),
    (lambda lines: lines.insert(0, lines.pop(2)), "sequence"),
    (lambda lines: lines.pop(), "releases.json[0] has no matching"),
], ids=["edit", "delete-middle", "reorder", "truncate-tail"])
def test_verify_log_detects_edits_and_deletions(tmp_path, tamper, expected):
    run = _released(tmp_path)
    path = run / revisions.AUDIT_LOG
    lines = path.read_text(encoding="utf-8").splitlines()
    tamper(lines)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert any(expected in p for p in revisions.verify_audit_log(run))
    assert release_control.main(["verify-log", str(run)]) == 2


def test_an_approval_written_around_the_commands_is_not_vouched_for(tmp_path):
    run = make_review_run(tmp_path)
    approve_synthetic(run)
    record = revisions.load(run / "approval.json")
    record["actor"] = "Somebody else"
    revisions.write_json(run / "approval.json", record)
    assert any("approval.json is not vouched" in p for p in revisions.verify_audit_log(run))


def test_a_broken_log_blocks_the_next_release(tmp_path):
    run = _released(tmp_path)
    path = run / revisions.AUDIT_LOG
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Audit log"):
        delivery.release(run, tmp_path / "again", "Traffic lead")


def test_withdrawal_and_resolution_are_logged(tmp_path):
    run = make_review_run(tmp_path)
    _with_conflict(run)
    agency.resolve(run, 0, "Synthetic lead", "July; synthetic decision")
    assert revisions.read_audit_log(run)[-1]["event"] == "conflict_resolved"
    (tmp_path / "second").mkdir()
    run2 = _released(tmp_path / "second")
    release_control.withdraw(run2, "Synthetic lead", "Wrong campaign")
    assert revisions.read_audit_log(run2)[-1]["event"] == "approval_withdrawn"
    assert revisions.verify_audit_log(run2) == []
