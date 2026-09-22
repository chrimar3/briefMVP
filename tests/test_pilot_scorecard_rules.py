"""Every SCORECARD.md §4 pass rule, evaluated as pass / fail / insufficient_data.
Synthetic rows only; missing data is never a pass."""

import csv

import pytest

from eval import pilot_scorecard as sc


def row(brief, phase="retro", lead="L1", **overrides):
    base = dict(row_type="PILOT", brief_id=brief, phase=phase, lead_id=lead, assembly_min="15", review_min="25",
                total_attention_min="40", oq_total="10", oq_real="9", oq_duplicate="1", oq_answered_in_sources="0",
                oq_not_worth_asking="0", ce_total="0", schema_valid="yes", survival_en_pct="80", survival_el_pct="75",
                initiated_by="lead", manual_fallback="no")
    base.update(overrides)
    return base


def retro_set(**overrides):
    return [row(f"r{i}", lead="L1" if i < 3 else "L2", **overrides) for i in range(6)]


def rules(report, week):
    return {r["rule"]: r for r in report["pass_rules"][week]["rules"]}


def test_complete_passing_retro_set_passes_every_week_3_rule():
    report = sc.summarize(retro_set())
    week3 = report["pass_rules"]["end_week_3"]
    assert week3["gate"] == "pass"
    assert set(rules(report, "end_week_3")) == {"assembly_le_20", "review_under_30", "total_attention_le_50",
                                                "question_precision_gt_80", "critical_errors_zero",
                                                "schema_valid_all", "retro_set_complete"}
    # No live rows yet: week 4 cannot pass.
    assert report["pass_rules"]["end_week_4"]["gate"] == "insufficient_data"


@pytest.mark.parametrize("override, rule_id", [
    ({"assembly_min": "21", "total_attention_min": "46"}, "assembly_le_20"),
    ({"review_min": "30", "total_attention_min": "45"}, "review_under_30"),
    ({"total_attention_min": "51", "review_min": "29", "assembly_min": "22"}, "total_attention_le_50"),
    ({"oq_real": "8", "oq_duplicate": "2"}, "question_precision_gt_80"),
    ({"schema_valid": "no"}, "schema_valid_all"),
])
def test_each_threshold_fails_on_its_own(override, rule_id):
    report = sc.summarize(retro_set(**override))
    assert rules(report, "end_week_3")[rule_id]["status"] == "fail"
    assert report["pass_rules"]["end_week_3"]["gate"] == "fail"


def test_one_critical_error_fails_the_set():
    rows = retro_set()
    rows[4]["ce_total"] = "1"
    rule = rules(sc.summarize(rows), "end_week_3")["critical_errors_zero"]
    assert rule["status"] == "fail" and "r4" in rule["note"]


def test_a_missing_measurement_is_insufficient_never_a_pass():
    rows = retro_set()
    rows[2]["review_min"] = "not_recorded"
    rows[2]["total_attention_min"] = "not_recorded"
    report = sc.summarize(rows)
    assert rules(report, "end_week_3")["review_under_30"]["status"] == "insufficient_data"
    assert report["pass_rules"]["end_week_3"]["gate"] == "insufficient_data"


def test_fewer_than_six_retro_briefs_cannot_pass_week_3():
    report = sc.summarize(retro_set()[:5])
    assert rules(report, "end_week_3")["retro_set_complete"]["status"] == "insufficient_data"
    assert report["pass_rules"]["end_week_3"]["gate"] == "insufficient_data"


def test_manual_fallback_is_reported_and_excluded_from_timing_rules():
    rows = retro_set() + [row("fallback", assembly_min="not_recorded", review_min="not_recorded",
                              total_attention_min="not_recorded", manual_fallback="yes")]
    report = sc.summarize(rows)
    assert report["pass_rules"]["end_week_3"]["gate"] == "pass"
    assert report["pass_rules"]["reported"]["manual_fallback_briefs"] == 1
    assert report["pass_rules"]["reported"]["manual_fallback_share_pct"] == pytest.approx(100 / 7)
    # ...and a fallback cannot fill the six-brief set.
    rows = retro_set()[:5] + [row("fallback", manual_fallback="yes")]
    assert sc.summarize(rows)["pass_rules"]["end_week_3"]["gate"] == "insufficient_data"


def test_briefs_without_questions_are_excluded_from_precision_not_scored_100():
    rows = retro_set()
    rows[0].update(oq_total="0", oq_real="0", oq_duplicate="0")
    rule = rules(sc.summarize(rows), "end_week_3")["question_precision_gt_80"]
    assert rule["status"] == "pass" and rule["n"] == 5 and "no open questions" in rule["note"]


def test_week_4_rules_include_survival_and_two_of_two_adoption():
    rows = retro_set() + [row("live1", phase="live", lead="L1"), row("live2", phase="live", lead="L2")]
    report = sc.summarize(rows)
    week4 = rules(report, "end_week_4")
    assert week4["survival_en_gt_70"]["status"] == "pass" and week4["survival_el_gt_70"]["status"] == "pass"
    assert week4["adoption_2_of_2"]["observed"] == "2/2"
    assert report["pass_rules"]["end_week_4"]["gate"] == "pass"
    rows[-1]["initiated_by"] = "operator"
    assert rules(sc.summarize(rows), "end_week_4")["adoption_2_of_2"]["status"] == "fail"
    rows[-1]["initiated_by"] = "lead"
    rows[-1]["survival_el_pct"] = "60"
    rows[-2]["survival_el_pct"] = "70"
    assert rules(sc.summarize(rows), "end_week_4")["survival_el_gt_70"]["status"] == "fail"


def test_creative_delivery_columns_are_reported_and_waivers_warned():
    rows = retro_set()
    rows[0].update(creative_released="yes", sod_waiver="yes")
    rows[1].update(creative_released="yes", creative_withdrawn="yes")
    reported = sc.summarize(rows)["pass_rules"]["reported"]
    assert reported["creative_released"] == 2 and reported["creative_withdrawn"] == 1
    assert reported["sod_waivers"] == 1 and "synthetic rehearsal only" in reported["warning"]


def test_invalid_flag_values_are_data_errors():
    rows = retro_set()
    rows[0]["manual_fallback"] = "maybe"
    with pytest.raises(ValueError, match="manual_fallback"):
        sc.summarize(rows)


def test_template_example_row_evaluates_to_insufficient_data(repo_root):
    """The shipped template carries only the EXAMPLE row, which never counts."""
    with (repo_root / "docs" / "pilot" / "scorecard_template.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for column in ("creative_approved", "creative_released", "creative_withdrawn", "sod_waiver", "manual_fallback"):
        assert column in rows[0]
    report = sc.summarize(rows)
    assert report["briefs"] == 0
    assert report["pass_rules"]["end_week_3"]["gate"] == "insufficient_data"
    assert report["pass_rules"]["end_week_4"]["gate"] == "insufficient_data"
