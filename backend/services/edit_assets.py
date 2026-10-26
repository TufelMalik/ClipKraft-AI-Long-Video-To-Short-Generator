"""Private, immutable local media library sharing the existing SQLite store."""
import asyncio
import json
import time
from pathlib import Path

from edit_project import EditError, uid
from longform_render import command, fingerprint
from composition import layers, resolve

EXTENSIONS = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.mp4', '.mov', '.webm', '.png', '.jpg', '.jpeg', '.webp'}
MAX_BYTES = 256 * 1024 * 1024
MAX_LIBRARY_BYTES = 2 * 1024 * 1024 * 1024


def public(record):
    return {k: v for k, v in record.items() if k not in ('filename', 'thumbnail')}


def path(store, record):
    value = store.root / 'assets' / record['filename']
    if not value.is_file():
        raise EditError('asset_missing:' + record['id'])
    return value


async def ingest(store, upload):
    extension = Path(upload.filename or '').suffix.lower()
    if extension not in EXTENSIONS:
        raise EditError('unsupported_asset_format')
    directory = store.root / 'assets'
    directory.mkdir(exist_ok=True)
    id = uid()
    target = directory / (id + extension)
    thumbnail = directory / (id + '.thumb.png')
    size = 0
    # Shared host admission bounds upload/probe/decode and total library storage.
    with store.slot('longform-work', 300):
        used = sum(p.stat().st_size for p in directory.iterdir() if p.is_file())
        try:
            with target.open('wb') as out:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES or used + size > MAX_LIBRARY_BYTES:
                        raise EditError('asset_storage_limit')
                    await asyncio.to_thread(out.write, chunk)
            info = json.loads(await command(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                '-show_format', '-show_streams', '-of', 'json', target], 30))
            streams = info.get('streams', [])
            video = next((s for s in streams if s['codec_type'] == 'video'), None)
            audio = next((s for s in streams if s['codec_type'] == 'audio'), None)
            image = extension in ('.png', '.jpg', '.jpeg', '.webp')
            if image:
                from PIL import Image
                with Image.open(target) as im:
                    if im.format not in ('PNG', 'JPEG', 'WEBP') or im.width * im.height > 16000000:
                        raise EditError('invalid_image')
                    im.verify()
                with Image.open(target) as im:
                    im.thumbnail((320, 320))
                    im.convert('RGB').save(thumbnail)
            elif not audio and not video:
                raise EditError('invalid_asset_media')
            duration = 0 if image else round(float(info['format']['duration']) * 1000)
            if not image and not 100 <= duration <= 7200000:
                raise EditError('asset_duration_limit')
            if video and (video.get('width', 0) * video.get('height', 0) > 16000000 or max(video.get('width', 0), video.get('height', 0)) > 7680):
                raise EditError('asset_dimensions_limit')
            allowed_codecs = {'h264', 'hevc', 'vp8', 'vp9', 'av1', 'aac', 'mp3', 'flac', 'vorbis', 'opus', 'pcm_s16le', 'pcm_s24le', 'pcm_f32le', 'alac', 'png', 'mjpeg', 'webp'}
            if any(s.get('codec_name') not in allowed_codecs for s in streams if s['codec_type'] in ('audio', 'video')):
                raise EditError('unsupported_asset_codec')
            if video and not image:
                await command(['ffmpeg', '-v', 'error', '-y', '-protocol_whitelist', 'file,pipe', '-i', target,
                    '-frames:v', '1', '-vf', 'scale=320:320:force_original_aspect_ratio=decrease', thumbnail], 30)
            record = {'id': id, 'version': 1, 'metadata_version': 1, 'filename': target.name,
                'name': Path(upload.filename or '').name[:150], 'type': 'image' if image else 'video' if video else 'audio',
                'checksum': await asyncio.to_thread(fingerprint, target), 'duration_ms': duration,
                'width': video.get('width') if video else None, 'height': video.get('height') if video else None,
                'codec': (video or audio)['codec_name'], 'has_audio': bool(audio), 'bytes': size,
                'tags': [], 'description': '', 'language': '', 'source_label': '', 'usage_notes': '',
                'created_at': time.time(), 'thumbnail': thumbnail.name if thumbnail.exists() else None}
            return store.put('asset', id, record)
        except BaseException:
            target.unlink(missing_ok=True)
            thumbnail.unlink(missing_ok=True)
            raise


def metadata(store, id, body):
    with store.db() as db:
        row = db.execute("SELECT body FROM records WHERE kind='asset' AND id=?", (id,)).fetchone()
        if not row:
            raise EditError('not_found')
        record = json.loads(row[0])
        if body.get('expected_version') != record['metadata_version']:
            raise EditError('revision_conflict')
        if set(body) - {'expected_version', 'tags', 'description', 'language', 'source_label', 'usage_notes'}:
            raise EditError('invalid_asset_metadata')
        for key in ('description', 'language', 'source_label', 'usage_notes'):
            if key in body:
                if not isinstance(body[key], str) or len(body[key]) > 1000:
                    raise EditError('invalid_asset_metadata')
                record[key] = body[key]
        if 'tags' in body:
            if not isinstance(body['tags'], list) or len(body['tags']) > 32 or any(not isinstance(s, str) or len(s) > 80 for s in body['tags']):
                raise EditError('invalid_asset_metadata')
            record['tags'] = body['tags']
        record['metadata_version'] += 1
        store._put(db, 'asset', id, record)
    return record


def delete(store, id):
    # Serialize with project mutations; protect history and pending approvals too.
    with store.db() as db:
        for kind, raw in db.execute('SELECT kind,body FROM records').fetchall():
            if kind in ('project', 'history', 'composition_draft', 'export') and id in raw:
                raise EditError('asset_referenced_by_draft_history_or_export')
        row = db.execute("SELECT body FROM records WHERE kind='asset' AND id=?", (id,)).fetchone()
        if not row:
            raise EditError('not_found')
        record = json.loads(row[0])
        for filename in (record['filename'], record.get('thumbnail')):
            if filename:
                (store.root / 'assets' / filename).unlink(missing_ok=True)
        db.execute("DELETE FROM records WHERE kind='asset' AND id=?", (id,))


def dependencies(store, project, verify=True):
    result = {}
    for layer in layers(project):
        if not layer['enabled']:
            continue
        if layer['needs_review']:
            raise EditError('layer_needs_review:' + layer['id'])
        a, b = resolve(project, layer['anchor'])
        if 'asset_id' not in layer:
            continue
        asset = store.get('asset', layer['asset_id'])
        if asset['version'] != layer['asset_version']:
            raise EditError('asset_version_changed')
        file = path(store, asset)
        if verify and fingerprint(file) != asset['checksum']:
            raise EditError('asset_checksum_changed:' + asset['id'])
        if layer['kind'] in ('music', 'sfx') and asset['type'] != 'audio':
            raise EditError('audio_asset_required')
        if asset['type'] != 'image':
            remaining = asset['duration_ms'] - layer['asset_in_ms']
            if layer.get('loop') and remaining > 60000:
                raise EditError('loop_tail_limit_60_seconds')
            if remaining <= 0 or (not layer.get('loop') and remaining < b - a):
                raise EditError('asset_too_short_trim_or_loop:' + layer['id'])
        result[asset['id']] = {'id': asset['id'], 'version': asset['version'], 'checksum': asset['checksum']}
    return sorted(result.values(), key=lambda x: x['id'])
