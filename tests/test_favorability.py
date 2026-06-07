from datetime import datetime, timedelta

from tests.helpers import load_module

favorability = load_module("groupmate_agent_favorability_under_test", "favorability.py")


def test_score_conversions_clamp_to_supported_range():
    assert favorability.clamp_raw_favorability(-9999) == favorability.MIN_RAW_FAVORABILITY
    assert favorability.clamp_raw_favorability(9999) == favorability.MAX_RAW_FAVORABILITY
    assert favorability.raw_to_score(245) == 24
    assert favorability.score_to_raw(999) == favorability.MAX_RAW_FAVORABILITY


def test_state_and_status_descriptions_cover_thresholds():
    assert favorability.get_favorability_state(-900) == "broken"
    assert favorability.get_favorability_state(-500) == "distressed"
    assert favorability.get_favorability_state(-200) == "upset"
    assert favorability.get_favorability_state(0) == "normal"
    assert favorability.get_favorability_state(200) == "happy"
    assert favorability.get_favorability_state(500) == "affectionate"
    assert favorability.get_favorability_state(750) == "enamored"
    assert favorability.get_favorability_state(900) == "love"
    assert favorability.status_desc_from_score(100) == "恋人/依赖"


def test_positive_change_is_limited_by_turn_delta_and_daily_cap():
    now = datetime(2026, 1, 1, 12, 0, 0)

    transition = favorability.apply_favorability_change_detailed(
        old_score=0,
        old_raw=0,
        requested_change=120,
        reason="日常互动",
        now=now,
        daily_gain_used=60,
        daily_loss_used=0,
        daily_bypass_used=0,
        daily_gain_bank=0,
        daily_cap=70,
        cap_reset_at=now,
        apology_counts={},
    )

    assert transition.requested_change_raw == favorability.MAX_DELTA_PER_TURN_RAW
    assert transition.applied_change_raw == 10
    assert transition.daily_gain_used_after == 70
    assert "delta_capped_positive" in transition.notes
    assert "daily_cap_limited" in transition.notes


def test_apology_gain_diminishes_after_repeated_same_apology():
    now = datetime(2026, 1, 1, 12, 0, 0)
    kwargs = {
        "old_score": 0,
        "old_raw": 0,
        "requested_change": 40,
        "reason": "认真道歉",
        "now": now,
        "daily_gain_used": 0,
        "daily_loss_used": 0,
        "daily_bypass_used": 0,
        "daily_gain_bank": 0,
        "daily_cap": 999,
        "cap_reset_at": now,
    }

    first = favorability.apply_favorability_change_detailed(**kwargs, apology_counts={})
    second = favorability.apply_favorability_change_detailed(**kwargs, apology_counts=first.apology_counts_after)
    third = favorability.apply_favorability_change_detailed(**kwargs, apology_counts=second.apology_counts_after)

    assert first.applied_change_raw == 40
    assert second.applied_change_raw == 20
    assert third.applied_change_raw == 0
    assert "apology_first" in first.notes
    assert "apology_second_half" in second.notes
    assert "apology_exhausted" in third.notes


def test_bypass_gain_uses_bypass_bucket_and_banks_overflow():
    now = datetime(2026, 1, 1, 12, 0, 0)

    transition = favorability.apply_favorability_change_detailed(
        old_score=0,
        old_raw=0,
        requested_change=50,
        reason="生日活动奖励 #bypass",
        now=now,
        daily_gain_used=0,
        daily_loss_used=0,
        daily_bypass_used=90,
        daily_gain_bank=0,
        daily_cap=70,
        cap_reset_at=now,
        apology_counts={},
    )

    assert transition.applied_change_raw == 10
    assert transition.daily_bypass_used_after == favorability.DEFAULT_DAILY_BYPASS_LIMIT
    assert transition.daily_gain_bank_after == 40
    assert {"bypass_gain", "bypass_overflow", "banked_gain"}.issubset(transition.notes)


def test_penalty_cooldown_can_suppress_repeated_penalty():
    now = datetime(2026, 1, 1, 12, 0, 0)

    transition = favorability.apply_favorability_change_detailed(
        old_score=50,
        old_raw=500,
        requested_change=-50,
        reason="重复惩罚",
        now=now,
        daily_gain_used=0,
        daily_loss_used=0,
        daily_bypass_used=0,
        daily_gain_bank=0,
        daily_cap=999,
        cap_reset_at=now,
        apology_counts={},
        last_penalty_at=now,
    )

    assert transition.applied_change_raw == 0
    assert transition.daily_loss_used_after == 0
    assert "penalty_cooldown_step(0/6)" in transition.notes


def test_bank_absorbs_and_amplifies_part_of_negative_change():
    now = datetime(2026, 1, 1, 12, 0, 0)

    transition = favorability.apply_favorability_change_detailed(
        old_score=0,
        old_raw=0,
        requested_change=-50,
        reason="糟糕互动",
        now=now,
        daily_gain_used=0,
        daily_loss_used=0,
        daily_bypass_used=0,
        daily_gain_bank=100,
        daily_cap=999,
        cap_reset_at=now,
        apology_counts={},
    )

    assert transition.applied_change_raw == -58
    assert transition.daily_gain_bank_after == 62.5
    assert "bank_penalty" in transition.notes


def test_daily_counters_reset_on_new_day():
    now = datetime(2026, 1, 2, 12, 0, 0)

    transition = favorability.apply_favorability_change_detailed(
        old_score=0,
        old_raw=0,
        requested_change=0,
        reason="",
        now=now,
        daily_gain_used=10,
        daily_loss_used=20,
        daily_bypass_used=30,
        daily_gain_bank=40,
        daily_cap=12,
        cap_reset_at=now - timedelta(days=1),
        apology_counts={},
    )

    assert transition.daily_gain_used_after == 0
    assert transition.daily_loss_used_after == 0
    assert transition.daily_bypass_used_after == 0
    assert transition.daily_cap_after == favorability.DEFAULT_DAILY_CAP
    assert transition.cap_reset_at_after == now
    assert "daily_reset" in transition.notes
