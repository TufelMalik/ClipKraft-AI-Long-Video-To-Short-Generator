"""Installed capabilities, cached per process; no optimistic frontend-only gates."""
import functools
import subprocess


@functools.lru_cache(maxsize=1)
def installed():
    try:
        result = subprocess.run(['ffmpeg', '-hide_banner', '-filters'], capture_output=True, timeout=10, text=True)
        filters = {line.split()[1] for line in result.stdout.splitlines() if len(line.split()) >= 3}
    except (OSError, subprocess.TimeoutExpired):
        filters = set()
    needed = {'afftdn', 'sidechaincompress', 'amix', 'afade', 'loudnorm', 'aloop'}
    from visual_templates import support
    return {'audio_supported': needed <= filters, 'audio_filters': sorted(needed & filters),
        'broll_supported': {'overlay', 'scale', 'crop', 'pad', 'tpad', 'fps'} <= filters,
        'visuals_supported': support() and 'overlay' in filters, 'text_shaping': 'harfbuzz-freetype' if support() else 'unavailable',
        'template_ids': ['key_point', 'comparison', 'process', 'callout'] if support() else []}
