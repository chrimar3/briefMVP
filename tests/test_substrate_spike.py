"""Cost-audit C4 — the single-call substrate spike. Prompt assembly only; no network, no
model. The api transport is exercised solely by explicit human invocation (CLAUDE.md rule 4)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
import substrate_spike as spike  # noqa: E402

from pipeline import gates  # noqa: E402


def test_system_prompt_carries_skill_schema_and_no_tools_note():
    system = spike.build_system_prompt()
    assert "SOURCES.md" in system                      # the injected skill travels whole
    assert "extract_schema.json" in system             # the output contract is inlined
    assert "keep_latin" in system                      # the client glossary is inlined
    assert "you have NO tools" in system               # single-call mode is explicit


def test_user_prompt_inlines_the_source_and_pins_the_timestamp():
    source = gates.SourceDoc("t", "transcript", "2026-01-01", Path("/x/t.md"),
                             "[00:01:00] CMO: Θέλουμε μπραντ αγουέρνες.")
    prompt = spike.build_user_prompt(source, "proj", {"client_id": "c", "sensitivity_tier": "S1"})
    assert "μπραντ αγουέρνες" in prompt                # source text travels inline, verbatim
    assert spike.FIXED_TS in prompt                    # deterministic meta for comparable runs
    assert "ONLY the JSON extract object" in prompt


def test_fence_stripping_tolerates_both_reply_shapes():
    bare = '{"a": 1}'
    fenced = "```json\n{\"a\": 1}\n```"
    assert spike._strip_fences(bare) == bare
    assert spike._strip_fences(fenced) == bare
