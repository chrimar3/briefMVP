"""Explicitly approved reference material, imported as evidence, never hidden memory."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import re

KINDS = {"positioning", "tone", "approved_claim", "prohibited_claim", "terminology", "brand_requirement"}


def validate(pack, client_id, today=None):
    problems = []
    if not isinstance(pack, dict):
        return ["Client pack must be an object"]
    if not re.fullmatch(r"[A-Za-z0-9._-]+", str(pack.get("version", ""))):
        problems.append("version must be a single safe identifier")
    for key in ("client_id", "approved_by"):
        if not isinstance(pack.get(key), str) or "\n" in pack[key] or "\r" in pack[key]:
            problems.append(f"{key} must be single-line text")
    if pack.get("client_id") != client_id:
        problems.append("client_id does not match the project")
    for key in ("version", "approved_by", "review_due"):
        if not str(pack.get(key, "")).strip():
            problems.append(f"Missing {key}")
    try:
        if date.fromisoformat(pack.get("review_due", "")) < (today or date.today()):
            problems.append("Client pack is expired; obtain human review")
    except ValueError:
        problems.append("review_due must be an ISO date")
    if not pack.get("items"):
        problems.append("Client pack must contain sourced items")
    for i, item in enumerate(pack.get("items") or []):
        if item.get("kind") not in KINDS:
            problems.append(f"item {i}: unknown kind")
        for key in ("text", "source"):
            if not str(item.get(key, "")).strip():
                problems.append(f"item {i}: missing {key}")
    return problems


def materialize(pack, client_id, output):
    problems = validate(pack, client_id)
    if problems:
        raise ValueError("; ".join(problems))
    output = Path(output)
    if output.exists():
        raise ValueError("Reference output already exists; use a new version filename")
    # Matches the intake/source header contract; conflicting campaign claims remain visible.
    text = (f"source_id: client_reference_{pack['version']}\nsource_type: background\nsource_date: {date.today().isoformat()}\n\n"
            f"# Approved reference for {client_id}\n\nVersion: {pack['version']}\nApproved by: {pack['approved_by']}\n"
            f"Review due: {pack['review_due']}\n\nThese references do not override campaign sources; report disagreements.\n\n")
    for item in pack["items"]:
        text += f"- {item['kind']}: {item['text']} (source: {item['source']})\n"
    output.write_text(text, encoding="utf-8")
    return output
