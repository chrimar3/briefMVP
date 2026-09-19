"""Persistent human triage. Similarity is a review hint, never a decision."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from pipeline.revisions import digest, load, timestamp, write_json
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
