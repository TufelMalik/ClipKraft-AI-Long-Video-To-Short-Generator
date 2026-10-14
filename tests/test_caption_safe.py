from caption_safe import safe_alignment


def test_clear_bottom_keeps_default_caption_anchor():
    assert safe_alignment([[ (.3,.15,.6,.4) ]]) == 'bottom'


def test_face_in_bottom_band_moves_captions():
    assert safe_alignment([[ (.3,.7,.6,.95) ]]) != 'bottom'


def test_seam_is_kept_when_both_speakers_are_clear_of_it():
    assert safe_alignment([[ (.3,.12,.6,.25),(.3,.70,.6,.85) ]],'middle') == 'middle'
