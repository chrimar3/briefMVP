"""Data declaration: the first clause of the input contract (owner decision 4, 2026-09-22).

Every project folder carries `data_declaration.json` at its root. It says what kind of
material the folder holds, so that the fixtures-only rule is enforced by code as well as by
policy text:

    {"data_class": "synthetic"}
    {"data_class": "approved", "approval_ref": "DP-2026-014",
     "approved_by": "Agency data-protection lead", "approved_on": "2026-10-01"}

`synthetic` is invented material (every fixture). `approved` is anything else, and it must
carry the reference, approver and date of the agency's recorded data-policy approval.

An `approved` declaration may also record the data-protection preconditions the pilot pack
sets before real material is run (`docs/pilot/DATA_PROTECTION.md` §10, `GO_LIVE_DECISIONS.md`
D-03 and D-09): `screened_by` and `screened_on` (the special-category screening step),
`processor_ref` (the filed processor terms for the account in use) and `dpia_ref` (the DPIA or
screening decision). They are required (`REQUIRE_PRECONDITIONS`, owner decision 4, round 2
phase B): an approved declaration without all four is refused (exit 6), and `pipeline/intake.py`
writes them from `--screened-by`, `--screened-on`, `--processor-ref` and `--dpia-ref`. With the
switch off, absent ones would only be listed in the run manifest as `preconditions_missing`. The
declaration is a control, not a grant: writing an `approved` declaration does not approve
anything; it records WHO approved it and WHERE that decision lives, so the run manifest can
show it. Whether real client data may be processed at all remains the agency's data-policy
decision (`docs/pilot/DATA_PROTECTION.md`, `docs/pilot/GO_LIVE_DECISIONS.md`).

Deterministic, no model calls. A missing file is a refusal, never an inferred class: the
runner and intake refuse before any source is read into a work order.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from pipeline import gates

DECLARATION_FILE = "data_declaration.json"
SYNTHETIC = "synthetic"
APPROVED = "approved"
DATA_CLASSES = (SYNTHETIC, APPROVED)
APPROVAL_FIELDS = ("approval_ref", "approved_by", "approved_on")
#: Data-protection preconditions an `approved` declaration records (validated when present).
PRECONDITION_FIELDS = ("screened_by", "screened_on", "processor_ref", "dpia_ref")
#: Date-valued fields: ISO YYYY-MM-DD, never in the future.
DATE_FIELDS = ("approved_on", "screened_on")
#: True since intake writes the precondition fields (round 2, phase B): an approved declaration
#: without them is a refusal (exit 6). A tightening; synthetic declarations are unaffected.
REQUIRE_PRECONDITIONS = True

_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

_HOW_TO_DECLARE = (
    'Synthetic fixtures declare {"data_class": "synthetic"}; any other material needs '
    '{"data_class": "approved", "approval_ref": "...", "approved_by": "...", "approved_on": "YYYY-MM-DD", '
    '"screened_by": "...", "screened_on": "YYYY-MM-DD", "processor_ref": "...", "dpia_ref": "..."} '
    "recorded from the agency's data-policy approval (docs/OPERATING_DECISIONS.md, 2026-09-22 decision 4; "
    "docs/pilot/DATA_PROTECTION.md §10)."
)


class DataDeclarationError(gates.InputContractError):
    """The project folder has no valid data declaration, or its data class forbids the requested paths."""


@dataclass(frozen=True)
class DataDeclaration:
    """A validated declaration. `path` is the file it was read from; `sha256` hashes the exact
    bytes that were validated (None only for a declaration built in memory, not read)."""

    data_class: str
    path: Path
    approval_ref: Optional[str] = None
    approved_by: Optional[str] = None
    approved_on: Optional[str] = None
    screened_by: Optional[str] = None
    screened_on: Optional[str] = None
    processor_ref: Optional[str] = None
    dpia_ref: Optional[str] = None
    sha256: Optional[str] = None

    @property
    def is_synthetic(self) -> bool:
        """True for invented material; the only class allowed inside the repository."""
        return self.data_class == SYNTHETIC

    @property
    def missing_preconditions(self) -> list:
        """Precondition fields an approved declaration does not record (always [] for synthetic)."""
        if self.is_synthetic:
            return []
        return [name for name in PRECONDITION_FIELDS if not getattr(self, name)]

    def as_record(self) -> dict:
        """What the run manifest records (never the material itself)."""
        record: dict = {"data_class": self.data_class, "file": str(self.path), "sha256": self.sha256}
        if not self.is_synthetic:
            record.update(approval_ref=self.approval_ref, approved_by=self.approved_by,
                          approved_on=self.approved_on)
            record.update({name: getattr(self, name) for name in PRECONDITION_FIELDS if getattr(self, name)})
            record["preconditions_missing"] = self.missing_preconditions
        return record


def _date_problem(where: str, key: str, value: str, today: Optional[date]) -> Optional[str]:
    try:
        if not _ISO_DATE_RE.fullmatch(value):
            raise ValueError
        when = date.fromisoformat(value)
    except ValueError:
        return f"{where}: {key} must be an ISO date YYYY-MM-DD, got {value!r}"
    if when > (today or date.today()):
        return f"{where}: {key} {value} is in the future"
    return None


def validate_payload(payload: object, where: str = DECLARATION_FILE, today: Optional[date] = None) -> list:
    """Every problem with a parsed declaration, as sentences. Empty list = valid."""
    if not isinstance(payload, dict):
        return [f"{where}: must be a JSON object"]
    problems = []
    data_class = payload.get("data_class")
    if data_class not in DATA_CLASSES:
        problems.append(f"{where}: data_class must be one of {list(DATA_CLASSES)}, got {data_class!r}")
    allowed = {"data_class", *APPROVAL_FIELDS, *PRECONDITION_FIELDS}
    unknown = sorted(k for k in payload if k not in allowed and not str(k).startswith("_"))
    if unknown:
        problems.append(f"{where}: unknown key(s) {unknown} (notes go in keys starting with '_')")
    if data_class == SYNTHETIC:
        present = [k for k in (*APPROVAL_FIELDS, *PRECONDITION_FIELDS) if k in payload]
        if present:
            problems.append(
                f"{where}: a synthetic declaration carries no approval fields ({present}); "
                "use data_class 'approved' for approved non-synthetic material"
            )
    elif data_class == APPROVED:
        required = APPROVAL_FIELDS + (PRECONDITION_FIELDS if REQUIRE_PRECONDITIONS else ())
        for key in required:
            value = payload.get(key)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{where}: data_class 'approved' requires a non-empty {key}")
        for key in PRECONDITION_FIELDS:
            if key in payload and key not in required:
                value = payload[key]
                if not isinstance(value, str) or not value.strip():
                    problems.append(f"{where}: {key}, when present, must be non-empty text")
        for key in DATE_FIELDS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                problem = _date_problem(where, key, value, today)
                if problem:
                    problems.append(problem)
    return problems


def load_declaration(project_dir: Path, today: Optional[date] = None) -> DataDeclaration:
    """Read and validate `<project_dir>/data_declaration.json`, or raise DataDeclarationError."""
    project_dir = Path(project_dir)
    path = project_dir / DECLARATION_FILE
    if path.is_symlink():
        raise DataDeclarationError(f"{path}: the data declaration must be a regular file, not a symlink")
    if not path.is_file():
        raise DataDeclarationError(
            f"{project_dir}: no {DECLARATION_FILE} — every project folder must declare its data class "
            f"before anything is read. {_HOW_TO_DECLARE}"
        )
    try:
        data = path.read_bytes()
        payload = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataDeclarationError(f"{path}: not readable JSON ({exc}). {_HOW_TO_DECLARE}") from exc
    problems = validate_payload(payload, str(path), today)
    if problems:
        raise DataDeclarationError("; ".join(problems) + f". {_HOW_TO_DECLARE}")
    return DataDeclaration(
        data_class=payload["data_class"], path=path.resolve(), sha256=hashlib.sha256(data).hexdigest(),
        **{name: payload.get(name) for name in (*APPROVAL_FIELDS, *PRECONDITION_FIELDS)},
    )


def is_synthetic(project_dir: Path) -> bool:
    """True only for a valid synthetic declaration. Missing or invalid → False (never inferred)."""
    try:
        return load_declaration(project_dir).is_synthetic
    except DataDeclarationError:
        return False


def _inside(path: Path, root: Path) -> bool:
    path, root = Path(path).resolve(), Path(root).resolve()
    return path == root or root in path.parents


def check_locations(declaration: DataDeclaration, *, project_dir: Path, out_dir: Optional[Path] = None,
                    glossary: Optional[Path] = None, repo_root: Path = gates.REPO_ROOT) -> list:
    """Non-synthetic material never lives in, or writes into, this repository.

    `fixtures/`, `glossary/` and the committed `runs/` exceptions are tracked and pushed
    (docs/pilot/OPERATING_TERMS.md §e), so an approved project, its client config and its run
    output must all sit outside the repository. `glossary=None` means the runner's default
    (the single file in the repository's `glossary/`), which is therefore refused as well.
    Synthetic declarations are unrestricted.
    """
    if declaration.is_synthetic:
        return []
    problems = []
    named = [("project folder", project_dir), ("output directory", out_dir)]
    for label, path in named:
        if path is not None and _inside(path, repo_root):
            problems.append(f"{label} {Path(path).resolve()} is inside the repository")
    if glossary is None:
        problems.append("no explicit --glossary: the default client config lives inside the repository")
    elif _inside(glossary, repo_root):
        problems.append(f"client config {Path(glossary).resolve()} is inside the repository")
    return [
        f"data_class 'approved' material must stay outside the repository ({p}); "
        "pass --project, --out and --glossary paths under the agency's pilot location"
        for p in problems
    ]


def require_for_run(project_dir: Path, *, out_dir: Optional[Path] = None, glossary: Optional[Path] = None,
                    repo_root: Path = gates.REPO_ROOT, today: Optional[date] = None) -> DataDeclaration:
    """The runner's refusal: a valid declaration, and paths its data class permits."""
    declaration = load_declaration(project_dir, today)
    problems = check_locations(declaration, project_dir=project_dir, out_dir=out_dir,
                               glossary=glossary, repo_root=repo_root)
    if problems:
        raise DataDeclarationError("; ".join(problems))
    return declaration


def build_declaration(data_class: str, approval_ref: Optional[str] = None, approved_by: Optional[str] = None,
                      approved_on: Optional[str] = None, today: Optional[date] = None, *,
                      screened_by: Optional[str] = None, screened_on: Optional[str] = None,
                      processor_ref: Optional[str] = None, dpia_ref: Optional[str] = None) -> dict:
    """The payload intake writes. Validated before it is returned; nothing is inferred."""
    payload: dict = {"data_class": data_class}
    preconditions = {"screened_by": screened_by, "screened_on": screened_on,
                     "processor_ref": processor_ref, "dpia_ref": dpia_ref}
    if data_class == APPROVED:
        payload.update(approval_ref=approval_ref, approved_by=approved_by, approved_on=approved_on)
        payload.update({k: v for k, v in preconditions.items() if v is not None})
    elif any(v is not None for v in (approval_ref, approved_by, approved_on, *preconditions.values())):
        raise DataDeclarationError("approval fields are only valid with --data-class approved")
    problems = validate_payload(payload, "declaration", today)
    if problems:
        raise DataDeclarationError("; ".join(problems))
    return payload
