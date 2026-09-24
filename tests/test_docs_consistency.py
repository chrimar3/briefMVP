"""Documentation consistency — the drift the round-1 judges found, made a regression test.

1. Shared headline figures come from one facts file, `docs/facts.json`. Each fact's `text` must
   appear verbatim in every file its `appears_in` lists, and every fact with a `derive` rule is
   re-derived from the committed evidence (`runs/r2-live`) with the same tools the documents cite,
   so a figure cannot drift from its run or between documents.
2. Every `X.md §N` section reference in the current documents (docs/*.md, docs/pilot/*.md,
   README.md, CLAUDE.md and the three front-door HTML pages) resolves to a file with a heading
   numbered N.
3. Every backticked repo path in docs/*.md, docs/pilot/*.md, README.md and CLAUDE.md resolves:
   a path with a directory must exist in the checkout; a bare file name must be a tracked file's
   name or a record name the pipeline writes (named in pipeline/*.py). Allowed exceptions are
   explicit: placeholders (`<ts>`, `*`, `_N_`), the names the runner creates only locally
   (`runs/latest`, `runs/r2-live/latest`, `runs/BLOCKED.md`), and paths whose line (or the two lines before it) says the
   run is local, gitignored or untracked.

Deterministic: reads files and git's index only; no model call, no network. docs/history/ holds
superseded notes and is not scanned.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "eval"))
import cost_report  # noqa: E402

FACTS = json.loads((REPO / "docs" / "facts.json").read_text(encoding="utf-8"))["facts"]
LIVE = REPO / "runs" / "r2-live"

CURRENT_DOCS = sorted((REPO / "docs").glob("*.md")) + sorted((REPO / "docs" / "pilot").glob("*.md")) + [
    REPO / "README.md", REPO / "CLAUDE.md"]
FRONT_DOORS = [REPO / "WALKTHROUGH.html", REPO / "START_HERE.html", REPO / "SHARE_ME.html"]

TOP_DIRS = (r"(?:\.claude|\.github|pipeline|eval|docs|runs|fixtures|tests|tools|config|skills|schema|templates|"
            r"scripts|reviews|demo|glossary)")
PATH_RE = re.compile(r"`(" + TOP_DIRS + r"/[^`\s]*)`")
BARE_RE = re.compile(r"`([A-Za-z0-9_.-]+\.(?:md|html|json|jsonl|py|sh|csv))`")
SECTION_RE = re.compile(r"((?:docs/)?(?:pilot/)?[A-Z][A-Z_]+\.md)\s?§\s?(\d+(?:\.\d+)?)")
LOCAL_MARK = re.compile(r"local store|gitignored|not committed|untracked|local run|operator's machine", re.I)
PLACEHOLDER = re.compile(r"[<>*{}$…]|\.\.\.|_N_|/N/")
CREATED_ONLY_LOCALLY = {
    "runs/latest": "symlink the runner creates beside each local run; gitignored",
    "runs/r2-live/latest": "the same symlink inside the round-2 run folder; gitignored",
    "runs/BLOCKED.md": "written only when a tier blocks (CLAUDE.md rule 3); none has",
}


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO))


# ---- 1. shared figures ----------------------------------------------------------------------------


@pytest.mark.parametrize("name,target", [(n, t) for n, f in sorted(FACTS.items()) for t in f["appears_in"]])
def test_shared_figure_appears_verbatim(name, target):
    path = REPO / target
    assert path.is_file(), f"{target} (listed for {name}) does not exist"
    text = html.unescape(path.read_text(encoding="utf-8"))
    text = re.sub(r"<[^>]+>", "", text) if target.endswith(".html") else text
    assert FACTS[name]["text"] in text, f"{target} does not say {FACTS[name]['text']!r} ({name})"


def _briefs() -> list:
    return cost_report.complete_briefs(cost_report.load_runs(LIVE))


def _derive(rule: str):
    if rule == "harness_full_passes":
        # Real run directories only: a local `latest` symlink (gitignored) must not count a run twice.
        reports = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(LIVE.glob("*/harness_report.json"))
                   if not p.parent.is_symlink()]
        full = sum(1 for r in reports if len(r.get("checks") or []) == 17
                   and all(c["status"] == "pass" for c in r["checks"]))
        return {"full_17": full, "graded": len(reports)}
    if rule.startswith("brief_mean:"):
        project = rule.split(":", 1)[1]
        sel = [b for b in _briefs() if project in ("*", b["project"])]
        return round(sum(b["stage1_total"] for b in sel) / len(sel))
    if rule == "sonnet_share":
        briefs = _briefs()
        sonnet = sum(b["tokens"]["stage1"].get("sonnet", {}).get("total", 0) for b in briefs)
        return round(sonnet / sum(b["stage1_total"] for b in briefs), 3)
    if rule.startswith("run_tokens:"):
        return cost_report.token_ledger(cost_report.load_runs(LIVE / rule.split(":", 1)[1]))["total"]["total"]
    if rule == "sealed_extras":
        import sealed_extras
        result = sealed_extras.grade(LIVE / "lv-r1")
        return {"passed": result["required_passed"], "required": result["required"]}
    if rule == "verifier":
        total = cost_report.verifier_effectiveness(cost_report.load_runs(LIVE))["total"]
        return {k: total[k] for k in ("checks", "issues", "forwarded", "dropped", "applied", "rejected")}
    raise AssertionError(f"unknown derive rule {rule}")


@pytest.mark.parametrize("name", sorted(n for n, f in FACTS.items() if f.get("derive")))
def test_fact_value_rederives_from_the_committed_evidence(name):
    assert _derive(FACTS[name]["derive"]) == FACTS[name]["value"]


def test_monthly_estimate_is_the_pooled_mean_times_prd_a2():
    fact = FACTS["monthly_estimate"]["value"]
    assert fact["briefs_per_month"] == 15  # PRD §4 assumption A2
    assert round(fact["briefs_per_month"] * FACTS["pooled_mean_tokens"]["value"] / 1e6, 1) == fact["tokens_millions"]


def test_the_symlinked_latest_run_is_not_counted():
    runs = [run_id for run_id, _m in cost_report.load_runs(LIVE)]
    assert "latest" not in runs and len(runs) == len(set(runs))


# ---- 2. section references ------------------------------------------------------------------------


def _section_refs():
    for doc in CURRENT_DOCS + FRONT_DOORS:
        if not doc.is_file():
            continue
        text = html.unescape(doc.read_text(encoding="utf-8"))
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in SECTION_RE.finditer(line):
                yield _rel(doc), lineno, m.group(1), m.group(2)


def _resolve_doc(name: str):
    if "/" in name:
        candidates = [REPO / name]
    else:
        candidates = [REPO / name, REPO / "docs" / name, REPO / "docs" / "pilot" / name, REPO / "skills" / name]
    return next((c for c in candidates if c.is_file()), None)


def test_every_section_reference_resolves():
    broken = []
    for doc, lineno, name, section in _section_refs():
        target = _resolve_doc(name)
        if target is None:
            broken.append(f"{doc}:{lineno}: {name} §{section} — no such file")
            continue
        heading = re.compile(rf"^#{{1,4}}\s*(?:§\s?)?{re.escape(section)}[.\s)—:-]", re.MULTILINE)
        if not heading.search(target.read_text(encoding="utf-8")):
            broken.append(f"{doc}:{lineno}: {name} §{section} — no heading numbered {section} in {_rel(target)}")
    assert not broken, "\n".join(broken)


# ---- 3. repo paths --------------------------------------------------------------------------------


def _tracked_names() -> set:
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=REPO,
                         capture_output=True, text=True, check=False).stdout
    return {Path(p).name for p in out.splitlines() if p}


def _pipeline_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted((REPO / "pipeline").glob("*.py")))


def test_every_repo_path_in_the_documents_resolves():
    tracked, pipeline_src = _tracked_names(), _pipeline_text()
    broken = []
    for doc in CURRENT_DOCS:
        lines = doc.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            context = " ".join(lines[max(0, i - 2): i + 1])
            for m in PATH_RE.finditer(line):
                path = re.sub(r"(::\w+|:[A-Za-z_]\w*|:\d+(?:[–-]\d+)?)$", "", m.group(1).rstrip(".,;:)").split("#")[0])
                if PLACEHOLDER.search(path) or any(path.rstrip("/") == p or path.startswith(p + "/")
                                                   for p in CREATED_ONLY_LOCALLY):
                    continue
                if (REPO / path).exists() or (REPO / path).is_symlink() or LOCAL_MARK.search(context):
                    continue
                broken.append(f"{_rel(doc)}:{i + 1}: {path}")
            for m in BARE_RE.finditer(line):
                name = m.group(1)
                if name in tracked or (REPO / name).exists() or f"{name}" in pipeline_src or PLACEHOLDER.search(name):
                    continue
                broken.append(f"{_rel(doc)}:{i + 1}: {name} (bare name: not a tracked file or a pipeline record)")
    assert not broken, "\n".join(broken)
