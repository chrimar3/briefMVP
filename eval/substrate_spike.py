"""eval/substrate_spike.py — measure the production-substrate shape on the extraction stage.

    python eval/substrate_spike.py --transport cli [--out runs/cost-c4]
    python eval/substrate_spike.py --transport api [--out runs/cost-c4-api]

Cost-audit C4. The demo pipeline runs every stage as a multi-turn Claude Code subagent that
reads its inputs through tool calls (5–7 turns/stage; C0 measured ~30% of spend as cache
writes those turns generate). PRD DR-1's production shape is one metered call per stage with
the static skeleton prompt-cached. This spike runs the SAME extraction task in that shape —
single turn, zero tools, source inlined, the JSON extract returned as the reply — and grades
every artifact with the pipeline's own `extraction.check_extract` gate. The gate does not
care how an artifact was produced; 4/4 clean is the equivalence claim.

Two transports:
  cli — a single-turn `claude -p` subagent (tools stripped). Same substrate and billing as
        the pipeline; isolates the turn-structure saving. Runs on the subscription today.
  api — a metered `anthropic` SDK call per source (haiku, prompt caching on the static
        prefix). The true production measurement. Requires the `anthropic` package and
        ANTHROPIC_API_KEY (or an `ant auth` profile) — refuses loudly without them, and is
        the ONLY sanctioned non-subagent model path (CLAUDE.md rule 4, amended for C4).

Dev tooling, never a gate, never frozen. Deliberately inlines source content into the prompt
— the runner's paths-not-content rule exists so the RUNNER generalises; a measurement spike
is not the runner.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline import agents, extraction, gates  # noqa: E402

FIXED_TS = "2026-07-25T00:00:00"  # deterministic meta.extraction_ts for comparable runs


def build_system_prompt() -> str:
    """The static, cacheable prefix: the extract agent's full definition body (injected
    SOURCES.md and all) plus the two static contracts (schema, glossary are per-client
    static — they change per onboarding, not per call)."""
    body = agents.build_inline_agent("extract")["extract"]["prompt"]
    schema = (gates.SCHEMA_DIR / "extract_schema.json").read_text(encoding="utf-8")
    glossary_path = extraction.resolve_glossary()
    glossary = Path(glossary_path).read_text(encoding="utf-8")
    return (
        f"{body}\n\n"
        f"===== OUTPUT CONTRACT (extract_schema.json) =====\n{schema}\n\n"
        f"===== CLIENT GLOSSARY =====\n{glossary}\n\n"
        f"SUBSTRATE NOTE — single-call mode: you have NO tools. The source document is "
        f"inlined in the user message. Reply with ONLY the JSON extract object — no prose, "
        f"no code fences, no commentary. Your reply IS the artifact."
    )


def build_user_prompt(source: gates.SourceDoc, project_id: str, client_config: dict) -> str:
    return (
        f"EXTRACTION WORK ORDER — single-call substrate (cost-audit C4).\n\n"
        f"Parameters:\n"
        f"  project_id={project_id} · client_id={client_config['client_id']}"
        f" · sensitivity_tier={client_config['sensitivity_tier']}\n"
        f"  source_id={source.source_id} · source_type={source.source_type}"
        f" · source_date={source.source_date}\n"
        f"  meta.extraction_ts={FIXED_TS} · meta.agent_version=1.0\n\n"
        f"===== SOURCE DOCUMENT ({source.source_id}) =====\n{source.text}\n"
        f"===== END SOURCE =====\n\n"
        f"Reply with ONLY the JSON extract object."
    )


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[: -3]
    return text.strip()


def run_cli(system_prompt: str, user_prompt: str) -> tuple:
    """One single-turn subagent call: same billing substrate as the pipeline, zero tools."""
    inline = {"c4-extract": {"description": "single-call extraction spike", "prompt": system_prompt,
                             "tools": [], "model": "haiku"}}
    cmd = [agents.CLAUDE_BIN, "-p", user_prompt,
           "--agents", json.dumps(inline, ensure_ascii=False), "--agent", "c4-extract",
           "--output-format", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=agents.DEFAULT_TIMEOUT_S)
    payload = json.loads(proc.stdout)
    usage = payload.get("modelUsage") or {}
    return payload.get("result") or "", {
        "cost_usd": payload.get("total_cost_usd"),
        "num_turns": payload.get("num_turns"),
        "usage": {k: sum((m.get(k) or 0) for m in usage.values())
                  for k in ("input_tokens", "output_tokens",
                            "cache_read_input_tokens", "cache_creation_input_tokens")},
    }


#: Haiku 4.5 list rates $/MTok (input, output, cache_read, cache_write_5m) — for the api
#: transport, whose responses report tokens, not dollars. Snapshot 2026-07-25.
_HAIKU = (1.00, 5.00, 0.10, 1.25)


def run_api(system_prompt: str, user_prompt: str) -> tuple:
    """One metered API call (production shape). Loud preflight: this is the only sanctioned
    non-subagent model path (CLAUDE.md rule 4, C4 amendment) and it never runs implicitly."""
    try:
        import anthropic
    except ImportError:
        raise SystemExit("[spike] the api transport needs `pip install anthropic`")
    client = anthropic.Anthropic()  # resolves ANTHROPIC_API_KEY / ant-auth profile; errors if neither
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=16000,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_prompt}],
    )
    u = response.usage
    tokens = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
              "cache_read_input_tokens": u.cache_read_input_tokens or 0,
              "cache_creation_input_tokens": u.cache_creation_input_tokens or 0}
    p_in, p_out, p_cr, p_cw = _HAIKU
    cost = (tokens["input_tokens"] * p_in + tokens["output_tokens"] * p_out
            + tokens["cache_read_input_tokens"] * p_cr
            + tokens["cache_creation_input_tokens"] * p_cw) / 1e6
    text = "".join(b.text for b in response.content if b.type == "text")
    return text, {"cost_usd": round(cost, 6), "num_turns": 1, "usage": tokens}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Single-call substrate spike (extraction).")
    parser.add_argument("--transport", choices=("cli", "api"), required=True)
    parser.add_argument("--project", default=str(REPO_ROOT / "fixtures" / "northlight_01"))
    parser.add_argument("--out", default=str(REPO_ROOT / "runs" / "cost-c4"))
    args = parser.parse_args(argv)

    sources = gates.discover_sources(Path(args.project))
    glossary_path = extraction.resolve_glossary()
    client_config = extraction.load_client_config(glossary_path)
    system_prompt = build_system_prompt()
    out_dir = Path(args.out) / "extracts"
    out_dir.mkdir(parents=True, exist_ok=True)

    runner = run_cli if args.transport == "cli" else run_api
    results, total = [], 0.0
    for source in sources:
        text, meter = runner(system_prompt, build_user_prompt(
            source, Path(args.project).name, client_config))
        path = out_dir / f"{source.source_id}.json"
        try:
            artifact = json.loads(_strip_fences(text))
            path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
            violations = extraction.check_extract(path, source.text, client_config)
        except json.JSONDecodeError as exc:
            violations = [f"reply is not valid JSON: {exc}"]
        total += meter["cost_usd"] or 0.0
        results.append({"source_id": source.source_id, "violations": violations, **meter})
        status = "clean" if not violations else f"{len(violations)} VIOLATION(S)"
        u = meter["usage"]
        print(f"  {source.source_id:<28} ${meter['cost_usd'] or 0:.4f} · turns={meter['num_turns']}"
              f" · out={u['output_tokens']:,} · cw={u['cache_creation_input_tokens']:,}"
              f" · cr={u['cache_read_input_tokens']:,} · {status}")
        for v in violations[:4]:
            print(f"      · {v[:140]}")

    clean = sum(1 for r in results if not r["violations"])
    print(f"\n  {clean}/{len(results)} extracts pass the pipeline gate · total ${total:.4f} "
          f"({args.transport} transport)")
    (Path(args.out) / f"substrate_spike_{args.transport}.json").write_text(
        json.dumps({"transport": args.transport, "total_cost_usd": round(total, 6),
                    "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if clean == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
