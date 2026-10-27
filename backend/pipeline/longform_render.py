"""Cancellable source-aspect renders; previews and exports share exactly one path."""
import asyncio
import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from edit_project import EditError, digest
from ffmpeg_utils import video_encode_args, audio_encode_args, QUALITY_FAST, METADATA_SCRUB
from timeline_map import timeline, remap_transcript


async def command(args, timeout=1800, workdir=None, max_bytes=None, stderr_output=False):
    # ASR and FFmpeg children inherit no application, storage or Google credentials.
    env = dict(os.environ)
    for name in list(env):
        if any(part in name for part in ('TOKEN', 'SECRET', 'PASSWORD', 'CREDENTIAL', 'API_KEY', 'ACCESS_KEY')):
            env.pop(name, None)
    process = await asyncio.create_subprocess_exec(*map(str, args), stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.PIPE, env=env)
    reader = asyncio.create_task(process.communicate())
    async def monitor():
        while True:
            if workdir is not None:
                size = sum(p.stat().st_size for p in Path(workdir).rglob('*') if p.is_file())
                if size > max_bytes or shutil.disk_usage(workdir).free < 16 * 1024 * 1024:
                    raise EditError('storage_limit')
            await asyncio.sleep(.5)
    watcher = asyncio.create_task(monitor())
    try:
        done, _ = await asyncio.wait((reader, watcher), timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        if not done:
            raise EditError('media_operation_timeout')
        if watcher in done:
            await watcher
        stdout, stderr = await reader
        if process.returncode:
            raise EditError('media_operation_failed')
        return stderr if stderr_output else stdout
    finally:
        watcher.cancel()
        if process.returncode is None:
            process.kill()
            await process.wait()
        await asyncio.gather(reader, watcher, return_exceptions=True)


async def probe(path):
    raw = await command(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_format', '-show_streams', '-of', 'json', path], 30)
    data = json.loads(raw)
    if not any(s['codec_type'] == 'video' for s in data['streams']):
        raise EditError('video_required')
    return data


def fingerprint(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


async def render(project, source, transcript, directory, export_id, asset_store=None):
    import composition
    composition.validate(project)
    composed = composition.active(project)
    mix_audio = composition.audio_active(project)
    dependencies = []
    if 'composition' in project:
        if any(x['enabled'] and x['kind'] != 'broll' for x in project['composition']['visual_layers']):
            from visual_templates import dependencies as template_dependencies
            if project['composition']['visual_signature'] != digest(template_dependencies()):
                raise EditError('visual_environment_changed_preview_and_approve_again')
        from edit_assets import dependencies as asset_dependencies
        if any(x['enabled'] and x['needs_review'] for x in composition.layers(project)):
            raise EditError('unresolved_layers_disable_or_reanchor')
        if asset_store:
            dependencies = await asyncio.to_thread(asset_dependencies, asset_store, project)
    started = time.monotonic()
    directory = Path(directory)
    work = directory / ('temp_longform_' + export_id)
    work.mkdir(parents=True)
    target = directory / ('longform_' + export_id + '.mp4')
    entries = timeline(project['segments'])
    try:
        size = os.path.getsize(source)
        cap = int(os.getenv('LONGFORM_MAX_SOURCE_MB', '4096')) * 1024 * 1024
        disk_cap = int(os.getenv('LONGFORM_MAX_TEMP_MB', '8192')) * 1024 * 1024
        if size > cap or shutil.disk_usage(directory).free < min(size * 3, disk_cap):
            raise EditError('storage_limit')
        deadline = int(os.getenv('LONGFORM_RENDER_TIMEOUT_SECONDS', '1800'))
        parts = []
        for i, seg in enumerate(project['segments']):
            part = work / (f'part_{i}.mkv' if mix_audio else f'part_{i}.mp4')
            await command(['ffmpeg', '-v', 'error', '-y', '-ss', str(seg['source_start_ms'] / 1000),
                '-protocol_whitelist', 'file,pipe', '-i', source, '-t', str((seg['source_end_ms'] - seg['source_start_ms']) / 1000),
                '-map', '0:v:0', '-map', '0:a:0?', *video_encode_args(QUALITY_FAST), '-pix_fmt', 'yuv420p',
                *(['-c:a', 'pcm_s16le'] if mix_audio else audio_encode_args()), *METADATA_SCRUB,
                *([] if mix_audio else ['-movflags', '+faststart']), part],
                max(1, deadline - (time.monotonic() - started)), work, disk_cap)
            parts.append(part)
            if sum(p.stat().st_size for p in parts) > disk_cap:
                raise EditError('storage_limit')
        listing = work / 'concat.txt'
        listing.write_text(''.join(f"file '{p.name}'\n" for p in parts), encoding='utf-8')
        output = work / ('joined.mkv' if mix_audio else 'joined.mp4')
        await command(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', listing,
            '-c', 'copy', *METADATA_SCRUB, *([] if mix_audio else ['-movflags', '+faststart']), output],
            max(1, deadline - (time.monotonic() - started)), work, disk_cap)
        measured = None
        if composed:
            from longform_compositor import compose
            final = work / 'composed.mp4'
            measured = await compose(project, output, final, work, asset_store, command, probe,
                lambda: max(1, deadline - (time.monotonic() - started)), disk_cap)
            output = final
        info = await probe(output)
        actual = round(float(info['format']['duration']) * 1000)
        expected = entries[-1]['output_end_ms']
        if abs(actual - expected) > 250:
            raise EditError('render_duration_mismatch')
        # Optional captions are a separate selectable browser track, preserving clean video.
        from subtitles import generate_srt
        mapped = remap_transcript(transcript, entries)
        subtitle = work / 'captions.srt'
        generate_srt(mapped, 0, expected / 1000, str(subtitle))
        if not subtitle.exists():
            subtitle.write_text('', encoding='utf-8')
        srt_target = target.with_suffix('.srt')
        await asyncio.to_thread(os.replace, subtitle, srt_target)
        checksum = await asyncio.to_thread(fingerprint, output)
        os.replace(output, target)
        return {'export_id': export_id, 'project_id': project['project_id'], 'revision': project['revision'],
                'duration_ms': expected, 'media_duration_ms': actual, 'edl_hash': digest(project['segments']),
                'time_map': entries, 'fingerprint': checksum, 'filename': target.name,
                'captions_filename': srt_target.name, 'created_at': time.time(),
                **({'composition_hash': composition.identity(project, dependencies), 'dependencies': dependencies,
                    'template_dependencies': __import__('visual_templates').dependencies() if any(x['enabled'] and x['kind'] not in ('music', 'sfx', 'broll') for x in composition.layers(project)) else [],
                    'renderer_version': composition.RENDERER_VERSION, 'audio_measurement': measured} if 'composition' in project else {})}
    except BaseException:
        target.unlink(missing_ok=True)
        target.with_suffix('.srt').unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)
