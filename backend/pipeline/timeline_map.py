"""Integer, half-open occurrence maps shared by previews, exports and analytics."""
from bisect import bisect_left


def timeline(segments):
    result, offset = [], 0
    for s in segments:
        length = s['source_end_ms'] - s['source_start_ms']
        result.append({**s, 'output_start_ms': offset, 'output_end_ms': offset + length})
        offset += length
    return result


def map_interval(entries, start, end, direction='output'):
    other = 'source' if direction == 'output' else 'output'
    result = []
    for e in entries:
        a, b = max(start, e[f'{direction}_start_ms']), min(end, e[f'{direction}_end_ms'])
        if a < b:
            delta = e[f'{other}_start_ms'] - e[f'{direction}_start_ms']
            result.append({'segment_id': e['id'], 'start_ms': a + delta, 'end_ms': b + delta})
    return result


def remap_transcript(transcript, entries):
    words = sorted((w for s in transcript.get('segments', []) for w in s.get('words', [])
                    if w.get('end', 0) > w.get('start', 0)), key=lambda w: w['start'])
    starts = [round(w['start'] * 1000) for w in words]
    out = []
    for e in entries:
        a, b = e['source_start_ms'], e['source_end_ms']
        offset = e['output_start_ms'] - a
        selected = []
        # Include a word crossing the left boundary, never duplicate at a join.
        i = max(0, bisect_left(starts, a) - 1)
        while i < len(words) and starts[i] < b:
            w = words[i]
            end = round(w['end'] * 1000)
            if end > a:
                selected.append({**w, 'word': ' ' + w.get('word', '').strip(),
                                 'word_id': w.get('id', f'w{i}'), 'segment_id': e['id'],
                                 'source_start_ms': starts[i], 'source_end_ms': end,
                                 'start': (max(a, starts[i]) + offset) / 1000,
                                 'end': (min(b, end) + offset) / 1000})
            i += 1
        out.append({'start': e['output_start_ms'] / 1000, 'end': e['output_end_ms'] / 1000,
                    'text': ''.join(w['word'] for w in selected).strip(), 'words': selected})
    return {'language': transcript.get('language', 'en'), 'segments': out}


def remap_ranges(ranges, entries):
    return [{**r, **m} for r in ranges for m in map_interval(
        entries, r['start_ms'], r['end_ms'], 'source')]
