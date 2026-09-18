"""Voreas regression cases: pilot gates the frozen harness cannot see.

runs/voreas_prep_report.md (session 2026-07-26, plus its same-day addendum) records
content-integrity failures on the second fixture that eval/harness.py either scored
as a pass or could not score at all. The 16/17 run (runs/voreas-prep-03) is
harness-green and still not account-lead-ready (addendum, finding 1). The harness is
frozen (CLAUDE.md rule 2), so these cases live here instead: one test per documented
failure class, each operating on the stored artifacts under runs/voreas-prep-02/
(roll 1, full pipeline, 15/17) and runs/voreas-prep-03/ (synthesis and render
re-roll on the same extracts, 16/17). No model is called and nothing is regenerated.

Marking rule. A case the stored artifact fails is marked xfail(strict=True) with the
report section it encodes, so the suite stays green while the defect is on record.
When the artifact is regenerated without the defect, strict xfail turns the XPASS
into a failure, which is the signal to drop the mark. A case the artifact already
satisfies passes outright and says so in its docstring.

Inputs, all read-only: runs/voreas-prep-0{2,3}/brief.json, brief_en.md, brief_el.md,
extracts/*.json, harness_report.json; fixtures/voreas_02/ sources and
client_voreas.json. Never read here: fixtures/voreas_02/answer_key.json (the frozen
harness is the only code allowed to read it, CLAUDE.md rule 2).

Availability. runs/voreas-prep-02 and runs/voreas-prep-03 are committed alongside
runs/tier3 as evidence (.gitignore exceptions), so these cases run on any clone.
Every test still skips with an explicit message if its run directory is absent.

Not encoded, on purpose: report finding 5 (haiku formatting hazards, already refused
by runner gates), addendum finding 5 (conflict-blind readiness, a policy call) and
addendum finding 6 (keep_latin scope over source-faithful paraphrase, judged
ambiguous in the report).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from pipeline import gates, stages

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "fixtures" / "voreas_02"
RUNS = ("voreas-prep-02", "voreas-prep-03")
REPORT = "runs/voreas_prep_report.md"

# Documented tokens (report Findings 1 and 2, Addendum 2 and 3). Each is checked against
# the stored artifact or source before an assertion uses it, so a changed fixture fails
# as a precondition and never as a silent pass. xfail-marked cases carry
# raises=AssertionError, and preconditions use pytest.fail, so a precondition failure
# reports as a real failure rather than the expected one.
GARBLED_OBJECTIVE = "μπραντ αγουέρνες"
GARBLED_OBJECTIVE_PROPOSAL = "brand awareness"
GARBLED_OBJECTIVE_LOCATION = "[00:02:18]"
CLEAN_CLAUSE_BESIDE_IT = "δοκιμή"
NO_INFLUENCERS_ANCHOR = "Η μάρκα επικοινωνεί **χωρίς influencers**"
THREE_INFLUENCERS_ANCHOR = "θέλουμε τρεις micro-influencers για το πρώτο κύμα"
SUPERSEDED_DATE_TOKENS = ("31 Ιανουαρίου", "31/1")
GUIDELINES_VERSION_TOKEN = "2.0"

NUMBERED_RE = re.compile(r"^\s*\d{1,3}[.)]\s")
SECTION_RE = re.compile(r"^##\s+(\d)\.")
TAG_RE = re.compile(r"\[([^\]\s]+)[^\]]*\]")


# --------------------------------------------------------------------------------------
# Artifact access
# --------------------------------------------------------------------------------------


def _run_dir(run: str) -> Path:
    path = REPO / "runs" / run
    if not (path / "brief.json").is_file():
        pytest.skip(
            f"{path.relative_to(REPO)} is not present: runs/* is gitignored except "
            f"runs/tier3, so the Voreas evidence lives only where it was produced"
        )
    return path


def _brief(run: str) -> dict:
    return json.loads((_run_dir(run) / "brief.json").read_text(encoding="utf-8"))


def _extracts(run: str) -> dict:
    return {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((_run_dir(run) / "extracts").glob("*.json"))
    }


def _render(run: str, lang: str) -> str:
    return (_run_dir(run) / f"brief_{lang}.md").read_text(encoding="utf-8")


def _harness_report(run: str) -> dict:
    return json.loads((_run_dir(run) / "harness_report.json").read_text(encoding="utf-8"))


def _source(name: str) -> str:
    return (FIXTURE / name).read_text(encoding="utf-8")


def _keep_latin_terms() -> list:
    config = json.loads((FIXTURE / "client_voreas.json").read_text(encoding="utf-8"))
    return [t["term"] for t in config["terms"] if t.get("rule") == "keep_latin"]


def _source_ids(brief: dict) -> set:
    return {s["source_id"] for s in brief["meta"]["sources"]}


def _known_tags(line: str, known: set) -> list:
    return [m.group(0) for m in TAG_RE.finditer(line) if m.group(1) in known]


def _strip_known_tags(line: str, known: set) -> str:
    return TAG_RE.sub(lambda m: " " if m.group(1) in known else m.group(0), line)


def _field_sections(render: str) -> dict:
    """Numbered claim lines of sections 1 to 7, keyed by brief field.

    The template (templates/northlight_client_brief.md) numbers the sections in
    gates.BRIEF_FIELDS order and renders one entry as one line, so line i of section n
    is brief[BRIEF_FIELDS[n-1]][i].
    """
    out = {field: [] for field in gates.BRIEF_FIELDS}
    current = None
    for raw in render.splitlines():
        line = raw.strip()
        if line.startswith("##"):
            match = SECTION_RE.match(line)
            current = gates.BRIEF_FIELDS[int(match.group(1)) - 1] if match else None
            continue
        if current and NUMBERED_RE.match(line):
            out[current].append(line)
    return out


def _warning_regions(render: str) -> list:
    """(heading, numbered lines) for every warning section, in template order:
    open questions first, then unresolved conflicts."""
    regions, current = [], None
    for raw in render.splitlines():
        line = raw.strip()
        if line.startswith("##"):
            current = [] if "⚠" in line else None
            if current is not None:
                regions.append((line, current))
            continue
        if current is not None and NUMBERED_RE.match(line):
            current.append(line)
    return regions


def _digit_runs(text: str) -> set:
    """Digit sequences of two or more digits, thousands grouping joined ("140.000" is
    "140000", "30–45" is {"30", "45"}). Same semantics as the render gate's fingerprint
    in pipeline/stages.py, reimplemented here so this file depends on no private helper."""
    runs = set()
    for match in re.findall(r"\d(?:[\d.,]*\d)?", text or ""):
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", match):
            runs.add(re.sub(r"[.,]", "", match))
        else:
            runs.update(part for part in re.split(r"[.,]", match) if len(part) >= 2)
    return runs


def _extract_items(extract: dict):
    """Every cited item an extract holds: the seven fields plus both sides of each
    internal conflict. Extract open questions and notes are model prose, not evidence."""
    for field in gates.BRIEF_FIELDS:
        for item in extract.get(field) or []:
            yield item
    for conflict in extract.get("internal_conflicts") or []:
        for side in ("value_a", "value_b"):
            if conflict.get(side):
                yield conflict[side]


def _brief_strings(brief: dict) -> list:
    """(path, text) for every model-authored string the brief carries."""
    out = []
    for field in gates.BRIEF_FIELDS:
        for idx, entry in enumerate(brief.get(field) or []):
            out.append((f"{field}[{idx}].content", entry.get("content") or ""))
    for idx, conflict in enumerate(brief.get("conflicts") or []):
        for p_idx, position in enumerate(conflict.get("positions") or []):
            out.append((f"conflicts[{idx}].positions[{p_idx}].statement",
                        position.get("statement") or ""))
        out.append((f"conflicts[{idx}].resolution", conflict.get("resolution") or ""))
    for idx, question in enumerate(brief.get("open_questions") or []):
        for key in ("gap", "why_it_matters", "suggested_question_for_client"):
            out.append((f"open_questions[{idx}].{key}", question.get(key) or ""))
    return out


def _open_conflicts(brief: dict) -> list:
    return [c for c in brief.get("conflicts") or [] if c.get("status") == "open"]


def _xfail(run: str, reason: str):
    return pytest.param(
        run, id=run,
        marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason),
    )


def _passes(run: str):
    return pytest.param(run, id=run)


# --------------------------------------------------------------------------------------
# 1. Garble-avoidance content loss (report Findings 1; harness T3.3 evidence)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("run", [
    _xfail("voreas-prep-02", "report Findings 1: the kickoff extract holds no objectives "
           "item for the garbled clause (note only), so the brand-awareness objective "
           "never reaches the brief (harness T3.3, runs/voreas-prep-02/harness_report.json)"),
    _xfail("voreas-prep-03", "report Findings 1: sticky, 0/2 rolls carried it (harness "
           "T3.3, runs/voreas-prep-03/harness_report.json); the kickoff extract is "
           "byte-identical to prep-02's and holds the garble only as a note, so a "
           "synthesis re-roll could not have restored it"),
])
def test_garble_flagged_objective_survives_synthesis(run):
    """Report Findings 1. Kickoff line [00:02:18] states two objectives in one sentence:
    the garbled `μπραντ αγουέρνες` (brand awareness) and the clean `δοκιμή` (trial).
    The extract records the garble only in extraction_notes with its glossary proposal
    (harness T1.4 accepts that); its objectives list holds no item for the garbled
    clause, although SOURCES.md rule G asks for the as-is item plus the note. With no
    extract item, SYNTHESIS.md rule 3 forbids synthesis from restoring it, so the
    client's primary objective is absent from the brief. This case guards the outcome;
    the fix begins in extraction, and the report's attribution to a SYNTHESIS.md
    coverage gap is contradicted by runs/<run>/extracts/transcript_kickoff.json.

    Reads: fixtures/voreas_02/transcript_kickoff.md, runs/<run>/extracts/transcript_kickoff.json,
    runs/<run>/brief.json.
    """
    source_line = next(
        line for line in _source("transcript_kickoff.md").splitlines()
        if line.startswith(GARBLED_OBJECTIVE_LOCATION)
    )
    if not (GARBLED_OBJECTIVE in source_line and CLEAN_CLAUSE_BESIDE_IT in source_line):
        pytest.fail("precondition: the source line carries both the garbled and the clean clause")

    extract = _extracts(run)["transcript_kickoff"]
    flagged = [
        note for note in extract.get("extraction_notes") or []
        if GARBLED_OBJECTIVE in note and GARBLED_OBJECTIVE_PROPOSAL in note
        and GARBLED_OBJECTIVE_LOCATION in note
    ]
    if not flagged:
        pytest.fail("precondition: the extract flags the garble with its glossary proposal")

    brief = _brief(run)
    carriers = []
    for idx, entry in enumerate(brief["objectives"]):
        texts = [entry.get("content") or ""] + [
            (ref.get("anchor") or "") for ref in entry.get("evidence") or []
        ]
        if any(GARBLED_OBJECTIVE in t or GARBLED_OBJECTIVE_PROPOSAL in t.lower() for t in texts):
            carriers.append(f"objectives[{idx}]")
    for idx, conflict in enumerate(brief["conflicts"]):
        if conflict.get("field") != "objectives":
            continue
        for p_idx, position in enumerate(conflict.get("positions") or []):
            texts = [position.get("statement") or "",
                     (position.get("evidence") or {}).get("anchor") or ""]
            if any(GARBLED_OBJECTIVE in t or GARBLED_OBJECTIVE_PROPOSAL in t.lower() for t in texts):
                carriers.append(f"conflicts[{idx}].positions[{p_idx}]")

    assert carriers, (
        f"{run}: the garble-flagged objective at {GARBLED_OBJECTIVE_LOCATION} reaches no "
        f"objectives entry and no objectives conflict; objectives carry only "
        f"{[e['content'][:50] for e in brief['objectives']]}"
    )


# --------------------------------------------------------------------------------------
# 2. Open questions that duplicate an open conflict (report Addendum 4)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("run", [
    _xfail("voreas-prep-02", "report Addendum 4: questions re-ask what conflict objects "
           "already record (6 of 17 under the anchor-overlap rule)"),
    _xfail("voreas-prep-03", "report Addendum 4: 4 of 16 questions duplicate conflict "
           "objects, one re-asks the launch date the client declared final in writing"),
])
def test_open_questions_do_not_duplicate_open_conflicts(run):
    """Report Addendum 4. Conflicts are resolved by the account lead (PRD DR-10); a
    question in the same field whose linked evidence is a position of an open conflict
    asks the client to settle what the brief already routes to the human. The report's
    candidate gate is field-level ("a question whose field matches an open conflict is
    a duplicate"); this test tightens it to field plus a shared (source_id, anchor) so a
    legitimate question in a conflicted field is not flagged for the field alone.

    Reads: runs/<run>/brief.json.
    """
    brief = _brief(run)
    positions = {
        (conflict["field"], p["evidence"]["source_id"], p["evidence"]["anchor"])
        for conflict in _open_conflicts(brief) for p in conflict["positions"]
    }
    if not positions:
        pytest.fail("precondition: the brief carries open conflicts with anchored positions")

    duplicates = []
    for idx, question in enumerate(brief["open_questions"]):
        hits = [
            (ref["source_id"], ref["anchor"][:40])
            for ref in question.get("linked_evidence") or []
            if (question["field"], ref["source_id"], ref["anchor"]) in positions
        ]
        if hits:
            duplicates.append(f"open_questions[{idx}] ({question['field']}) -> {hits}")

    assert not duplicates, (
        f"{run}: {len(duplicates)} of {len(brief['open_questions'])} open questions "
        f"restate an open conflict's position:\n" + "\n".join(duplicates)
    )


# --------------------------------------------------------------------------------------
# 3a. Rendered open questions drop their linked evidence (report Addendum 4)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("run", [
    _xfail("voreas-prep-02", "report Addendum 4: most questions render without their "
           "linked_evidence citations (0 of 17 tagged in either render)"),
    _xfail("voreas-prep-03", "report Addendum 4: most questions render without their "
           "linked_evidence citations (0 of 16 tagged in either render)"),
])
def test_rendered_open_questions_carry_their_linked_evidence(run):
    """Report Addendum 4, last clause. The brief links evidence to most open questions;
    the renders number every question (template contract, checked by the runner) but
    print none of those citations, so the reader cannot see where a gap came from.
    Harness T2.4 and the runner's check_render police sections 1 to 7 only; the template
    itself asks no citation of a question, which is the spec gap this case records.

    Reads: runs/<run>/brief.json, runs/<run>/brief_en.md, runs/<run>/brief_el.md.
    """
    brief = _brief(run)
    known = _source_ids(brief)
    questions = brief["open_questions"]
    linked = [i for i, q in enumerate(questions) if q.get("linked_evidence")]
    if not linked:
        pytest.fail("precondition: some open questions carry linked_evidence")

    untagged = []
    for lang in ("en", "el"):
        heading, items = _warning_regions(_render(run, lang))[0]
        if len(items) != len(questions):
            pytest.fail(
                f"{lang}: precondition, the first warning region ({heading}) numbers one "
                f"item per open question"
            )
        for i in linked:
            if not _known_tags(items[i], known):
                untagged.append(f"{lang} question {i + 1}")

    assert not untagged, (
        f"{run}: {len(untagged)} rendered question lines carry linked evidence in the "
        f"brief but no citation tag: {untagged}"
    )


# --------------------------------------------------------------------------------------
# 3b. A field asserts one side of an open conflict (report Addendum 1)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("run", [
    _xfail("voreas-prep-02", "same rule, instance not in the report: audiences carries "
           "the Greece position while the Cyprus hedge lives only in conflicts[1] (a "
           "within-source hedge that roll 1 promoted to a conflict, see the two-source test)"),
    _xfail("voreas-prep-03", "report Addendum 1: timeline holds one entry, mid-March "
           "2027, while the written Feb 14 date exists only inside the conflict object "
           "and a question; budget and mandatories fail the same rule"),
])
def test_no_field_asserts_one_side_of_an_open_conflict(run):
    """Report Addendum 1. SYNTHESIS.md rule 4: a field under an open cross-source
    conflict never reads as settled; its entries carry every position or leave the
    assertion to the conflict object. The report's candidate gate: a field with an open
    conflict must not carry one position as its sole entry. Matching is anchor-exact,
    an entry counts as asserting a position only when it cites that position's anchor.
    The renders mirror the entries one line each, so the same lines assert the same
    side to the reader; the section line counts are checked to pin that mirroring.

    Reads: runs/<run>/brief.json, runs/<run>/brief_en.md, runs/<run>/brief_el.md.
    """
    brief = _brief(run)
    sections = {lang: _field_sections(_render(run, lang)) for lang in ("en", "el")}
    for lang, by_field in sections.items():
        for field in gates.BRIEF_FIELDS:
            if len(by_field[field]) != len(brief[field]):
                pytest.fail(f"{lang}: precondition, section for {field} renders one line per entry")

    one_sided = []
    for idx, conflict in enumerate(_open_conflicts(brief)):
        field = conflict["field"]
        entry_anchors = {
            (ref.get("anchor") or "").strip()
            for entry in brief[field] for ref in entry.get("evidence") or []
        }
        anchored = [(p["evidence"].get("anchor") or "").strip() for p in conflict["positions"]]
        present = [a for a in anchored if a in entry_anchors]
        missing = [a for a in anchored if a not in entry_anchors]
        if present and missing:
            one_sided.append(
                f"{field}: {len(brief[field])} entr{'y' if len(brief[field]) == 1 else 'ies'} "
                f"assert {present[0][:40]!r}; missing {[a[:40] for a in missing]} "
                f"(conflicts[{idx}]); rendered EN lines: "
                f"{[l[:60] for l in sections['en'][field]]}"
            )

    assert not one_sided, f"{run}: field(s) present one side of an open conflict:\n" + "\n".join(one_sided)


@pytest.mark.parametrize("run, field", [
    pytest.param("voreas-prep-02", "audiences", id="voreas-prep-02"),
    pytest.param("voreas-prep-03", "timeline", id="voreas-prep-03"),
])
def test_runner_synthesis_gate_now_refuses_the_stored_one_sided_brief(run, field, tmp_path):
    """Companion to the previous case, passes outright. The report's candidate gate
    (Addendum 1: "runner-side check_synthesis, not the frozen harness") now exists in
    pipeline/stages.py as the SYNTHESIS.md rule 4 conflict-consistency check. Replaying
    the stored brief through it (readiness stripped, the gate runs before injection)
    reports the documented instance: timeline for voreas-prep-03, the audiences pair
    for voreas-prep-02. A stored brief that passed its own run would be refused today.

    Reads: runs/<run>/brief.json, runs/<run>/extracts/*.json.
    """
    brief = _brief(run)
    probe = {k: v for k, v in brief.items() if k != "readiness"}
    probe_path = tmp_path / "brief.json"
    probe_path.write_text(json.dumps(probe, ensure_ascii=False), encoding="utf-8")
    violations = stages.check_synthesis(probe_path, _extracts(run))
    hits = [v for v in violations if v.startswith(f"{field}:") and "resolution by omission" in v]
    assert hits, f"{run}: check_synthesis did not flag {field}; got {violations}"


# --------------------------------------------------------------------------------------
# 4. Render-stage invention on a cited line (report Addendum 2)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("run", [
    _passes("voreas-prep-02"),
    _xfail("voreas-prep-03", "report Addendum 2: both renders say 'hero video and key "
           "visuals' on deliverables line 2 cited to the RFP, which wrote only 'video'; "
           "'hero' leaked in from the kickoff's garbled χίρο βίντεο"),
])
def test_cited_render_lines_add_no_glossary_term_the_entry_lacks(run):
    """Report Addendum 2. TRANSLATION.md rule 3: rendering adds a language, never
    content. The runner's check_render compares glossary terms against the whole brief
    content blob, so a term that any entry uses can be attributed to any line; harness
    T2.4 passes because the tag resolves. This case compares line by line: a keep_latin
    term on a cited line must appear in that line's own entry content. voreas-prep-02
    satisfies it outright (both renders say 'video and key visuals' on that line).

    Reads: runs/<run>/brief.json, runs/<run>/brief_en.md, runs/<run>/brief_el.md,
    fixtures/voreas_02/client_voreas.json.
    """
    brief = _brief(run)
    known = _source_ids(brief)
    terms = _keep_latin_terms()
    if not terms:
        pytest.fail("precondition: the client config declares keep_latin terms")

    invented = []
    for lang in ("en", "el"):
        by_field = _field_sections(_render(run, lang))
        for field in gates.BRIEF_FIELDS:
            if len(by_field[field]) != len(brief[field]):
                pytest.fail(f"{lang}: precondition, section for {field} renders one line per entry")
            for idx, line in enumerate(by_field[field]):
                bare = _strip_known_tags(line, known).lower()
                content = (brief[field][idx].get("content") or "").lower()
                for term in terms:
                    if term.lower() in bare and term.lower() not in content:
                        invented.append(f"{lang} {field}[{idx}] adds {term!r}: {line[:70]!r}")

    assert not invented, f"{run}: cited render lines carry a term their entry lacks:\n" + "\n".join(invented)


# --------------------------------------------------------------------------------------
# 5. Unmarked spoken-number conversion (report Findings 4)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("run", [
    _xfail("voreas-prep-02", "report Findings 4: 'around 120, maybe 125' written for "
           "«εκατόν είκοσι» in budget[1], conflicts[4] and open_questions[8]; the same "
           "rule also finds an unsourced '50%' in open_questions[4]"),
    _passes("voreas-prep-03"),
])
def test_brief_numerals_trace_to_extract_values(run):
    """Report Findings 4. SOURCES.md rule 4 and SYNTHESIS.md rule 2: numbers transfer
    verbatim in meaning, a spoken «εκατόν είκοσι» stays in words. Roll 1 wrote the
    numerals, which evades the runner's currency gate (needs a currency mark) and the
    harness trap X3 (needs currency or separator patterns). This case fingerprints every
    digit run in the brief's model-authored strings and requires it to occur in a cited
    extract value, anchor or location, or in a source date. voreas-prep-03 satisfies it
    outright (its conflict statement says 'around one hundred twenty').

    Reads: runs/<run>/brief.json, runs/<run>/extracts/*.json.
    """
    extracts = _extracts(run)
    sourced = set()
    for extract in extracts.values():
        sourced |= _digit_runs((extract.get("meta") or {}).get("source_date") or "")
        for item in _extract_items(extract):
            for key in ("value", "anchor", "location"):
                sourced |= _digit_runs(item.get(key) or "")
    if not sourced:
        pytest.fail("precondition: the extracts carry cited figures")

    unsourced = []
    for path, text in _brief_strings(_brief(run)):
        extra = sorted(_digit_runs(text) - sourced)
        if extra:
            unsourced.append(f"{path}: {extra} in {text[:70]!r}")

    assert not unsourced, f"{run}: figures with no cited extract text behind them:\n" + "\n".join(unsourced)


# --------------------------------------------------------------------------------------
# 6. Restatement citation-pairing (report Findings 3; harness T3.1 evidence)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("run", [
    _xfail("voreas-prep-02", "report Findings 3: roll 1 cited the kickoff's restatement "
           "of the RFP for the RFP's position (harness T3.1 C1, C3 both-sources check "
           "failed); conflicts[1], [2] and [4] each cite a single source"),
    _passes("voreas-prep-03"),
])
def test_conflict_positions_span_two_sources(run):
    """Report Findings 3. A conflicts[] object is cross-source by definition
    (SYNTHESIS.md rule 4); a within-source retraction or hedge is rule 7 material.
    Roll 1 paired the transcript's restatement of the RFP with the transcript's
    correction, so the RFP never appears as a position and the harness's both-sources
    check failed. Every open conflict must cite at least two distinct source_ids.
    voreas-prep-03 satisfies it outright (T3.1 4/4).

    Reads: runs/<run>/brief.json, runs/<run>/harness_report.json.
    """
    t31 = next(c for c in _harness_report(run)["checks"] if c["check_id"] == "T3.1")
    expected_status = "fail" if run == "voreas-prep-02" else "pass"
    if t31["status"] != expected_status:
        pytest.fail(f"precondition: stored harness T3.1 is {expected_status}")

    single_source = []
    for idx, conflict in enumerate(_open_conflicts(_brief(run))):
        sources = {p["evidence"]["source_id"] for p in conflict["positions"]}
        if len(sources) < 2:
            single_source.append(f"conflicts[{idx}] ({conflict['field']}): {sorted(sources)}")

    assert not single_source, f"{run}: conflicts whose positions all cite one source:\n" + "\n".join(single_source)


# --------------------------------------------------------------------------------------
# 7. Contradiction-flattening (report Findings 2)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("run", [
    _xfail("voreas-prep-02", "report Findings 2: roll 1 reinterpreted the guidelines-"
           "vs-influencer clash as compatibility and asked the client what their own "
           "guidelines say (open_questions[16]) instead of surfacing the conflict"),
    _passes("voreas-prep-03"),
])
def test_guidelines_vs_influencer_clash_is_a_conflict_not_a_question(run):
    """Report Findings 2. The brand guidelines extract holds 'communicates without
    influencers' as a mandatory; the follow-up extract holds 'three micro-influencers
    for the first wave' as a deliverable. Two sources, one field of tension: SYNTHESIS.md
    rule 4 demands a conflict object citing both anchors. Roll 1 flattened it; roll 2
    (voreas-prep-03) surfaced it, so that run passes outright.

    Reads: runs/<run>/extracts/background_brand_guidelines.json,
    runs/<run>/extracts/transcript_followup.json, runs/<run>/brief.json.
    """
    extracts = _extracts(run)
    guideline_anchors = {i.get("anchor") for i in _extract_items(extracts["background_brand_guidelines"])}
    followup_anchors = {i.get("anchor") for i in _extract_items(extracts["transcript_followup"])}
    if NO_INFLUENCERS_ANCHOR not in guideline_anchors:
        pytest.fail("precondition: guidelines extract holds the rule")
    if THREE_INFLUENCERS_ANCHOR not in followup_anchors:
        pytest.fail("precondition: follow-up extract holds the plan")

    surfaced = [
        idx for idx, conflict in enumerate(_open_conflicts(_brief(run)))
        if {p["evidence"]["anchor"] for p in conflict["positions"]}
        >= {NO_INFLUENCERS_ANCHOR, THREE_INFLUENCERS_ANCHOR}
    ]
    assert surfaced, (
        f"{run}: no conflict object pairs {NO_INFLUENCERS_ANCHOR!r} with "
        f"{THREE_INFLUENCERS_ANCHOR!r}"
    )


# --------------------------------------------------------------------------------------
# 8. Email supersession collapse: the superseded date (report Addendum 3)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("run", [
    _xfail("voreas-prep-02", "report Addendum 3: Jan 31 has zero trace in the emails "
           "extract, internal_conflicts is empty (extract shared byte-identical with prep-03)"),
    _xfail("voreas-prep-03", "report Addendum 3: Jan 31 has zero trace in the emails "
           "extract, internal_conflicts is empty; SOURCES.md rule 3 and its section 5 "
           "email row contradict each other on superseded positions"),
])
def test_email_extract_keeps_the_superseded_launch_date(run):
    """Report Addendum 3. Message 2 of the thread moves the launch to 31 January; message
    4 locks 14 February. SOURCES.md rule 3 says record both values; the section 5 email
    row says record superseded positions as internal_conflicts even when the reversal is
    explicit. The stored extract carries only the final date, so the position trail the
    account lead needs is gone before synthesis ever runs. Asserted dates downstream
    (Addendum 1) start here.

    Reads: fixtures/voreas_02/emails_thread.md, runs/<run>/extracts/emails_thread.json.
    """
    source = _source("emails_thread.md")
    if not any(tok in source for tok in SUPERSEDED_DATE_TOKENS):
        pytest.fail("precondition: the thread states the January date")

    extract = _extracts(run)["emails_thread"]
    carriers = [
        item for item in _extract_items(extract)
        if any(tok in (item.get("value") or "") or tok in (item.get("anchor") or "")
               for tok in SUPERSEDED_DATE_TOKENS)
    ]
    assert carriers, (
        f"{run}: no timeline item or internal conflict in the emails extract carries the "
        f"superseded January date; timeline={[(i.get('value') or '')[:40] for i in extract.get('timeline') or []]}, "
        f"internal_conflicts={len(extract.get('internal_conflicts') or [])}"
    )


# --------------------------------------------------------------------------------------
# 9. Email supersession collapse: the dropped mandatory (report Addendum 3)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("run", [
    _xfail("voreas-prep-02", "report Addendum 3: the guidelines-v2.0 fact is missing "
           "from the emails extract's mandatories (extract shared byte-identical with prep-03)"),
    _xfail("voreas-prep-03", "report Addendum 3: the guidelines-v2.0 fact is missing "
           "from the emails extract's mandatories, the one field SOURCES.md calls asymmetric"),
])
def test_email_extract_keeps_the_guidelines_version_mandatory(run):
    """Report Addendum 3, parenthetical. Message 2 states which guidelines version
    governs ('ισχύει η έκδοση 2.0'). SOURCES.md section 6 makes mandatories the one
    field where a miss is worse than noise; the stored extract's mandatories list is
    empty, so the version pin never reaches the brief.

    Reads: fixtures/voreas_02/emails_thread.md, runs/<run>/extracts/emails_thread.json.
    """
    if GUIDELINES_VERSION_TOKEN not in _source("emails_thread.md"):
        pytest.fail("precondition: the thread names the version")

    extract = _extracts(run)["emails_thread"]
    carriers = [
        item for item in extract.get("mandatories") or []
        if GUIDELINES_VERSION_TOKEN in (item.get("value") or "")
        or GUIDELINES_VERSION_TOKEN in (item.get("anchor") or "")
    ]
    assert carriers, (
        f"{run}: emails extract mandatories carry no guidelines version; "
        f"mandatories={len(extract.get('mandatories') or [])}"
    )
