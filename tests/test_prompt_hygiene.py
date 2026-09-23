"""Runtime prompts: no graded-fixture text, and an untrusted-content rule in every one (r1-W2).

The four skill files and the agent definitions are what a runtime model actually reads. If they
quote a graded fixture — a seeded garble, a trap phrase, the budget line itself — a green harness
run partly measures recall of a worked example, not the rule it was meant to teach
(tools/project_review/rounds/r0: a2_prompt_engineer, a3_llmops_engineer). The fixture sources are
read here as plain text; the answer keys are never opened (only eval/harness.py reads those).

Scope: every runtime instruction file — the four skills, and the agent bodies of all seven
runtime subagents (render and creative-shadow joined at the round-1 integration).
"""

import json
import re

import pytest

RUNTIME_PROMPTS = (
    "skills/SOURCES.md",
    "skills/TRANSCRIPTS.md",
    "skills/SYNTHESIS.md",
    ".claude/agents/extract.md",
    ".claude/agents/verify-extract.md",
    ".claude/agents/classify.md",
    ".claude/agents/fidelity-check.md",
    ".claude/agents/synthesize.md",
    "skills/TRANSLATION.md",
    ".claude/agents/render.md",
    ".claude/agents/creative-shadow.md",
)

#: Seeded or distinctive fixture strings too short for the n-gram check: the garbled terms, the
#: speculation phrase, the budget figure word, client/brand/person names and the trap timestamp.
SEEDED_STRINGS = (
    "μπραντ αγουέρνες", "κι βίζουαλ", "hold me to", "ογδόντα", "TikTok-first", "14:32",
    "Meltemi", "Voreas", "Dimitris", "Nikos", "Eleni", "Northlight",
)

#: A run of this many words shared with a fixture source is a quotation, not a coincidence.
#: (At 4 words generic phrases such as "in latin script in" start to collide.)
NGRAM = 5


def _words(text):
    return re.findall(r"\w+", text.casefold())


def _ngrams(text, n=NGRAM):
    words = _words(text)
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def quarantined_paths(repo_root):
    """Sealed blind-fixture paths (fixtures/SEALED_KEYS.json): no test reads their content before
    the fixture's first graded run is committed (round-2 rule 8) — not even to guard a prompt."""
    sealed = json.loads((repo_root / "fixtures" / "SEALED_KEYS.json").read_text(encoding="utf-8"))
    return tuple(repo_root / q for q in sealed.get("quarantined_paths") or [])


def fixture_sources(repo_root):
    """Every fixture source document a prompt must not quote, sealed fixtures excluded."""
    quarantined = quarantined_paths(repo_root)
    return [p for p in sorted((repo_root / "fixtures").glob("*/*.md"))
            if not any(p == q or q in p.parents for q in quarantined)]


@pytest.fixture(scope="module")
def fixture_ngrams(repo_root):
    grams = set()
    for path in fixture_sources(repo_root):
        grams |= _ngrams(path.read_text(encoding="utf-8"))
    assert grams, "no fixture sources found"
    return grams


def test_the_detector_catches_a_quoted_fixture_line(fixture_ngrams, repo_root):
    """Guard the guard: the old SOURCES.md §9 example quoted the graded budget line."""
    line = next(l for l in (repo_root / "fixtures" / "northlight_01" / "transcript_kickoff.md")
                .read_text(encoding="utf-8").splitlines() if l.startswith("[00:14:32]"))
    assert _ngrams(line) & fixture_ngrams


@pytest.mark.parametrize("relpath", RUNTIME_PROMPTS)
def test_runtime_prompt_quotes_no_fixture_text(relpath, repo_root, fixture_ngrams):
    shared = _ngrams((repo_root / relpath).read_text(encoding="utf-8")) & fixture_ngrams
    assert not shared, f"{relpath} quotes fixture text: {sorted(' '.join(g) for g in shared)[:5]}"


@pytest.mark.parametrize("relpath", RUNTIME_PROMPTS)
def test_runtime_prompt_carries_no_seeded_fixture_string(relpath, repo_root):
    text = (repo_root / relpath).read_text(encoding="utf-8")
    found = [s for s in SEEDED_STRINGS if s.casefold() in text.casefold()]
    assert not found, f"{relpath} carries graded-fixture strings {found}"


@pytest.mark.parametrize("relpath", RUNTIME_PROMPTS)
def test_runtime_prompt_has_an_untrusted_content_rule(relpath, repo_root):
    """Every stage reads client-authored text; every stage is told it is data, not orders."""
    text = " ".join((repo_root / relpath).read_text(encoding="utf-8").casefold().split())
    assert re.search(r"never (an )?instructions?", text), f"{relpath}: no untrusted-content rule"
    assert "never followed" in text, f"{relpath}: embedded instructions must be 'never followed'"


def test_skills_share_one_rule_label(repo_root):
    """Rule U is one rule with one name across the skills, so reviewers can grep for it."""
    for skill in ("skills/SOURCES.md", "skills/TRANSCRIPTS.md", "skills/SYNTHESIS.md", "skills/TRANSLATION.md",
                  ".claude/agents/render.md", ".claude/agents/creative-shadow.md"):
        assert "U — untrusted content" in (repo_root / skill).read_text(encoding="utf-8"), skill


def test_verifier_is_told_annotations_are_not_evidence_and_evidence_is_verbatim(repo_root):
    text = (repo_root / ".claude" / "agents" / "verify-extract.md").read_text(encoding="utf-8")
    assert "[FIDELITY: ...]` annotations are not source text" in text
    assert "Evidence is verbatim" in text
    assert "Self-check" in text
