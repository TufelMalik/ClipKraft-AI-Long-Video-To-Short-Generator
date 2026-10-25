"""Reproducible synthetic export smoke check beyond shorts' 180-second ceiling.

Run: python scripts/verify_longform_media.py --output .cache/longform-media
This does not substitute for reviewed speech footage or production-capacity measurements.
"""
import argparse
import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend  # noqa: F401 -- registers lightweight module paths
from edit_project import new_project, apply_suggestions
from longform_render import command, render, probe, fingerprint


async def main(output):
    output.mkdir(parents=True, exist_ok=True)
    source = output / 'counter_source.mp4'
    # Visible frame number and time counter; portable standard FFmpeg filters.
    await command(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                   'testsrc2=size=320x180:rate=10:duration=190', '-f', 'lavfi', '-i',
                   'sine=frequency=440:sample_rate=48000:duration=190',
                   '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', source])
    transcript = {'language': 'en', 'segments': [{'words': [
        {'word': ' Start.', 'start': 0, 'end': 1},
        {'word': ' Middle.', 'start': 95, 'end': 96},
        {'word': ' Teaser.', 'start': 180, 'end': 182},
        {'word': ' End.', 'start': 189, 'end': 190}]}]}
    p = new_project('synthetic', 190000, fingerprint(source), transcript)
    s = {'id': 'teaser', 'revision': 0, 'transcript_version': p['transcript_version'],
         'start_ms': 180000, 'end_ms': 182000}
    p = apply_suggestions(p, [s], 'cold_open')
    started = time.monotonic()
    result = await render(p, source, transcript, output, 'long-duration')
    info = await probe(output / result['filename'])
    assert abs(float(info['format']['duration']) - 192) < .25
    assert result['time_map'][0]['source_start_ms'] == 180000
    # Full decode catches corrupt frames/audio beyond container metadata.
    await command(['ffmpeg', '-v', 'error', '-i', output / result['filename'], '-f', 'null', '-'])
    # Export representative stills and audio for visual/listening review.
    for label, at in [('opening', 1), ('body-start', 3), ('middle', 97), ('ending', 191)]:
        await command(['ffmpeg', '-v', 'error', '-y', '-ss', at, '-i', output / result['filename'],
                       '-frames:v', '1', output / (label + '.png')])
    await command(['ffmpeg', '-v', 'error', '-y', '-i', output / result['filename'],
                   '-t', '6', '-vn', '-c:a', 'pcm_s16le', output / 'join-audio.wav'])
    result['verification'] = {'synthetic': True, 'full_decode': 'passed',
        'elapsed_seconds': round(time.monotonic() - started, 2),
        'output_bytes': (output / result['filename']).stat().st_size,
        'remaining_free_bytes': shutil.disk_usage(output).free,
        'limitations': 'Test pattern and tone; no speech/editorial quality or peak resource claim.'}
    (output / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result['verification'], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('.cache/longform-media'))
    asyncio.run(main(parser.parse_args().output))
