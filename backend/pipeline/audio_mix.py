"""Deterministic dialogue-driven soundtrack mix; no model or shared loudness defaults."""
import json
import re
from composition import resolve
from edit_project import EditError


def graph(project, has_voice, assets):
    c = project['composition']
    duration = project['duration_ms'] / 1000
    tracks = [t for t in c['audio_tracks'] if t['enabled']]
    if not has_voice and any(t['duck_under_voice'] for t in tracks):
        raise EditError('ducking_requires_source_audio_disable_ducking')
    filters, inputs = [], []
    voice = '[0:a:0]' if has_voice else f'anullsrc=r=48000:cl=stereo,atrim=duration={duration},'
    cleanup = 'afftdn=nr=8:nf=-45,' if c['voice']['cleanup'] == 'gentle' else ''
    filters.append(f'{voice}aresample=48000,aformat=channel_layouts=stereo,asetnsamples=n=1024:p=1,{cleanup}volume={c["voice"]["gain_db"]}dB,apad,atrim=duration={duration}[dialogue]')
    ducked = [t for t in tracks if t['duck_under_voice']]
    if ducked:
        filters.append('[dialogue]asplit=' + str(len(ducked) + 1) + '[voice]' + ''.join(f'[detector{i}]' for i in range(len(ducked))))
    else:
        filters.append('[dialogue]anull[voice]')
    detector = 0
    for i, t in enumerate(tracks):
        a, b = resolve(project, t['anchor'])
        length = (b - a) / 1000
        asset = assets[t['asset_id']]
        # Loop the selected tail, not the portion before the in-point.
        filters.append(f'[{i + 1}:a:0]aresample=48000,aformat=channel_layouts=stereo,atrim=start={t["asset_in_ms"] / 1000},asetpts=PTS-STARTPTS' +
            (f',aloop=loop=-1:size={round((asset["duration_ms"] - t["asset_in_ms"]) * 48)}' if t['loop'] else '') +
            f',atrim=duration={length},volume={t["gain_db"]}dB' +
            (f',afade=t=in:d={t["fade_in_ms"] / 1000}' if t['fade_in_ms'] else '') +
            (f',afade=t=out:st={length - t["fade_out_ms"] / 1000}:d={t["fade_out_ms"] / 1000}' if t['fade_out_ms'] else '') +
            f',adelay={a}|{a},apad,atrim=duration={duration},asetnsamples=n=1024:p=1[track{i}]')
        if t['duck_under_voice']:
            filters.append(f'[track{i}][detector{detector}]sidechaincompress=threshold=0.025:ratio=8:attack=20:release=350:makeup=1[duck{i}]')
            detector += 1
            inputs.append(f'[duck{i}]')
        else:
            inputs.append(f'[track{i}]')
    filters.append('[voice]' + ''.join(inputs) + f'amix=inputs={len(tracks) + 1}:duration=first:normalize=0:dropout_transition=0,' +
        f'asetnsamples=n=1024:p=1,loudnorm=I={c["loudness_lufs"]}:TP=-2:LRA=11,aresample=48000[mix]')
    return filters


def measurement(stderr):
    matches = re.findall(r'\{\s*"input_i".*?\}', stderr.decode(errors='replace'), re.S)
    if not matches:
        raise EditError('audio_measurement_failed')
    values = json.loads(matches[-1])
    return {'integrated_lufs': values['input_i'], 'true_peak_dbtp': values['input_tp'], 'loudness_range_lu': values['input_lra']}
