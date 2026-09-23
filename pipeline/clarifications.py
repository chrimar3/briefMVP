"""Persistent human triage. Similarity is a review hint, never a decision."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

from pipeline.quality import ref_key
from pipeline.records import PathLike
from pipeline.revisions import digest, file_hash, load, timestamp, write_json

#: One triage group of open questions (see `queue`), and the stored decisions keyed by group id.
QueueItem = dict[str, Any]
Decisions = dict[str, dict[str, Any]]

STATUSES = ("answered", "duplicate", "not_worth_asking", "open")
PRIORITIES = ("blocking", "nonblocking")


def normalize(text: str) -> str:
    """Case-folded text with runs of whitespace collapsed: the grouping key for duplicate questions."""
    return re.sub(r"\s+", " ", text.casefold()).strip()


def queue(brief: dict[str, Any], decisions: Optional[Decisions] = None) -> list[QueueItem]:
    """Group the brief's open questions by field and wording, with review hints and any still-valid decision.

    A stored decision applies only while the group's evidence hash is unchanged; overlap and
    shared-evidence hints are prompts for a human, never decisions.
    """
    groups: dict[tuple[str, str], QueueItem] = {}
    for i, question in enumerate(brief.get("open_questions") or []):
        key = (question.get("field", ""), normalize(question.get("suggested_question_for_client", "")))
        item = groups.setdefault(key, {"id": digest(key)[:20], "field": key[0],
                                       "question": question.get("suggested_question_for_client", ""),
                                       "member_indexes": [], "evidence": [], "review_hints": []})
        item["member_indexes"].append(i)
        for ref in question.get("linked_evidence") or []:
            if ref_key(ref) not in {ref_key(r) for r in item["evidence"]}:
                item["evidence"].append(ref)
    result = list(groups.values())
    for item in result:
        for other in result:
            similar = SequenceMatcher(None, normalize(item["question"]), normalize(other["question"])).ratio() > .75
            if item is not other and item["field"] == other["field"] and similar:
                item["review_hints"].append(f"Possible overlap with {other['id']}; human review required")
        for i, conflict in enumerate(brief.get("conflicts") or []):
            anchors = {ref_key(p.get("evidence") or {}) for p in conflict.get("positions") or []}
            if anchors.intersection(ref_key(r) for r in item["evidence"]):
                item["review_hints"].append(
                    f"Shares evidence with conflict {i}; check whether it asks a distinct question")
        item["existing_brief_context"] = [entry.get("content", "") for entry in brief.get(item["field"], [])]
        item["evidence_hash"] = digest(sorted(ref_key(r) for r in item["evidence"]))
        decision = (decisions or {}).get(item["id"])
        item["decision"] = decision if decision and decision.get("evidence_hash") == item["evidence_hash"] else None
    return result


def record(run_dir: PathLike, items: list[QueueItem], question_id: str, status: str, actor: str, text: str,
           evidence: str, owner: str, priority: str) -> None:
    """Store one attributed triage decision in clarifications.json, keeping the previous one in its history."""
    if status not in STATUSES:
        raise ValueError("Unknown question status")
    if not all(str(v).strip() for v in (actor, text, owner)) or priority not in PRIORITIES:
        raise ValueError("Actor, owner, rationale/answer and blocking/nonblocking priority are required")
    if status == "answered" and not evidence.strip():
        raise ValueError("An answer needs a source reference; ingest new evidence before updating the brief")
    item = next((q for q in items if q["id"] == question_id), None)
    if item is None:
        raise ValueError("Question no longer exists; regenerate the queue")
    path = Path(run_dir) / "clarifications.json"
    decisions: Decisions = load(path, {})
    previous = decisions.get(question_id)
    history = (previous.get("history", []) + [{k: v for k, v in previous.items() if k != "history"}]
               if previous else [])
    decisions[question_id] = {"status": status, "actor": actor, "text": text, "evidence": evidence,
                              "owner": owner, "priority": priority, "evidence_hash": item["evidence_hash"],
                              "recorded_at": timestamp(), "history": history}
    write_json(path, decisions)


def _identity(brief: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(brief.get('meta', {}).get(k) for k in ('client_id', 'project_id'))


def _source_hashes(run: Path) -> dict[str, Any]:
    return {k: v.get('sha256') for k, v in load(run / 'input_snapshot.json', {}).items() if k.startswith('source:')}


def carry_decisions(parent: PathLike, child: PathLike, actor: str) -> dict[str, Any]:
    """Explicitly carry matching triage only. Never transfer approval or resolve conflicts.

    Moved here from `pipeline/revisions.py` (it is triage policy, not a revision utility);
    `revisions.carry_decisions` still resolves to this function.
    """
    parent, child = Path(parent).resolve(), Path(child).resolve()
    if parent == child or not actor.strip():
        raise ValueError('Distinct parent/child revisions and a named operator required')
    old, new = load(parent / 'brief.json'), load(child / 'brief.json')
    if not all(_identity(old)) or _identity(old) != _identity(new):
        raise ValueError('Revision identity must match client and project')
    old_sources, new_sources = _source_hashes(parent), _source_hashes(child)
    unchanged_sources = bool(old_sources) and old_sources == new_sources
    prior = {q['id']: q for q in queue(old, load(parent / 'clarifications.json', {}))}
    current = queue(new)
    decisions: Decisions = load(child / 'clarifications.json', {})
    carried: list[str] = []
    pending: list[str] = []
    for q in current:
        previous = prior.get(q['id'])
        old_context = [old['open_questions'][i] for i in previous['member_indexes']] if previous else []
        new_context = [new['open_questions'][i] for i in q['member_indexes']]
        if (q['id'] not in decisions and previous and previous['decision'] and unchanged_sources
                and old_context == new_context and previous['evidence_hash'] == q['evidence_hash']):
            decisions[q['id']] = {**previous['decision'], 'carried_from': str(parent), 'carried_by': actor,
                                  'carried_at': timestamp()}
            carried.append(q['id'])
        elif q['id'] not in decisions:
            pending.append(q['id'])
    write_json(child / 'clarifications.json', decisions)
    result = {'parent': str(parent), 'parent_brief_sha256': file_hash(parent/'brief.json'), 'actor': actor,
              'carried': carried, 'needs_review': pending, 'at': timestamp()}
    history: list[dict[str, Any]] = load(child / 'revision_lineage.json', [])
    history.append(result)
    write_json(child / 'revision_lineage.json', history)
    return result
