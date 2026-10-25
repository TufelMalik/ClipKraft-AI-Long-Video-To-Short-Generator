"""Direct read-only Google OAuth and export-bound audience retention."""
import base64
import hashlib
import json
import math
import os
import re
import secrets
import time
from datetime import date
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from edit_project import EditError, uid
from timeline_map import map_interval

SCOPES = {'https://www.googleapis.com/auth/yt-analytics.readonly',
          'https://www.googleapis.com/auth/youtube.readonly'}


def cipher():
    from cryptography.fernet import Fernet
    try:
        return Fernet(os.environ['YOUTUBE_CREDENTIAL_KEY'].encode())
    except (KeyError, ValueError):
        raise EditError('youtube_configuration_required')


def configuration():
    redirect = os.getenv('YOUTUBE_REDIRECT_URI', '')
    p = urlparse(redirect)
    if p.hostname not in ('localhost', '127.0.0.1', '::1') or p.scheme != 'http' or p.path != '/api/youtube-analytics/callback' or p.query or p.fragment:
        raise EditError('youtube_configuration_required')
    if not os.getenv('YOUTUBE_CLIENT_ID') or not os.getenv('YOUTUBE_CLIENT_SECRET') or not os.getenv('LONGFORM_LOCAL_TOKEN'):
        raise EditError('youtube_configuration_required')
    cipher()
    return redirect


def connect(store):
    redirect = configuration()
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    store.put('oauth_state', hashlib.sha256(state.encode()).hexdigest(), {'expires': time.time() + 600,
        'verifier': cipher().encrypt(verifier.encode()).decode()})
    return {'url': 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
        'client_id': os.environ['YOUTUBE_CLIENT_ID'], 'redirect_uri': redirect, 'response_type': 'code',
        'scope': ' '.join(sorted(SCOPES)), 'state': state, 'code_challenge': challenge,
        'code_challenge_method': 'S256', 'access_type': 'offline', 'prompt': 'consent'})}


async def google(method, url, **kwargs):
    try:
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            r = await client.request(method, url, **kwargs)
    except httpx.HTTPError:
        raise EditError('youtube_unavailable')
    if r.status_code in (400, 401):
        raise EditError('reconnect_required')
    if r.status_code == 403:
        raise EditError('youtube_access_denied')
    if r.status_code == 429:
        raise EditError('youtube_rate_limited')
    if r.status_code != 200:
        raise EditError('youtube_unavailable')
    return r.json() if r.content else {}


async def callback(store, state, code):
    configuration()
    key = hashlib.sha256(state.encode()).hexdigest()
    # Consume atomically, including on a failed exchange.
    record = store.take('oauth_state', key)
    if record['expires'] < time.time():
        raise EditError('invalid_oauth_state')
    token = await google('POST', 'https://oauth2.googleapis.com/token', data={
        'client_id': os.environ['YOUTUBE_CLIENT_ID'], 'client_secret': os.environ['YOUTUBE_CLIENT_SECRET'],
        'redirect_uri': configuration(), 'grant_type': 'authorization_code', 'code': code,
        'code_verifier': cipher().decrypt(record['verifier'].encode()).decode()})
    if not SCOPES <= set(token.get('scope', '').split()) or not token.get('refresh_token'):
        raise EditError('insufficient_scopes')
    channels = await google('GET', 'https://www.googleapis.com/youtube/v3/channels',
        headers={'Authorization': 'Bearer ' + token['access_token']}, params={'part': 'id', 'mine': 'true'})
    ids = [c['id'] for c in channels.get('items', [])]
    if not ids:
        raise EditError('channel_required')
    token['expires_at'] = time.time() + token.get('expires_in', 3600) - 60
    for kind in ('report', 'publication'):
        store.clear(kind)  # a new connection cannot inherit another channel's cache
    store.put('connection', 'local', {'channels': ids, 'id': uid(), 'updated_at': time.time(),
        'encrypted': cipher().encrypt(json.dumps(token).encode()).decode()})


async def access(store):
    try:
        record = store.get('connection', 'local')
    except EditError:
        raise EditError('connection_required')
    token = json.loads(cipher().decrypt(record['encrypted'].encode()))
    if token['expires_at'] <= time.time():
        refreshed = await google('POST', 'https://oauth2.googleapis.com/token', data={
            'client_id': os.environ['YOUTUBE_CLIENT_ID'], 'client_secret': os.environ['YOUTUBE_CLIENT_SECRET'],
            'refresh_token': token['refresh_token'], 'grant_type': 'refresh_token'})
        token.update(refreshed)
        token['expires_at'] = time.time() + refreshed.get('expires_in', 3600) - 60
        record['encrypted'] = cipher().encrypt(json.dumps(token).encode()).decode()
        record['updated_at'] = time.time()
        store.put('connection', 'local', record)
    return record, {'Authorization': 'Bearer ' + token['access_token']}


def video_id(value):
    if re.fullmatch(r'[\w-]{11}', value, re.ASCII):
        return value
    p = urlparse(value)
    if p.scheme != 'https' or p.hostname not in ('www.youtube.com', 'youtube.com', 'youtu.be'):
        raise EditError('invalid_youtube_video')
    candidate = p.path.strip('/') if p.hostname == 'youtu.be' else parse_qs(p.query).get('v', [''])[0]
    if not re.fullmatch(r'[\w-]{11}', candidate, re.ASCII):
        raise EditError('invalid_youtube_video')
    return candidate


def duration_ms(value):
    m = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?', value)
    if not m:
        raise EditError('invalid_video_duration')
    return round(sum(float(v or 0) * scale for v, scale in zip(m.groups(), (3600000, 60000, 1000))))


async def publication(store, project, export, value, confirmed):
    if confirmed is not True or export['project_id'] != project['project_id'] or export.get('preview'):
        raise EditError('publication_confirmation_required')
    connection, headers = await access(store)
    id = video_id(value)
    data = await google('GET', 'https://www.googleapis.com/youtube/v3/videos', headers=headers,
        params={'part': 'snippet,contentDetails', 'id': id})
    items = data.get('items', [])
    if not items or items[0]['snippet']['channelId'] not in connection['channels']:
        raise EditError('publication_mismatch')
    duration = duration_ms(items[0]['contentDetails']['duration'])
    if abs(duration - export['duration_ms']) > 1500:
        raise EditError('publication_mismatch')
    link = {'id': uid(), 'connection_id': connection['id'], 'project_id': project['project_id'],
            'export_id': export['export_id'], 'revision': export['revision'], 'video_id': id,
            'duration_ms': duration, 'channel_id': items[0]['snippet']['channelId'],
            'mapping': 'user_confirmed', 'confirmed_at': time.time()}
    return store.put('publication', link['id'], link)


def normalize(raw, duration, entries):
    names = [h['name'] for h in raw.get('columnHeaders', [])]
    if not raw.get('rows'):
        return []
    if 'elapsedVideoTimeRatio' not in names or 'audienceWatchRatio' not in names:
        raise EditError('report_schema_changed')
    result, previous = [], 0
    for row in raw['rows']:
        data = dict(zip(names, row))
        ratio, watch = float(data['elapsedVideoTimeRatio']), float(data['audienceWatchRatio'])
        if not math.isfinite(ratio) or not math.isfinite(watch) or watch < 0 or not 0 < ratio <= 1:
            raise EditError('report_schema_changed')
        # Ratios are exclusive bucket ends; sparse reports retain the actual interval width.
        end = round(ratio * duration)
        start = round(max(0, ratio - .01) * duration)
        if end <= previous:
            raise EditError('report_schema_changed')
        relative = data.get('relativeRetentionPerformance')
        if relative is not None and (not math.isfinite(float(relative)) or not 0 <= float(relative) <= 1):
            raise EditError('report_schema_changed')
        result.append({'start_ms': start, 'end_ms': end, 'watch_ratio': watch,
            'relative_retention': relative, 'source_ranges': map_interval(entries, start, end)})
        previous = end
    return result


def observations(buckets, prominence=.15):
    result = []
    if len(buckets) < 5:
        return result
    for i in range(2, len(buckets) - 2):
        nearby = buckets[i - 2:i] + buckets[i + 1:i + 3]
        b = buckets[i]
        if any(abs(x['start_ms'] - b['start_ms']) > 3 * (b['end_ms'] - b['start_ms']) for x in nearby):
            continue
        baseline = sum(x['watch_ratio'] for x in nearby) / 4
        diff = b['watch_ratio'] - baseline
        if abs(diff) >= prominence:
            result.append({**b, 'kind': 'dip' if diff < 0 else 'peak', 'baseline': baseline,
                'note': 'Retention differs from nearby intervals; review this section. This does not establish a cause.'})
    return result


async def report(store, link, export, start, end):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if start > end or end > date.today():
        raise EditError('invalid_date_range')
    connection, headers = await access(store)
    if link['connection_id'] != connection['id']:
        raise EditError('reconnect_required')
    raw = await google('GET', 'https://youtubeanalytics.googleapis.com/v2/reports', headers=headers,
        params={'ids': 'channel==' + link['channel_id'], 'startDate': str(start), 'endDate': str(end),
                'dimensions': 'elapsedVideoTimeRatio', 'metrics': 'audienceWatchRatio,relativeRetentionPerformance',
                'filters': 'video==' + link['video_id'], 'sort': 'elapsedVideoTimeRatio'})
    buckets = normalize(raw, link['duration_ms'], export['time_map'])
    data = {'publication_id': link['id'], 'export_id': link['export_id'], 'revision': link['revision'],
            'start_date': str(start), 'end_date': str(end), 'fetched_at': time.time(), 'raw': raw,
            'duration_ms': link['duration_ms'], 'buckets': buckets, 'observations': observations(buckets),
            'state': 'ready' if buckets else 'report_pending',
            'definition': 'Watch ratio can exceed 100% due to repeated viewing. Bucket-level observations are heuristic.'}
    return store.put('report', link['id'], data)


async def disconnect(store):
    try:
        record = store.get('connection', 'local')
        token = json.loads(cipher().decrypt(record['encrypted'].encode()))
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.post('https://oauth2.googleapis.com/revoke', data={'token': token['refresh_token']})
            if response.status_code not in (200, 400):
                raise EditError('revoke_failed_retry')
    except EditError as e:
        if str(e) != 'not_found':
            raise
    finally:
        # Delete local credentials/cache even if remote revocation fails.
        for kind in ('connection', 'report', 'publication', 'oauth_state'):
            store.clear(kind)
