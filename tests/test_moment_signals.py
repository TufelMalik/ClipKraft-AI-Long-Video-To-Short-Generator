from moment_signals import annotate_windows, broll_suggestions, complete_thought_end, ranked_score, text_signals


def test_transcript_signals_describe_observed_content():
    features = text_signals('I was wrong. Last year I lost 50%. Why? [laughter]')
    assert features['confession'] and features['story'] and features['specific_claim']
    assert features['question'] and features['reaction']


def test_audio_peaks_are_attached_to_the_correct_window():
    windows = [{'id':'a','start':0.,'end':1.,'text':'Hello'},
               {'id':'b','start':1.,'end':2.,'text':'A story'}]
    result = annotate_windows(windows,[.1,.1,1.,.2],window_seconds=.5)
    assert result[0]['signals']['audio_peak']==.1
    assert result[1]['signals']['audio_peak']==1.
    assert 'signals' not in windows[0]


def test_weak_model_judgment_is_not_rescued_by_loudness():
    score = ranked_score(10,{'editorial_signal_score':100,'audio_contrast':1})
    assert score <= 18


def test_optimizer_does_not_cut_off_the_payoff_for_an_arbitrary_length():
    words = [{'w':'sentence.','s':45,'e':46},{'w':'payoff.','s':58,'e':59}]
    assert complete_thought_end(0,59.8,words)==59.15
    assert complete_thought_end(0,59.8,words[:1])==59.8


def test_broll_suggestions_are_bounded_and_spaced():
    transcript = {'segments':[{'words':[{'word':' 100','start':1,'end':1.2},
        {'word':' 200','start':2,'end':2.2},{'word':' 300','start':9,'end':9.2}]}]}
    points = broll_suggestions(transcript,10)
    assert points==[{'start':1.,'end':3.5,'label':'Illustrate: 100'}]
