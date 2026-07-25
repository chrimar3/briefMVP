"""Step 9 (Tier 4) — the deterministic guards around the creative-shadow stage.

The two guarantees under test are the ones a model cannot be trusted to self-enforce: it may
run only on a signed-off brief (DR-8), and it may not invent a channel spec (DR-7)."""

import json

import pytest

from pipeline import creative, gates

SPEC_TABLE = {
    "specs": [
        {"id": "tiktok_infeed_video", "channel": "TikTok", "aspect_ratio": "9:16", "resolution": "1080x1920"},
        {"id": "instagram_feed_image", "channel": "Instagram", "aspect_ratio": "4:5", "resolution": "1080x1350"},
    ]
}

SHADOW = "> SHADOW MODE — evaluation draft. Not for delivery.\n\n"


def _draft(tmp_path, body):
    path = tmp_path / "creative_brief_sonnet.md"
    path.write_text(body, encoding="utf-8")
    return path


# --------------------------------------------------------------------------------------
# Sign-off gate (DR-8)
# --------------------------------------------------------------------------------------


def test_signed_off_brief_passes():
    creative.require_signed_off({"signoff": {"status": "signed_off"}})


@pytest.mark.parametrize("status", ["draft", None])
def test_unsigned_brief_is_refused(status):
    with pytest.raises(creative.NotSignedOff):
        creative.require_signed_off({"signoff": {"status": status}} if status else {"signoff": {}})


# --------------------------------------------------------------------------------------
# Spec-match gate (DR-7) — the Tier-4 machine check
# --------------------------------------------------------------------------------------


def test_draft_using_only_table_specs_passes(tmp_path):
    body = SHADOW + "## Deliverables\nTikTok in-feed video, 9:16, 1080x1920. [spec: tiktok_infeed_video]\n"
    assert creative.check_creative_brief(_draft(tmp_path, body), SPEC_TABLE) == []


def test_invented_resolution_is_caught(tmp_path):
    """1920x1080 (landscape) is not in the table — a generated spec, which DR-7 forbids."""
    body = SHADOW + "## Deliverables\nHero video, 1920x1080. [spec: tiktok_infeed_video]\n"
    violations = creative.check_creative_brief(_draft(tmp_path, body), SPEC_TABLE)
    assert len(violations) == 1 and "1920x1080" in violations[0] and "never generated" in violations[0]


def test_invented_aspect_ratio_is_caught(tmp_path):
    body = SHADOW + "## Deliverables\nBillboard, 16:9. [spec: none]\n"
    violations = creative.check_creative_brief(_draft(tmp_path, body), SPEC_TABLE)
    assert any("16:9" in v for v in violations)


def test_spec_match_tolerates_spacing(tmp_path):
    """`1080 x 1920` is the same fact as `1080x1920` — formatting, not a different spec."""
    body = SHADOW + "## Deliverables\nReel, 1080 x 1920.\n"
    assert creative.check_creative_brief(_draft(tmp_path, body), SPEC_TABLE) == []


def test_video_duration_timecode_is_not_flagged_as_a_spec(tmp_path):
    """Regression (Tier-4 A/B): '00:06' is a six-second duration, not an aspect ratio. Flagging
    it forced both models to strip legitimate durations on the first attempt."""
    body = SHADOW + "## Deliverables\nTikTok in-feed video, 9:16, 1080x1920, cut at 00:06 and 00:15.\n"
    assert creative.check_creative_brief(_draft(tmp_path, body), SPEC_TABLE) == []


def test_invented_aspect_ratio_is_still_caught_after_the_timecode_fix(tmp_path):
    """The fix must not open a hole: 16:9 (not in the table) is still an invented spec."""
    body = SHADOW + "## Deliverables\nLandscape hero, 16:9.\n"
    assert any("16:9" in v for v in creative.check_creative_brief(_draft(tmp_path, body), SPEC_TABLE))


def test_duration_without_a_leading_zero_is_not_flagged_as_a_spec(tmp_path):
    """Regression (design audit F1) — the fifth gate false positive, same family as the
    timecodes: '1:30' is a ninety-second cut, not an aspect ratio. Flagging it forces the
    model to strip legitimate durations, corrupting good content to satisfy the gate."""
    body = SHADOW + "## Deliverables\nHero film: a 1:30 cut and a 1:15 cutdown, 9:16. [spec: tiktok_infeed_video]\n"
    assert creative.check_creative_brief(_draft(tmp_path, body), SPEC_TABLE) == []


def test_common_invented_aspect_ratios_are_still_caught_after_the_duration_fix(tmp_path):
    """The narrowing must keep the useful catches: single-digit denominators (16:9, 4:3,
    3:2, 21:9) are exactly the ratios a model would invent, and every one still fails."""
    body = SHADOW + "## Deliverables\nHero 16:9, print 4:3, banner 3:2, cinema 21:9.\n"
    violations = creative.check_creative_brief(_draft(tmp_path, body), SPEC_TABLE)
    assert len(violations) == 4


def test_missing_shadow_banner_is_caught(tmp_path):
    body = "## Deliverables\nTikTok video 9:16 1080x1920.\n"
    violations = creative.check_creative_brief(_draft(tmp_path, body), SPEC_TABLE)
    assert any("SHADOW MODE" in v for v in violations)


def test_missing_file_is_caught(tmp_path):
    assert "no creative brief" in creative.check_creative_brief(tmp_path / "nope.md", SPEC_TABLE)[0]


# --------------------------------------------------------------------------------------
# Spec table loading
# --------------------------------------------------------------------------------------


def test_shipped_spec_table_loads_and_has_rows():
    table = creative.load_spec_table()
    assert table["specs"] and all(r.get("id") for r in table["specs"])


def test_shipped_spec_table_declares_it_is_a_lookup_not_generated(repo_root):
    raw = json.loads((repo_root / "config" / "channel_specs.json").read_text(encoding="utf-8"))
    assert "DR-7" in raw["_what_this_is"]
    assert "SELECTS" in raw["_what_this_is"] or "selects" in raw["_what_this_is"]


def test_empty_spec_table_is_refused(tmp_path):
    path = tmp_path / "specs.json"
    path.write_text(json.dumps({"specs": []}), encoding="utf-8")
    with pytest.raises(creative.CreativeError, match="no rows"):
        creative.load_spec_table(path)


def test_every_table_spec_value_is_self_consistent():
    """A spec value in the table must itself pass the token detectors — otherwise the gate
    could never match it and every use would be a false positive."""
    table = creative.load_spec_table()
    body = "> SHADOW MODE\n" + " ".join(
        f"{r.get('resolution','')} {r.get('aspect_ratio','')}" for r in table["specs"]
    )
    from pathlib import Path
    import tempfile
    p = Path(tempfile.mkdtemp()) / "d.md"
    p.write_text(body, encoding="utf-8")
    assert creative.check_creative_brief(p, table) == []
