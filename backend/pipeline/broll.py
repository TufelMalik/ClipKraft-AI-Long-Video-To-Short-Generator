"""Video-only placement; all inputs are resolved immutable library assets."""

from composition import resolve
from ffmpeg_utils import video_encode_args, QUALITY_FAST


def geometry(layer, width, height):
    if layer['mode'] == 'cover':
        return width, height, 0, 0
    w, h = max(2, int(width * .4) // 2 * 2), max(2, int(height * .4) // 2 * 2)
    margin_x, margin_y = round(width * .04), round(height * .06)
    return w, h, margin_x if layer['position'] == 'upper_left' else width - w - margin_x, margin_y


def sizing(layer, width, height):
    w, h, _, _ = geometry(layer, width, height)
    # Normalize pixel shape before sizing so anamorphic assets are not distorted.
    normalize = 'scale=trunc(iw*sar/2)*2:ih,setsar=1,'
    if layer['fit'] == 'crop':
        return (normalize + f'scale={w}:{h}:force_original_aspect_ratio=increase:force_divisible_by=2,'
                f"crop={w}:{h}:(iw-ow)*{layer['crop_x']}:(ih-oh)*{layer['crop_y']},setsar=1")
    return (normalize + f'scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,'
            f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1')


async def input_args(layer, asset, file, work, number, width, height, command, timeout, disk_cap):
    if asset['type'] == 'image':
        return ['-loop', '1', '-framerate', '30', '-i', file]
    if not layer['loop']:
        return ['-ss', str(layer['asset_in_ms'] / 1000), '-protocol_whitelist', 'file,pipe', '-i', file]
    # Stream looping a normalized selected tail avoids unbounded decoded-frame
    # caches and prevents the in-point from resetting to the start of the asset.
    tail = work / f'broll_loop_{number}.mp4'
    await command(['ffmpeg', '-v', 'error', '-y', '-ss', str(layer['asset_in_ms'] / 1000),
        '-protocol_whitelist', 'file,pipe', '-i', file, '-an', '-vf', sizing(layer, width, height) + ',fps=30',
        *video_encode_args(QUALITY_FAST), '-pix_fmt', 'yuv420p', tail], timeout(), work, disk_cap)
    return ['-stream_loop', '-1', '-i', tail]


def graph(project, layer, index, label, number, width, height):
    start, end = resolve(project, layer['anchor'])
    duration = (end - start) / 1000
    w, h, x, y = geometry(layer, width, height)
    fit = sizing(layer, width, height)
    extend = f',tpad=stop_mode=clone:stop_duration={duration}' if layer['freeze'] else ''
    return [f'[{index}:v]setpts=PTS-STARTPTS,{fit},fps=30{extend},trim=duration={duration},'
            f'setpts=PTS-STARTPTS+{start/1000}/TB[br{number}]',
            f"[{label}][br{number}]overlay=x={x}:y={y}:eof_action=pass:enable='gte(t,{start/1000})*lt(t,{end/1000})'[broll{number}]"]
