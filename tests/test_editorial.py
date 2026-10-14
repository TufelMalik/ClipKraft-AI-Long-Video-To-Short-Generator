import pytest

from editorial import normalize_config, shifted_transcript, silence_keeps


def test_pause_trimming_keeps_breaths_and_short_pauses():
    assert silence_keeps(10,[(2,4),(6,6.6)]) == [
        {'start':0.,'end':2.15},{'start':3.85,'end':10}]


def test_an_entirely_silent_clip_still_has_frames():
    ranges = silence_keeps(5,[(0,5)])
    assert sum(r['end']-r['start'] for r in ranges) > 0


def test_intro_offset_moves_every_caption_without_mutating_source():
    transcript = {'segments':[{'start':0,'end':2,'words':[{'word':' hi','start':.2,'end':.5}]}]}
    output = shifted_transcript(transcript,3)
    assert output['segments'][0]['words'][0]['start'] == 3.2
    assert transcript['segments'][0]['words'][0]['start'] == .2


@pytest.mark.parametrize('raw',[{'niche':'unknown'},{'trim_silence':'false'},
    {'broll_points':[float('nan')]},{'topic':'x'*161}])
def test_editorial_validation_rejects_invalid_settings(raw):
    with pytest.raises(ValueError):
        normalize_config(raw)


def test_user_json_cannot_choose_server_audio_paths():
    assert 'intro_audio' not in normalize_config({'intro_audio':'/etc/passwd'})
