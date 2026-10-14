"""Observable transcript/audio signals for clip ranking, not virality promises."""
import math
import re


def text_signals(text):
    text = str(text or '')
    lower = text.lower()
    signals = {
        'question':bool(re.search(r'[?？]',text)),
        'specific_claim':bool(re.search(r'\d+(?:[.,]\d+)?(?:%|\s*(?:million|billion|dollars|percent))?',text)),
        'story':bool(re.search(r'\b(?:i remember|when i was|one day|last year|i realized)\b',lower)),
        'confession':bool(re.search(r'\b(?:i was wrong|i failed|i admit|my biggest mistake)\b',lower)),
        'debate':bool(re.search(r'\b(?:disagree|wrong|everyone thinks|actually|unpopular)\b',lower)),
        'reaction':bool(re.search(r'\[(?:laugh(?:ter|s|ing)?|applause)\]|\b(?:hahaha|laughs)\b',lower)),
    }
    signals['editorial_signal_score'] = min(100,sum([15,20,15,20,15,15][i]
        for i,key in enumerate(list(signals)) if signals[key]))
    return signals


def annotate_windows(windows,envelope=None,window_seconds=.4):
    output = []
    envelope = envelope or []
    for window in windows:
        signals = text_signals(window['text'])
        if envelope:
            start = max(0,int(window['start']/window_seconds))
            end = min(len(envelope),max(start+1,int(math.ceil(window['end']/window_seconds))))
            values = envelope[start:end]
            if values:
                mean = sum(values)/len(values)
                signals['audio_peak'] = round(max(values),3)
                signals['audio_contrast'] = round(max(values)-mean,3)
        output.append({**window,'signals':signals})
    return output


def ranked_score(model_score,signals):
    score = float(model_score or 0)
    # The model's context judgment dominates; energy cannot rescue a poor idea.
    bonus = min(5.,float(signals.get('editorial_signal_score',0))*.04)
    bonus += min(3.,max(0,float(signals.get('audio_contrast',0)))*5)
    return round(min(100.,max(0.,score+bonus)),2)


def complete_thought_end(start,end,words,min_seconds=15.,max_shift=1.):
    """Tighten only the tail near the model's payoff, at sentence punctuation.

    Never truncate an arbitrary long thought just to reach a preferred length.
    Absence of punctuation keeps the model/word-boundary cut.
    """
    candidates = [float(w['e']) for w in words
        if start+min_seconds <= float(w['e']) <= end
        and end-float(w['e'])<=max_shift and re.search(r'[.!?。！？][\"\']?$',w['w'])]
    return min(end,max(candidates)+.15) if candidates else end


def broll_suggestions(transcript,duration):
    from recut import transcript_words
    points = []
    for word in transcript_words(transcript):
        if re.search(r'\d',word['w']) and word['s']+1.5<duration:
            if not points or word['s']-points[-1]['start']>=6:
                points.append({'start':round(word['s'],3),
                    'end':round(min(duration,word['s']+2.5),3),
                    'label':f"Illustrate: {word['w']}"})
        if len(points)>=6:
            break
    return points
