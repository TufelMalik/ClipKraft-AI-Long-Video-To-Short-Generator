"""Optional compositor, called only for enabled composition content."""
import asyncio
from pathlib import Path
import audio_mix
import edit_assets
from composition import layers
from ffmpeg_utils import METADATA_SCRUB
from edit_project import EditError


async def compose(project, base, output, work, store, command, probe, timeout, disk_cap):
    info = await probe(base)
    has_voice = any(s['codec_type'] == 'audio' for s in info['streams'])
    tracks = [t for t in project['composition']['audio_tracks'] if t['enabled']]
    assets = {t['asset_id']: store.get('asset', t['asset_id']) for t in tracks} if store else {}
    if tracks and not store:
        raise EditError('asset_store_required')
    args = ['ffmpeg', '-v', 'error', '-y', '-filter_complex_threads', '1', '-protocol_whitelist', 'file,pipe', '-i', base]
    for t in tracks:
        args += ['-protocol_whitelist', 'file,pipe', '-i', edit_assets.path(store, assets[t['asset_id']])]
    filters = audio_mix.graph(project, has_voice, assets)
    await command([*args, '-filter_complex', ';'.join(filters), '-map', '0:v:0', '-map', '[mix]',
        '-c:v', 'copy', '-c:a', 'aac', '-flags:a', '+bitexact', '-threads:a', '1', '-b:a', '192k', '-t', str(project['duration_ms'] / 1000),
        *METADATA_SCRUB, '-movflags', '+faststart', output], timeout(), work, disk_cap)
    # Measure decoded AAC, rather than claiming pre-encode true peak is final.
    stderr = await command(['ffmpeg', '-hide_banner', '-i', output, '-vn', '-af',
        'loudnorm=I=-16:TP=-2:LRA=11:print_format=json', '-f', 'null', '-'], timeout(), work, disk_cap, stderr_output=True)
    measured = audio_mix.measurement(stderr)
    if float(measured['true_peak_dbtp']) > 0:
        raise EditError('encoded_audio_clipping_reduce_gain')
    return measured
