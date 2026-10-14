from active_speaker import hold, reaction_cuts, segments
from speaker_registry import SpeakerRegistry


def test_tracks_keep_ids_when_detector_order_changes_and_face_moves():
    r = SpeakerRegistry()
    tracks = r.update([(100,100,80,80), (600,100,80,80)], 0)
    first = {t['box'][0]:t['id'] for t in tracks}
    moved = r.update([(610,100,80,80), (110,100,80,80)], 4)
    assert {t['box'][0]:t['id'] for t in moved} == {610:first[600], 110:first[100]}
    assert r.predict(first[100], 8)[0] == 120


def test_occlusion_has_bounded_hold():
    r = SpeakerRegistry(max_missing=10)
    t = r.update([(100,100,80,80)], 0)[0]
    assert r.predict(t['id'], 8) is not None
    assert r.predict(t['id'], 11) is None


def test_minimum_camera_hold_does_not_cut_back_immediately():
    held = hold([0,1,1,1,1,1,1,0,0,0,0,0,0], min_windows=2, min_hold_windows=6)
    switches = [i for i in range(1,len(held)) if held[i] != held[i-1]]
    assert switches == [6,12]


def test_reaction_cutaway_is_short_and_does_not_relabel_speech():
    held = [0]*80
    activity = [[.5,.5] for _ in held]
    activity[31] = [.4,3.]
    reaction = reaction_cuts(held,activity)
    assert reaction[31:34]==[1,1,1]
    assert reaction[34]==0 and held[31]==0
    assert segments(held)==[{'start':0.,'end':32.,'speaker':0}]
