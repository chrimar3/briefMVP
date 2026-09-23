"""The shared record I/O (pipeline/records.py) and the one clock (pipeline/clock.py)."""

import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pipeline import clock, effort, records, retention, revisions, stages

REPO = Path(__file__).resolve().parents[1]
FROZEN = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc)


# -- records ----------------------------------------------------------------------------

def test_load_optional_missing_is_the_default_and_corrupt_is_named(tmp_path):
    path = tmp_path / "record.json"
    assert records.load_optional(path) is None
    assert records.load_optional(path, {"empty": True}) == {"empty": True}
    path.write_text("{", encoding="utf-8")
    with pytest.raises(records.CorruptRecordError) as caught:
        records.load_optional(path, {})
    assert isinstance(caught.value, ValueError) and caught.value.path == path
    assert "record.json" in str(caught.value)
    path.write_bytes(b'{"x": "\xff"}')
    with pytest.raises(records.CorruptRecordError):
        records.load_optional(path)


def test_load_strict_requires_the_record(tmp_path):
    with pytest.raises(FileNotFoundError):
        records.load_strict(tmp_path / "absent.json")
    (tmp_path / "ok.json").write_text('{"a": 1}', encoding="utf-8")
    assert records.load_strict(tmp_path / "ok.json") == {"a": 1}


def test_write_json_is_the_revisions_format_and_leaves_no_debris(tmp_path):
    path = tmp_path / "nested" / "record.json"
    records.write_json(path, {"name": "Συνθετικό", "n": 1})
    assert path.read_text(encoding="utf-8") == json.dumps({"name": "Συνθετικό", "n": 1},
                                                          ensure_ascii=False, indent=2) + "\n"
    assert revisions.write_json is records.write_json and revisions.load is records.load_optional
    assert [p.name for p in path.parent.iterdir()] == ["record.json"]


def test_failed_atomic_write_keeps_the_old_record(tmp_path, monkeypatch):
    path = tmp_path / "record.json"
    records.write_json(path, {"v": 1})

    def fail(*args):
        raise OSError("synthetic replace failure")
    monkeypatch.setattr(records.os, "replace", fail)
    with pytest.raises(OSError):
        records.write_json(path, {"v": 2})
    assert json.loads(path.read_text(encoding="utf-8")) == {"v": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["record.json"]


# -- clock ------------------------------------------------------------------------------

def test_frozen_clock_drives_every_written_timestamp(tmp_path):
    with clock.frozen(FROZEN):
        assert clock.timestamp() == "2026-09-23T10:00:00+00:00"
        assert clock.timestamp("seconds") == "2026-09-23T10:00:00+00:00"
        assert revisions.timestamp() == "2026-09-23T10:00:00+00:00"
        assert retention._now() == "2026-09-23T10:00:00+00:00"
        assert clock.compact("%Y%m%d-%H%M%S") == "20260923-100000"
        saved = effort.record(tmp_path, actor="Synthetic", role="operator", minutes=1, event_id="e1")
        assert saved["recorded_at"] == "2026-09-23T10:00:00+00:00"
    assert clock.now() > FROZEN  # restored to the system clock


def test_injected_times_are_normalised_to_utc_and_naive_ones_refused():
    athens = timezone(timedelta(hours=3))
    with clock.frozen(datetime(2026, 9, 23, 13, 0, tzinfo=athens)):
        assert clock.timestamp("seconds") == "2026-09-23T10:00:00+00:00"
    with pytest.raises(ValueError):
        with clock.frozen(datetime(2026, 9, 23, 10, 0)):
            pass
    previous = clock.set_clock(lambda: datetime(2026, 9, 23, 10, 0))
    try:
        with pytest.raises(ValueError):
            clock.now()
    finally:
        clock.set_clock(previous)


def test_synthesis_work_order_stamps_utc(tmp_path):
    with clock.frozen(FROZEN):
        order = stages.build_synthesis_order(
            tmp_path, tmp_path / "brief.json", "p", {"client_id": "c"},
            {"project_type": "other", "classification_confidence": "high", "sensitivity_tier": "S1"},
            [], tmp_path / "g.json")
    assert "created_ts                = 2026-09-23T10:00:00+00:00" in order


# -- layering ---------------------------------------------------------------------------

def _pipeline_imports(path: Path) -> set:
    """Every `pipeline` module a file imports, at any depth (function-local imports included)."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module == "pipeline":
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("pipeline."):
            found.add(node.module.split(".", 1)[1])
        elif isinstance(node, ast.Import):
            found.update(a.name.split(".", 1)[1] for a in node.names if a.name.startswith("pipeline."))
    return found


@pytest.mark.parametrize("module,allowed", [
    ("revisions", {"clock", "records"}),
    ("records", set()),
    ("clock", set()),
    ("money", set()),
    ("stage_common", {"agents", "gates"}),
])
def test_utility_modules_import_no_policy(module, allowed):
    assert _pipeline_imports(REPO / "pipeline" / f"{module}.py") <= allowed


def test_moved_names_still_resolve_from_their_old_homes():
    from pipeline import approval, clarifications
    assert revisions.require_current_approval is approval.require_current_approval
    assert revisions.carry_decisions is clarifications.carry_decisions
    with pytest.raises(AttributeError):
        revisions.no_such_name  # noqa: B018
