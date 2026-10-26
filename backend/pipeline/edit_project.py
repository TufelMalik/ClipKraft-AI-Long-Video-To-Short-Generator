"""Long-form EDL validation and deterministic, occurrence-scoped edits.

Independent of recut's deliberately unchanged shorts policy.
"""
import copy
import hashlib
import json
import os
import uuid


class EditError(ValueError):
    pass


def flag(name):
    return os.getenv(name, 'false').lower() in ('1', 'true', 'yes')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def uid():
    return uuid.uuid4().hex


def validate(project):
    segments = project.get('segments')
    if not isinstance(segments, list) or not 0 < len(segments) <= int(os.getenv('LONGFORM_MAX_SEGMENTS', '256')):
        raise EditError('invalid_segments')
    duration = project['source']['duration_ms']
    seen, total = set(), 0
    for s in segments:
        if not isinstance(s, dict):
            raise EditError('invalid_segments')
        a, b = s.get('source_start_ms'), s.get('source_end_ms')
        if type(a) is not int or type(b) is not int or not 0 <= a < b <= duration or b - a < 100:
            raise EditError('invalid_media_bounds')
        if not isinstance(s.get('id'), str) or not 0 < len(s['id']) <= 100 or s['id'] in seen:
            raise EditError('invalid_segment_id')
        seen.add(s['id'])
        if s.get('role') not in ('body', 'cold_open'):
            raise EditError('invalid_role')
        total += b - a
    if sum(s['role'] == 'cold_open' for s in segments) > 1 or any(
            s['role'] == 'cold_open' for s in segments[1:]):
        raise EditError('invalid_cold_open')
    if total > int(os.getenv('LONGFORM_MAX_DURATION_SECONDS', '7200')) * 1000:
        raise EditError('duration_limit')
    ranges = project.get('protected_ranges', [])
    if not isinstance(ranges, list) or len(ranges) > 1024:
        raise EditError('invalid_protected_range')
    for r in ranges:
        if not isinstance(r, dict):
            raise EditError('invalid_protected_range')
        if type(r.get('start_ms')) is not int or type(r.get('end_ms')) is not int or not 0 <= r['start_ms'] < r['end_ms'] <= duration:
            raise EditError('invalid_protected_range')
    project['duration_ms'] = total
    from composition import validate as validate_composition
    return validate_composition(project)


def new_project(job_id, duration_ms, fingerprint, transcript):
    return validate({'schema_version': 1, 'project_id': uid(), 'job_id': job_id, 'revision': 0,
        'source': {'duration_ms': duration_ms, 'fingerprint': fingerprint},
        'transcript_version': digest(transcript), 'output': {'aspect_ratio': 'source', 'playback_rate': 1},
        'segments': [{'id': uid(), 'source_start_ms': 0, 'source_end_ms': duration_ms, 'role': 'body'}],
        'protected_ranges': [], 'applied_suggestion_ids': []})


def protected(project, a, b):
    return any(a < r['end_ms'] and b > r['start_ms'] for r in project['protected_ranges'])


def apply_suggestions(project, suggestions, kind):
    p = copy.deepcopy(project)
    for s in suggestions:
        if s['revision'] != p['revision'] or s['transcript_version'] != p['transcript_version']:
            raise EditError('analysis_stale')
    if kind == 'cold_open':
        if len(suggestions) != 1:
            raise EditError('choose_one_opening')
        s = suggestions[0]
        p['segments'] = [{'id': uid(), 'role': 'cold_open', 'source_start_ms': s['start_ms'],
                          'source_end_ms': s['end_ms']}] + [s for s in p['segments'] if s['role'] == 'body']
    else:
        cuts = {}
        for s in suggestions:
            a, b = s['start_ms'], s['end_ms']
            evidence = s.get('retained_range')
            if evidence and any(x['segment_id'] == s['segment_id'] and
                    x['start_ms'] < evidence['end_ms'] and x['end_ms'] > evidence['start_ms'] for x in suggestions):
                raise EditError('retained_evidence_removed')
            if protected(p, a, b) or any(x['role'] == 'cold_open' and a < x['source_end_ms'] and b > x['source_start_ms'] for x in p['segments']):
                raise EditError('protected_range')
            occurrence = next((x for x in p['segments'] if x['id'] == s['segment_id'] and x['role'] == 'body'), None)
            if not occurrence or not occurrence['source_start_ms'] <= a < b <= occurrence['source_end_ms']:
                raise EditError('analysis_stale')
            cuts.setdefault(s['segment_id'], []).append((a, b))
        result = []
        for seg in p['segments']:
            cursor, end = seg['source_start_ms'], seg['source_end_ms']
            for a, b in sorted(cuts.get(seg['id'], [])):
                if a > cursor:
                    result.append({**seg, 'id': uid(), 'lineage': [*seg.get('lineage', []), seg['id']], 'source_start_ms': cursor, 'source_end_ms': a})
                cursor = max(cursor, b)
            if cursor < end:
                result.append({**seg, **({'lineage': [*seg.get('lineage', []), seg['id']]} if seg['id'] in cuts else {}), 'id': uid() if seg['id'] in cuts else seg['id'], 'source_start_ms': cursor})
        p['segments'] = result
    p['applied_suggestion_ids'] += [s['id'] for s in suggestions]
    from composition import reconcile
    return validate(reconcile(project, p))


def sentences(transcript):
    """Only punctuation-terminated units can be proposed for AI edits."""
    result, pending = [], []
    for seg in transcript.get('segments', []):
        for w in seg.get('words', []):
            if w.get('end', 0) <= w.get('start', 0):
                continue
            pending.append(w)
            if w.get('word', '').rstrip().endswith(('.', '?', '!', '।', '؟')):
                result.append({'id': f's{len(result)}', 'start_ms': round(pending[0]['start'] * 1000),
                               'end_ms': round(w['end'] * 1000),
                               'text': ''.join(' ' + x.get('word', '').strip() for x in pending).strip()})
                pending = []
    return result
