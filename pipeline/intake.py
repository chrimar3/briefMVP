"""Intake: turn a folder of raw client documents into a contract-compliant Input folder.

The runner's input contract (`gates.parse_source_header`) requires every source to declare
`source_id · source_type · source_date` in its first lines — raw documents from a client
never arrive that way. This tool stamps the header deterministically, so an arbitrary pile
of transcript/RFP/email files becomes a runnable project folder in one command:

    python pipeline/intake.py raw_docs/ --out fixtures/acme_01 --client acme --tier S1

Ethos matches the rest of the pipeline: no model calls, no guessing. Where a document's
type is evident from strong signals (transcript timestamps, email headers), it is inferred
and announced; where it is not, intake refuses and asks for an explicit `--type` — a file
that will not say what it is does not get read into a brief. The sensitivity tier is NEVER
inferred (PRD DR-11): it is a required argument, validated against the permitted tiers.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from pipeline import gates
else:
    from . import gates


class IntakeError(Exception):
    pass


RAW_SUFFIXES = (".md", ".txt")

#: Timestamps like [00:12:41] or [12:41] — three or more make a transcript.
_TIMESTAMP_RE = re.compile(r"\[\d{1,2}:\d{2}(?::\d{2})?\]")
#: Email message headers: a From: line with a To: or Date: line nearby.
_EMAIL_FROM_RE = re.compile(r"^\**From\**\s*:", re.MULTILINE | re.IGNORECASE)
_EMAIL_TO_DATE_RE = re.compile(r"^\**(To|Date)\**\s*:", re.MULTILINE | re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")

_FILENAME_HINTS = (
    ("rfp", "rfp"),
    ("transcript", "transcript"),
    ("kickoff", "transcript"),
    ("call", "transcript"),
    ("email", "email_thread"),
    ("mail", "email_thread"),
    ("thread", "email_thread"),
    ("guideline", "background"),
    ("research", "background"),
    ("background", "background"),
    ("deck", "background"),
    ("brief", "background"),
)


def slugify(stem: str) -> str:
    """ASCII-fold a filename stem into a stable source_id."""
    folded = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", folded.lower()).strip("_")
    if not slug:
        raise IntakeError(f"cannot derive a source_id from filename {stem!r} — rename the file to Latin characters")
    return slug


def infer_source_type(path: Path, text: str) -> str | None:
    """Deterministic type inference. Returns None when no strong signal exists —
    the caller refuses and asks for --type rather than defaulting."""
    head = text[:6000]
    if len(_TIMESTAMP_RE.findall(head)) >= 3:
        return "transcript"
    if _EMAIL_FROM_RE.search(head) and _EMAIL_TO_DATE_RE.search(head):
        return "email_thread"
    name = path.stem.lower()
    for hint, stype in _FILENAME_HINTS:
        if hint in name:
            return stype
    if re.search(r"\bRFP\b", head):
        return "rfp"
    return None


def infer_source_date(path: Path, text: str) -> tuple[str, str]:
    """First ISO date in the document head wins; else the file's mtime, announced as such."""
    match = _ISO_DATE_RE.search("\n".join(text.splitlines()[:40]))
    if match:
        return match.group(1), "found in document"
    mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    return mtime, "file mtime — verify, or pass --date"


@dataclass
class IntakeItem:
    raw_path: Path
    source_id: str
    source_type: str
    source_date: str
    date_provenance: str
    already_compliant: bool


def plan_intake(
    raw_files: list[Path],
    type_overrides: dict[str, str],
    date_overrides: dict[str, str],
) -> list[IntakeItem]:
    items: list[IntakeItem] = []
    unknown: list[str] = []
    for path in raw_files:
        text = path.read_text(encoding="utf-8")
        try:
            header = gates.parse_source_header(text, path)
            items.append(IntakeItem(path, header["source_id"], header["source_type"],
                                    header["source_date"], "declared in file", True))
            continue
        except gates.InputContractError:
            pass

        stype = type_overrides.get(path.name) or type_overrides.get(path.stem) or infer_source_type(path, text)
        if stype is None:
            unknown.append(path.name)
            continue
        if stype not in gates.VALID_SOURCE_TYPES:
            raise IntakeError(f"{path.name}: type {stype!r} is not one of {list(gates.VALID_SOURCE_TYPES)}")
        date_override = date_overrides.get(path.name) or date_overrides.get(path.stem)
        if date_override:
            sdate, provenance = date_override, "explicit --date"
        else:
            sdate, provenance = infer_source_date(path, text)
        items.append(IntakeItem(path, slugify(path.stem), stype, sdate, provenance, False))

    if unknown:
        raise IntakeError(
            "cannot infer source_type for: " + ", ".join(unknown)
            + f". Pass --type <filename>={'|'.join(gates.VALID_SOURCE_TYPES)} for each."
        )
    ids = [i.source_id for i in items]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise IntakeError(f"duplicate source_id(s) after slugging: {dupes} — rename the clashing files")
    return items


STARTER_TERMS = [
    {"term": "key visual", "rule": "keep_latin", "note": "Standard EN creative term."},
    {"term": "launch", "rule": "keep_latin", "note": "Used untranslated in agency register."},
    {"term": "KPI", "rule": "keep_latin", "note": "Acronym stays Latin."},
    {"term": "media spend", "rule": "keep_latin", "note": "Budget term; distinct from production budget — never merge the two."},
    {"term": "brand awareness", "rule": "keep_latin", "note": "Standard EN marketing term in agency Greek."},
]


def scaffold_glossary(glossary_path: Path, client_id: str, tier: str) -> bool:
    """Create a starter client config if none exists. Returns True when written.

    The tier is validated against the same permitted list the pipeline enforces, so an
    out-of-scope client fails at intake, before anyone burns a model call.
    """
    gates.enforce_sensitivity_tier(tier)
    if glossary_path.exists():
        existing = json.loads(glossary_path.read_text(encoding="utf-8"))
        if existing.get("sensitivity_tier") != tier:
            raise IntakeError(
                f"{glossary_path} already exists with tier {existing.get('sensitivity_tier')!r}; "
                f"refusing to change it to {tier!r} from the intake CLI — edit the client config deliberately."
            )
        return False
    glossary_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "client_id": client_id,
        "sensitivity_tier": tier,
        "_scaffold_note": "Starter glossary written by pipeline/intake.py — review terms with the account lead before the run.",
        "terms": STARTER_TERMS,
    }
    glossary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def write_project(items: list[IntakeItem], out_dir: Path, force: bool) -> list[Path]:
    if out_dir.exists() and any(out_dir.iterdir()) and not force:
        raise IntakeError(f"{out_dir} exists and is not empty — pass --force to overwrite its files")
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for item in items:
        text = item.raw_path.read_text(encoding="utf-8")
        dest = out_dir / f"{item.source_id}.md"
        if item.already_compliant:
            dest.write_text(text, encoding="utf-8")
        else:
            title = item.raw_path.stem.replace("_", " ").replace("-", " ").strip()
            header = (
                f"# {title}\n"
                f"source_id: {item.source_id} · source_type: {item.source_type} · source_date: {item.source_date}\n\n"
            )
            dest.write_text(header + text, encoding="utf-8")
        written.append(dest)
    return written


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("raw", help="Folder of raw documents (or a single file)")
    parser.add_argument("--out", required=True, help="Project folder to create, e.g. fixtures/acme_01")
    parser.add_argument("--client", required=True, help="client_id for the glossary scaffold")
    parser.add_argument("--tier", required=True, help="Onboarding sensitivity tier (never inferred — PRD DR-11)")
    parser.add_argument("--type", action="append", default=[], metavar="FILE=TYPE",
                        help="Explicit source_type for a file, e.g. --type notes.txt=background")
    parser.add_argument("--date", action="append", default=[], metavar="FILE=YYYY-MM-DD",
                        help="Explicit source_date for a file")
    parser.add_argument("--glossary-dir", default=None,
                        help="Where to scaffold the client config (default: the project folder itself, "
                             "keeping glossary/ single-client so existing default commands stay valid)")
    parser.add_argument("--force", action="store_true", help="Overwrite files in a non-empty --out")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan, write nothing")
    args = parser.parse_args(argv)

    raw = Path(args.raw)
    raw_files = sorted(p for p in ([raw] if raw.is_file() else raw.glob("*"))
                       if p.suffix.lower() in RAW_SUFFIXES and p.name not in gates.HARNESS_ONLY_FILES)
    if not raw_files:
        print(f"[intake] no {'/'.join(RAW_SUFFIXES)} files in {raw}", file=sys.stderr)
        return 2

    def parse_kv(pairs, flag):
        out = {}
        for pair in pairs:
            if "=" not in pair:
                raise IntakeError(f"{flag} expects FILE=VALUE, got {pair!r}")
            k, v = pair.split("=", 1)
            out[k] = v
        return out

    try:
        items = plan_intake(raw_files, parse_kv(args.type, "--type"), parse_kv(args.date, "--date"))
        glossary_dir = Path(args.glossary_dir) if args.glossary_dir else Path(args.out)
        glossary_path = glossary_dir / f"client_{args.client}.json"
        print(f"Intake plan for {len(items)} source(s) → {args.out}")
        for item in items:
            note = "header already compliant" if item.already_compliant else f"date: {item.date_provenance}"
            print(f"  {item.source_id:32s} {item.source_type:12s} {item.source_date}  ({note})")
        if args.dry_run:
            print("[dry-run] nothing written")
            return 0
        written = write_project(items, Path(args.out), args.force)
        scaffolded = scaffold_glossary(glossary_path, args.client, args.tier)
        sources = gates.discover_sources(Path(args.out))  # prove the contract holds
        verdict = gates.readiness_gate(sources)
    except (IntakeError, gates.InputContractError, gates.ScopeError) as exc:
        print(f"[intake] {exc}", file=sys.stderr)
        return 2

    print(f"\n{len(written)} file(s) written; glossary "
          + (f"scaffolded at {glossary_path} — REVIEW TERMS before the run" if scaffolded
             else f"already present at {glossary_path} (untouched)"))
    print(f"readiness: {verdict.message}")
    print(f"\nRun:\n  python pipeline/runner.py --project {args.out} --glossary {glossary_path}")
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
