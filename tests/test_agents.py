"""Tier-0 DoD: all 6 agent files exist with the correct model alias and skill injection.

The injection check is byte-exact on purpose. The four skeleton files are the product
(README: `skills/*.md` ships to the client); an agent prompt that has drifted from its
skill is a silent spec fork, and this is the only thing standing between the repo and
that fork. When it fails, the fix is to re-sync the agent file from the skill — never
to edit the copy inside the agent.
"""

import pytest

from conftest import split_frontmatter

#: The routing table of CLAUDE.md, as a test. Schema-following work -> haiku;
#: judgment work -> sonnet. Changing a value here is a human decision (CLAUDE.md).
AGENT_SPEC = {
    "extract": ("haiku", "skills/SOURCES.md"),
    "classify": ("haiku", None),
    "fidelity-check": ("haiku", "skills/TRANSCRIPTS.md"),
    "synthesize": ("sonnet", "skills/SYNTHESIS.md"),
    "render": ("sonnet", "skills/TRANSLATION.md"),
    "creative-shadow": ("sonnet", None),
}

#: Rule 4 — no network calls beyond the model itself; and no shell out of a runtime agent.
FORBIDDEN_TOOLS = {"Bash", "WebFetch", "WebSearch", "Task", "NotebookEdit"}


@pytest.fixture(params=sorted(AGENT_SPEC))
def agent(request, repo_root):
    name = request.param
    path = repo_root / ".claude" / "agents" / f"{name}.md"
    assert path.is_file(), f"missing agent definition: {path}"
    frontmatter, body = split_frontmatter(path)
    return name, frontmatter, body


def test_agent_name_matches_filename(agent):
    name, frontmatter, _ = agent
    assert frontmatter.get("name") == name


def test_agent_has_triggering_description(agent):
    name, frontmatter, _ = agent
    description = (frontmatter.get("description") or "").strip()
    assert len(description) >= 40, f"{name}: description too thin to route on"


def test_agent_model_alias(agent):
    """DoD 2a — correct model alias per the routing table."""
    name, frontmatter, _ = agent
    expected_model, _skill = AGENT_SPEC[name]
    assert frontmatter.get("model") == expected_model


def test_agent_model_is_an_alias_not_a_pinned_id(agent):
    """TIERS.md §Models: aliases resolve to the latest generation; pinned IDs freeze the demo."""
    name, frontmatter, _ = agent
    model = str(frontmatter.get("model", ""))
    assert model in {"haiku", "sonnet"}, f"{name}: {model!r} is not a bare alias"
    assert not model.startswith("claude-"), f"{name}: pinned model id {model!r}"


def test_agent_tools_are_least_privilege(agent):
    """Runtime agents read sources and write artifacts. Nothing else."""
    name, frontmatter, _ = agent
    raw = frontmatter.get("tools")
    assert raw, f"{name}: no `tools` field — agents must not inherit full tool access"
    tools = {t.strip() for t in raw.split(",")} if isinstance(raw, str) else set(raw)
    leaked = tools & FORBIDDEN_TOOLS
    assert not leaked, f"{name}: forbidden tool(s) {sorted(leaked)}"


def test_skill_is_injected_verbatim(agent, repo_root):
    """DoD 2b — the four skill-backed agents carry their skill file byte-exact.

    `extract` <- SOURCES.md · `synthesize` <- SYNTHESIS.md
    `render`  <- TRANSLATION.md · `fidelity-check` <- TRANSCRIPTS.md
    """
    name, _frontmatter, body = agent
    _model, skill = AGENT_SPEC[name]
    if skill is None:
        pytest.skip(f"{name} carries inline instructions by design")

    skill_text = (repo_root / skill).read_text(encoding="utf-8")
    begin = f"===== BEGIN INJECTED SKILL: {skill} ====="
    end = f"===== END INJECTED SKILL: {skill} ====="
    assert begin in body and end in body, f"{name}: injection markers for {skill} missing"

    injected = body.split(begin, 1)[1].split(end, 1)[0]
    assert injected.strip("\n") == skill_text.strip("\n"), (
        f"{name}: injected copy of {skill} has drifted from the source file. "
        f"Re-sync the agent from the skill; do not edit the injected block."
    )


def test_inline_agents_declare_no_skill_injection(agent):
    """`classify` and `creative-shadow` are inline by design — no half-injected state."""
    name, _frontmatter, body = agent
    _model, skill = AGENT_SPEC[name]
    if skill is not None:
        pytest.skip(f"{name} is skill-backed")
    assert "BEGIN INJECTED SKILL" not in body
    assert len(body.strip()) >= 500, f"{name}: inline instructions are too thin to govern a stage"


def test_no_stray_agent_definitions(repo_root):
    """Exactly six agents — an undeclared seventh would run outside the routing table."""
    found = {p.stem for p in (repo_root / ".claude" / "agents").glob("*.md")}
    assert found == set(AGENT_SPEC)


def test_every_skill_file_is_injected_somewhere(repo_root):
    """All four skeleton files reach a runtime agent — none is documentation-only."""
    injected = {skill for _model, skill in AGENT_SPEC.values() if skill}
    on_disk = {f"skills/{p.name}" for p in (repo_root / "skills").glob("*.md")}
    assert on_disk == injected


# --------------------------------------------------------------------------------------
# Inline-agent payload for the clean-substrate invocation (pipeline/agents.py)
# --------------------------------------------------------------------------------------


def test_build_inline_agent_carries_prompt_model_and_tools():
    """The --agents payload must reproduce the .md definition: system prompt, model, tools.

    This is what lets a subagent run from a neutral cwd instead of the repo root, so the
    build-time CLAUDE.md is never auto-loaded into a runtime agent (the substrate fix)."""
    from pipeline import agents

    payload = agents.build_inline_agent("extract")
    assert set(payload) == {"extract"}
    spec = payload["extract"]
    assert spec["model"] == "haiku"
    assert spec["tools"] == ["Read", "Write"]
    # The body is the system prompt verbatim — injected skill and all.
    assert "BEGIN INJECTED SKILL: skills/SOURCES.md" in spec["prompt"]
    assert spec["description"]


def test_build_inline_agent_routes_judgment_work_to_sonnet():
    from pipeline import agents

    assert agents.build_inline_agent("synthesize")["synthesize"]["model"] == "sonnet"


def test_build_inline_agent_is_json_serialisable():
    """It is passed to the CLI as one argv element via json.dumps — Greek, quotes and all."""
    import json as _json
    from pipeline import agents

    for name in ("extract", "synthesize", "render", "fidelity-check"):
        _json.dumps(agents.build_inline_agent(name), ensure_ascii=False)


def test_build_inline_agent_rejects_an_unknown_agent():
    from pipeline import agents

    with pytest.raises(agents.SubagentError, match="no agent definition"):
        agents.build_inline_agent("does-not-exist")


# --------------------------------------------------------------------------------------
# The shared invoke-gate-repair loop (design audit F7)
# --------------------------------------------------------------------------------------


def _fake_invoke(calls):
    from pipeline import agents

    def fake(agent, prompt, access_dirs, timeout_s=agents.DEFAULT_TIMEOUT_S, model_override=None):
        calls.append({"prompt": prompt, "model_override": model_override})
        return agents.SubagentResult(agent=agent, ok=True)

    return fake


def test_run_gated_repairs_once_and_logs_every_attempt(tmp_path, monkeypatch):
    """One loop serves every model stage: gate fails once, the repair prompt goes out, and
    both attempts land in the durable repair log with the caller's stage/site labels."""
    import json as _json
    from pipeline import agents

    calls = []
    monkeypatch.setattr(agents, "invoke", _fake_invoke(calls))
    verdicts = iter([["broken"], []])

    attempts, failed = agents.run_gated(
        "extract", "ORDER", lambda: next(verdicts), lambda v: f"REPAIR {v[0]}",
        [], stage="extraction", site="src1", run_dir=tmp_path,
    )
    assert failed is None and len(attempts) == 2
    assert [c["prompt"] for c in calls] == ["ORDER", "REPAIR broken"]

    log = (tmp_path / "diagnostics" / "repair_log.jsonl").read_text(encoding="utf-8").splitlines()
    records = [_json.loads(line) for line in log]
    assert [(r["stage"], r["site"], r["attempt"]) for r in records] == [
        ("extraction", "src1", 1), ("extraction", "src1", 2)]


def test_run_gated_gives_up_after_the_attempt_budget(tmp_path, monkeypatch):
    from pipeline import agents

    calls = []
    monkeypatch.setattr(agents, "invoke", _fake_invoke(calls))
    attempts, failed = agents.run_gated(
        "extract", "ORDER", lambda: ["still broken"], lambda v: "REPAIR",
        [], stage="extraction", site="src1", run_dir=tmp_path,
    )
    assert failed == ["still broken"]
    assert len(attempts) == agents.MAX_ATTEMPTS and len(calls) == agents.MAX_ATTEMPTS


def test_run_gated_passes_the_model_override_through(monkeypatch):
    """The Tier-4 A/B depends on this: same agent definition, only the model moves."""
    from pipeline import agents

    calls = []
    monkeypatch.setattr(agents, "invoke", _fake_invoke(calls))
    agents.run_gated("creative-shadow", "ORDER", lambda: [], lambda v: "",
                     [], stage="creative-shadow", site="opus", model_override="opus")
    assert calls[0]["model_override"] == "opus"


def test_repair_order_carries_the_violations_verbatim():
    from pipeline import agents

    text = agents.repair_order("brief", ["v1", "v2"], "Fix exactly these.")
    assert text.startswith("REPAIR ORDER — your brief failed the gate:\n")
    assert "  - v1\n  - v2" in text and text.endswith("Fix exactly these.")


# --------------------------------------------------------------------------------------
# Per-stage effort policy (cost-audit C2)
# --------------------------------------------------------------------------------------


def test_stage_effort_missing_file_means_cli_default(tmp_path):
    from pipeline import agents

    assert agents.stage_effort("render", path=tmp_path / "absent.json") is None


def test_stage_effort_reads_the_level(tmp_path):
    import json as _json
    from pipeline import agents

    p = tmp_path / "routing.json"
    p.write_text(_json.dumps({"effort": {"render": "low"}}), encoding="utf-8")
    assert agents.stage_effort("render", path=p) == "low"
    assert agents.stage_effort("synthesize", path=p) is None  # uncapped stage → default


def test_stage_effort_rejects_an_invalid_level_loudly(tmp_path):
    """A silent fallback would let a measured cost number and the config that produced it
    disagree — malformed policy fails the run, mirroring gates.load_readiness_policy."""
    import json as _json

    import pytest as _pytest

    from pipeline import agents

    p = tmp_path / "routing.json"
    p.write_text(_json.dumps({"effort": {"render": "turbo"}}), encoding="utf-8")
    with _pytest.raises(agents.SubagentError, match="turbo"):
        agents.stage_effort("render", path=p)


def test_shipping_routing_policy_is_valid():
    """Every configured stage is a real agent; every level is one the CLI accepts; and
    synthesis — the judgment core — carries no cap (capping it is a human decision)."""
    import json as _json

    from pipeline import agents

    policy = _json.loads(agents.ROUTING_POLICY_PATH.read_text(encoding="utf-8"))
    for agent_name, level in (policy.get("effort") or {}).items():
        assert agent_name in AGENT_SPEC, f"unknown agent {agent_name!r} in routing policy"
        assert level in agents.EFFORT_LEVELS
    assert "synthesize" not in (policy.get("effort") or {})
