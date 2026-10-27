"""Optional compositor, called only for enabled composition content."""
import asyncio
from pathlib import Path
import audio_mix
import edit_assets
from composition import layers, resolve, audio_active
from ffmpeg_utils import METADATA_SCRUB, video_encode_args, QUALITY_FAST
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
    mix_audio = audio_active(project)
    filters = audio_mix.graph(project, has_voice, assets) if mix_audio else []
    visuals = [v for v in project['composition']['visual_layers'] if v['enabled'] and v['kind'] != 'broll']
    brolls = [v for v in project['composition']['visual_layers'] if v['enabled'] and v['kind'] == 'broll']
    video_label = '0:v:0'
    if brolls:
        if not store:
            raise EditError('asset_store_required')
        import broll
        video = next(s for s in info['streams'] if s['codec_type'] == 'video')
        for i, layer in enumerate(brolls):
            asset = store.get('asset', layer['asset_id'])
            args += await broll.input_args(layer, asset, edit_assets.path(store, asset), work, i,
                video['width'], video['height'], command, timeout, disk_cap)
            index = 1 + len(tracks) + i
            filters += broll.graph(project, layer, index, video_label, i, video['width'], video['height'])
            video_label = f'broll{i}'
    if visuals:
        from visual_templates import raster
        video = next(s for s in info['streams'] if s['codec_type'] == 'video')
        for i, layer in enumerate(visuals):
            picture = work / f'visual_{i}.png'
            await asyncio.to_thread(raster, layer, video['width'], video['height'], picture)
            index = 1 + len(tracks) + len(brolls) + i
            args += ['-loop', '1', '-framerate', '30', '-i', picture]
            start, end = resolve(project, layer['anchor'])
            fade = layer['transition_ms'] / 1000
            filters.append(f'[{index}:v]format=rgba' + (f',fade=t=in:st=0:d={fade}:alpha=1,fade=t=out:st={(end-start)/1000-fade}:d={fade}:alpha=1' if fade else '') + f',setpts=PTS-STARTPTS+{start/1000}/TB[pic{i}]')
            filters.append(f'[{video_label}][pic{i}]overlay=eof_action=pass:enable=\'gte(t,{start/1000})*lt(t,{end/1000})\'[visual{i}]')
            video_label = f'visual{i}'
    video_args = ['-map', f'[{video_label}]', *video_encode_args(QUALITY_FAST), '-pix_fmt', 'yuv420p'] if visuals or brolls else ['-map', '0:v:0', '-c:v', 'copy']
    audio_args = ['-map', '[mix]', '-c:a', 'aac', '-flags:a', '+bitexact', '-threads:a', '1', '-b:a', '192k'] if mix_audio else ['-map', '0:a:0?', '-c:a', 'copy']
    await command([*args, *(['-filter_complex', ';'.join(filters)] if filters else []), *video_args, *audio_args, '-t', str(project['duration_ms'] / 1000),
        *METADATA_SCRUB, '-movflags', '+faststart', output], timeout(), work, disk_cap)
    if not mix_audio:
        return None
    # Measure decoded AAC, rather than claiming pre-encode true peak is final.
    stderr = await command(['ffmpeg', '-hide_banner', '-i', output, '-vn', '-af',
        'loudnorm=I=-16:TP=-2:LRA=11:print_format=json', '-f', 'null', '-'], timeout(), work, disk_cap, stderr_output=True)
    measured = audio_mix.measurement(stderr)
    if float(measured['true_peak_dbtp']) > 0:
        raise EditError('encoded_audio_clipping_reduce_gain')
    return measured
