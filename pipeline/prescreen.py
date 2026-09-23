"""Advisory personal-data pre-screen of a project folder. Deterministic, local, no model calls.

    python3 -m pipeline.prescreen PROJECT_DIR [--output report.json]

`scan(project_dir)` reads the folder's text sources and counts, per source and per category,
the lines that carry a contact identifier (e-mail address, phone number, IBAN-like string) or a
term from the Greek + English special-category list in `config/prescreen_terms.json` (GDPR
Art. 9, Art. 10 criminal-offence data, data about children). It reports *where to look*
(source file, category, line numbers, counts), never *what it found*: matched values are not
recorded anywhere, so the report itself carries no personal data.

It is advisory by design. It never blocks, never changes a declaration, and a clean result
proves nothing: the human screening step in `docs/pilot/DATA_PROTECTION.md` §10 remains the
control, and the data-protection lead decides what a hit means. The runner records the result
in the run manifest as `prescreen` (round 2, phase B); the account lead reads it before
declaring a project `approved`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from pipeline import gates

TERMS_PATH = gates.CONFIG_DIR / "prescreen_terms.json"

#: Suffixes read as text sources: the input contract's `*.md`, plus the raw `.txt` an intake
#: folder may hold before headers are added. `HARNESS_ONLY_FILES` (the answer key) is skipped.
TEXT_SUFFIXES = (".md", ".txt")

#: Line numbers kept per source and category; counts are never truncated.
MAX_LINES_LISTED = 20

EMAIL_RE = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}(?!\w)")
#: International form (+30 …, 0030 …) or a Greek national 10-digit number (landline 2x…,
#: mobile 69…), with optional spaces, dots or dashes between digits. Candidates are then
#: checked by `_phone_hits`: one separator style only, and never an ISO date, so a date plus
#: time such as "2026-07-11 09:40" or a timestamp such as [00:03:41] is not a phone number.
PHONE_RE = re.compile(
    r"(?<![\w+:])(?:(?:\+|00)\d{1,3}[ .-]?(?:\(?\d{1,4}\)?[ .-]?)?(?:\d[ .-]?){5,10}\d"
    r"|(?:2\d|69)(?:[ .-]?\d){8})(?![\w:])"
)
_ISO_DATE_START = re.compile(r"\d{4}-\d{2}-\d{2}")
#: Two letters, two check digits, then 11-30 alphanumerics, optionally in groups of four
#: separated by single spaces (the printed form). Length is checked after removing spaces.
IBAN_RE = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}(?![A-Za-z0-9])")

PATTERN_CATEGORIES = ("email_address", "phone_number", "iban_like")


def normalise(text: str) -> str:
    """Accent-, case- and final-sigma-insensitive form used for term matching."""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.casefold().replace("ς", "σ")


def _term_pattern(term: str, whole_word: bool) -> str:
    body = r"\s+".join(re.escape(part) for part in normalise(term).split())
    return r"(?<!\w)" + body + (r"(?!\w)" if whole_word else "")


def load_terms(path: Path = TERMS_PATH) -> dict:
    """Compile the special-category term list: {category: compiled regex}."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    compiled = {}
    for category, spec in payload["categories"].items():
        parts = [_term_pattern(t, False) for t in spec.get("prefix", [])]
        parts += [_term_pattern(t, True) for t in spec.get("word", [])]
        if not parts:
            raise ValueError(f"{path}: category {category!r} has no terms")
        compiled[category] = re.compile("|".join(parts))
    return compiled


def _iban_spans(line: str) -> list:
    spans = []
    for match in IBAN_RE.finditer(line):
        compact = match.group(0).replace(" ", "")
        if 15 <= len(compact) <= 34 and any(ch.isdigit() for ch in compact[4:]):
            spans.append(match.span())
    return spans


def _phone_hits(line: str, skip: Sequence[tuple] = ()) -> int:
    hits = 0
    for match in PHONE_RE.finditer(line):
        if any(start < match.end() and match.start() < end for start, end in skip):
            continue  # digits inside an IBAN-like string are counted once, as the IBAN
        text = match.group(0)
        separators = set(re.findall(r"[ .-]", text.lstrip("+")))
        if _ISO_DATE_START.match(text) or len(separators) > 1:
            continue
        hits += 1
    return hits


def scan_text(text: str, terms: Optional[dict] = None) -> dict:
    """Per-category {"count": n, "lines": [...]} for one text. Values are never returned."""
    terms = load_terms() if terms is None else terms
    found: dict = {}

    def note(category: str, lineno: int, count: int) -> None:
        if count:
            entry = found.setdefault(category, {"count": 0, "lines": []})
            entry["count"] += count
            if len(entry["lines"]) < MAX_LINES_LISTED:
                entry["lines"].append(lineno)

    for lineno, line in enumerate(text.splitlines(), 1):
        note("email_address", lineno, len(EMAIL_RE.findall(line)))
        ibans = _iban_spans(line)
        note("phone_number", lineno, _phone_hits(line, ibans))
        note("iban_like", lineno, len(ibans))
        folded = normalise(line)
        for category, pattern in terms.items():
            note(category, lineno, len(pattern.findall(folded)))
    return found


def _text_files(project_dir: Path) -> list:
    return sorted(p for p in project_dir.iterdir()
                  if p.is_file() and not p.is_symlink() and p.suffix.lower() in TEXT_SUFFIXES
                  and p.name not in gates.HARNESS_ONLY_FILES)


def _declares_a_source(path: Path) -> bool:
    """True when the file opens with a valid source header (the input contract's declaration)."""
    try:
        gates.parse_source_header(path.read_text(encoding="utf-8"), path)
    except (gates.InputContractError, OSError, UnicodeDecodeError):
        return False
    return True


def _sources(project_dir: Path) -> tuple:
    """(files to screen, mode). A folder that declares sources is screened on those only —
    never a README, a note or any other non-source file beside them. A raw intake folder
    (no file declares a source yet) is screened on every text file, since each is a candidate."""
    candidates = _text_files(project_dir)
    declared = [p for p in candidates if p.suffix.lower() == ".md" and _declares_a_source(p)]
    if declared:
        return declared, "declared_sources"
    return candidates, "raw_folder"


def scan(project_dir: Path, terms_path: Path = TERMS_PATH, files: Optional[list] = None) -> dict:
    """Advisory pre-screen of the sources in `project_dir`. Never raises on content.

    `files` names exactly the files to screen (the runner passes its declared sources);
    without it the folder's declared sources are screened, or every text file of a raw intake
    folder (`_sources`). Harness-only files are never read.

    Returns a JSON-serialisable report: per source, per category, a count and the first line
    numbers; totals per category; and the fixed advisory boundary. A missing folder is an
    error (there is nothing to screen); an unreadable file is listed under `unreadable`.
    """
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        raise FileNotFoundError(f"{project_dir}: not a folder")
    terms = load_terms(terms_path)
    if files is not None:
        paths, mode = [Path(p) for p in files if Path(p).name not in gates.HARNESS_ONLY_FILES], "given_files"
    else:
        paths, mode = _sources(project_dir)
    sources: list = []
    unreadable: list = []
    totals: dict = {}
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            unreadable.append({"file": path.name, "reason": type(exc).__name__})
            continue
        found = scan_text(text, terms)
        for category, entry in found.items():
            totals[category] = totals.get(category, 0) + entry["count"]
        sources.append({"file": path.name, "findings": found})
    try:
        terms_ref = str(Path(terms_path).resolve().relative_to(gates.REPO_ROOT))
    except ValueError:
        terms_ref = str(terms_path)
    return {
        "advisory": True,
        "blocking": False,
        "mode": mode,
        "scanned_files": len(sources),
        "sources_with_findings": sum(1 for s in sources if s["findings"]),
        "totals": dict(sorted(totals.items())),
        "sources": sources,
        "unreadable": unreadable,
        "categories": list(PATTERN_CATEGORIES) + list(terms),
        "terms_file": terms_ref,
        "boundary": ("Advisory pre-screen: counts and line numbers only, matched values are never recorded. "
                     "A hit asks a person to look; a clean result proves nothing. The human screening step "
                     "(docs/pilot/DATA_PROTECTION.md section 10) remains the control."),
    }


def main(argv: Optional[list] = None) -> int:
    """CLI: print (and optionally write) the advisory report. Exit 0 whatever it finds."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", type=Path, help="Project folder (the input contract's source folder)")
    parser.add_argument("--output", type=Path, help="Also write the JSON report here")
    args = parser.parse_args(argv)
    try:
        report = scan(args.project)
    except (OSError, ValueError, KeyError) as exc:
        print(f"[prescreen] {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
