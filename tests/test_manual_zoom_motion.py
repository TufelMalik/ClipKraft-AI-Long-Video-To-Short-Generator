"""Automatic motion should support the conversation without repeated breathing."""
import pytest

p = pytest.importorskip('manual_clip_pipeline')


def test_long_take_has_one_gentle_push_and_never_zooms_back_out():
    values = p.compute_dynamic_motion_zooms(45 * 24, 24)
    assert values[:36] == [1.0] * 36
    assert all(a <= b for a, b in zip(values, values[1:]))
    assert max(values) == pytest.approx(1.035)
    assert values[7 * 24:] == pytest.approx([1.035] * (38 * 24))


def test_short_conversational_turns_remain_still():
    assert p.compute_dynamic_motion_zooms(24 * 20, 24, [96, 192, 288, 384]) == [1.0] * 480


def test_a_cut_resets_at_once_without_a_pre_cut_zoom_out():
    values = p.compute_dynamic_motion_zooms(24 * 18, 24, [24 * 10])
    assert values[239] == pytest.approx(1.035)
    assert values[240:276] == [1.0] * 36
    assert all(a <= b for a, b in zip(values[240:], values[241:]))


def test_motion_is_timed_to_final_playback_speed():
    # 7 source seconds becomes 5.83 delivered seconds: too short for a push.
    values = p.compute_dynamic_motion_zooms(24 * 7, 24, playback_speed=1.2)
    assert values == [1.0] * len(values)
    values = p.compute_dynamic_motion_zooms(24 * 12, 24, playback_speed=1.2)
    assert values[:44] == [1.0] * 44
    assert values[45] > 1.0


def test_old_peak_override_cannot_restore_excessive_automatic_zoom():
    assert max(p.compute_dynamic_motion_zooms(600, 30, max_zoom=1.13)) <= 1.04


def test_zero_frames_and_disabled_motion():
    assert p.compute_dynamic_motion_zooms(0, 24) == []
    assert p.compute_dynamic_motion_zooms(300, 24, max_zoom=1) == [1.0] * 300


def test_frequent_speaker_cuts_do_not_make_zoom_pulses():
    values = p.compute_dynamic_motion_zooms(1104, 24,
        [156, 243, 272, 311, 387, 455, 485, 700, 748, 883, 1033], playback_speed=1.2)
    # This source has only one long enough uninterrupted turn for subtle motion.
    starts = [i for i in range(1, len(values)) if values[i] > 1 and values[i - 1] == 1]
    assert len(starts) == 1
    assert max(values) <= 1.035


def test_zoomed_crop_keeps_even_dimensions_and_stays_inside_source():
    zooms = p.compute_dynamic_motion_zooms(300, 24)
    boxes = p.compute_crop_boxes([0] * 150 + [1750] * 150, zooms, 810, 1440, 2560, 1440)
    for w, h, x, y in boxes:
        assert all(v % 2 == 0 for v in (w, h, x, y))
        assert 0 <= x <= 2560 - w and 0 <= y <= 1440 - h
