"""Persistent human triage. Similarity is a review hint, never a decision."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Union

from pipeline.revisions import digest, file_hash, load, timestamp, write_json
from pipeline.quality import ref_key


def normalize(text):
    return re.sub(r"\s+", " ", text.casefold()).strip()


def queue(brief, decisions=None):
    groups = {}
    for i, question in enumerate(brief.get("open_questions") or []):
        key = (question.get("field", ""), normalize(question.get("suggested_question_for_client", "")))
        item = groups.setdefault(key, {"id": digest(key)[:20], "field": key[0], "question": question.get("suggested_question_for_client", ""),
                                      "member_indexes": [], "evidence": [], "review_hints": []})
        item["member_indexes"].append(i)
        for ref in question.get("linked_evidence") or []:
            if ref_key(ref) not in {ref_key(r) for r in item["evidence"]}:
                item["evidence"].append(ref)
    result = list(groups.values())
    for item in result:
        for other in result:
            if item is not other and item["field"] == other["field"] and SequenceMatcher(None, normalize(item["question"]), normalize(other["question"])).ratio() > .75:
                item["review_hints"].append(f"Possible overlap with {other['id']}; human review required")
        for i, conflict in enumerate(brief.get("conflicts") or []):
            anchors = {ref_key(p.get("evidence") or {}) for p in conflict.get("positions") or []}
            if anchors.intersection(ref_key(r) for r in item["evidence"]):
                item["review_hints"].append(f"Shares evidence with conflict {i}; check whether it asks a distinct question")
        item["existing_brief_context"] = [entry.get("content", "") for entry in brief.get(item["field"], [])]
        item["evidence_hash"] = digest(sorted(ref_key(r) for r in item["evidence"]))
        decision = (decisions or {}).get(item["id"])
        item["decision"] = decision if decision and decision.get("evidence_hash") == item["evidence_hash"] else None
    return result


def record(run_dir, items, question_id, status, actor, text, evidence, owner, priority):
    if status not in ("answered", "duplicate", "not_worth_asking", "open"):
        raise ValueError("Unknown question status")
    if not all(str(v).strip() for v in (actor, text, owner)) or priority not in ("blocking", "nonblocking"):
        raise ValueError("Actor, owner, rationale/answer and blocking/nonblocking priority are required")
    if status == "answered" and not evidence.strip():
        raise ValueError("An answer needs a source reference; ingest new evidence before updating the brief")
    item = next((q for q in items if q["id"] == question_id), None)
    if item is None:
        raise ValueError("Question no longer exists; regenerate the queue")
    path = Path(run_dir) / "clarifications.json"
    decisions = load(path, {})
    previous = decisions.get(question_id)
    decisions[question_id] = {"status": status, "actor": actor, "text": text, "evidence": evidence,
                              "owner": owner, "priority": priority, "evidence_hash": item["evidence_hash"],
                              "recorded_at": timestamp(), "history": ((previous or {}).get("history", []) +
                              [{k: v for k, v in previous.items() if k != "history"}] if previous else [])}
    write_json(path, decisions)


def carry_decisions(parent: Union[str, Path], child: Union[str, Path], actor: str) -> dict:
    """Explicitly carry matching triage only. Never transfer approval or resolve conflicts.

    Moved here from `pipeline/revisions.py` (it is triage policy, not a revision utility);
    `revisions.carry_decisions` still resolves to this function.
    """
    parent, child = Path(parent).resolve(), Path(child).resolve()
    if parent == child or not actor.strip():
        raise ValueError('Distinct parent/child revisions and a named operator required')
    old, new = load(parent / 'brief.json'), load(child / 'brief.json')
    identity = lambda b: tuple(b.get('meta', {}).get(k) for k in ('client_id', 'project_id'))
    if not all(identity(old)) or identity(old) != identity(new):
        raise ValueError('Revision identity must match client and project')
    source_hashes = lambda path: {k: v.get('sha256') for k, v in load(path/'input_snapshot.json', {}).items() if k.startswith('source:')}
    old_sources, new_sources = source_hashes(parent), source_hashes(child)
    unchanged_sources = bool(old_sources) and old_sources == new_sources
    prior = {q['id']: q for q in queue(old, load(parent / 'clarifications.json', {}))}
    current = queue(new)
    decisions = load(child / 'clarifications.json', {})
    carried, pending = [], []
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
    history = load(child / 'revision_lineage.json', [])
    history.append(result)
    write_json(child / 'revision_lineage.json', history)
    return result
