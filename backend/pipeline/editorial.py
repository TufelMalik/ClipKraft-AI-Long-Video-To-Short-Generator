"""Editorial assembly: commentary, context, branding and tighter pacing.

Runs on the clean reframe BEFORE hooks/captions. The canonical reframe stays
intact for later trims. The returned transcript follows every removed pause
and added intro, so caption timing does not depend on a guessed time offset.
"""
import json
import math
import os
import re
import subprocess
import tempfile
import uuid

import layout_ranges
import recut
from ffmpeg_utils import METADATA_SCRUB, QUALITY_FAST, ffmpeg_input_args, video_encode_args

COLORS = {'finance':'#0d9488', 'tech':'#6366f1', 'motivation':'#ea580c'}


def normalize_config(raw):
    if not isinstance(raw, dict):
        raise ValueError('editorial must be an object')
    out = {}
    for key in ('speaker', 'topic', 'source', 'channel_name'):
        value = str(raw.get(key) or '').strip()
        if len(value) > 160:
            raise ValueError(f'{key} must be 160 characters or fewer')
        out[key] = value
    niche = raw.get('niche', 'tech')
    if niche not in COLORS:
        raise ValueError('niche must be finance, tech, or motivation')
    out['niche'] = niche
    for key in ('trim_silence', 'branding', 'color_grade', 'sound_design',
                'reaction_shots','zoom_punches','speaker_colors'):
        if not isinstance(raw.get(key, False), bool):
            raise ValueError(f'{key} must be true or false')
        out[key] = raw.get(key, False)
    preset = raw.get('caption_preset','default')
    if preset not in ('default','hormozi','neon','clean'):
        raise ValueError('caption_preset must be default, hormozi, neon, or clean')
    out['caption_preset'] = preset
    marks = raw.get('broll_points', [])
    if not isinstance(marks, list) or len(marks) > 24:
        raise ValueError('broll_points must contain at most 24 timestamps')
    out['broll_points'] = []
    for mark in marks:
        t = float(mark)
        if not math.isfinite(t) or t < 0:
            raise ValueError('B-roll timestamps must be finite non-negative seconds')
        out['broll_points'].append(round(t,3))
    return out


def enabled(config):
    return any(config.get(k) for k in ('speaker','topic','source','branding',
        'trim_silence','intro_audio','outro_audio','color_grade','sound_design'))


def binary():
    return os.environ.get('FFMPEG_BINARY', 'ffmpeg')


def run(args):
    result = subprocess.run([binary(), '-y', '-v', 'error', *ffmpeg_input_args(), *args],
                            capture_output=True, timeout=1800)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-600:])


def media_info(path):
    """FFmpeg parses the actual file, including audio-only uploaded commentary."""
    result = subprocess.run([binary(), '-hide_banner', '-i', path],
                            capture_output=True, timeout=30)
    text = result.stderr.decode(errors='replace')
    duration = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', text)
    if not duration:
        raise ValueError('Cannot read the media duration')
    h,m,s = map(float,duration.groups())
    dimensions = re.search(r'Video:.*?\b(\d{2,5})x(\d{2,5})\b',text)
    return {'duration':h*3600+m*60+s, 'audio':'Audio:' in text,
            'width':int(dimensions[1]) if dimensions else 0,
            'height':int(dimensions[2]) if dimensions else 0}


def silence_keeps(duration, silences, threshold=.8, retained=.15):
    """Keep a breath either side of a long pause; never remove every frame."""
    ranges, cursor = [], 0.0
    for start,end in sorted(silences):
        start,end = max(0.,start), min(duration,end)
        if end-start <= threshold:
            continue
        cut_start, cut_end = start+retained, end-retained
        if cut_start > cursor:
            ranges.append({'start':cursor,'end':cut_start})
        cursor = max(cursor,cut_end)
    if duration-cursor >= .05:
        ranges.append({'start':cursor,'end':duration})
    return ranges or [{'start':0.,'end':duration}]


def detect_silences(path, duration):
    result = subprocess.run([binary(), '-hide_banner', '-i',path,'-af',
        'silencedetect=noise=-35dB:d=0.8','-f','null','-'],
        capture_output=True, timeout=300)
    text = result.stderr.decode(errors='replace')
    pairs, start = [], None
    for kind,value in re.findall(r'silence_(start|end): ([\d.]+)',text):
        if kind == 'start':
            start = float(value)
        elif start is not None:
            pairs.append((start,float(value)))
            start = None
    if start is not None:
        pairs.append((start,duration))
    return pairs


def shifted_transcript(transcript, offset):
    result = json.loads(json.dumps(transcript))
    for segment in result.get('segments',[]):
        for item in [segment,*segment.get('words',[])]:
            for key in ('start','end'):
                if key in item:
                    item[key] = round(float(item[key])+offset,3)
    return result


def card_image(path, width, height, lines, color, full=False):
    from PIL import Image, ImageDraw, ImageFont
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    font_path = os.path.join(root,'fonts','Montserrat-ExtraBold.ttf')
    image = Image.new('RGBA',(width,height), (14,18,24,255 if full else 215))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0,0,max(6,width//100),height),fill=color)
    y = int(height*.15)
    for line in lines:
        if not line:
            continue
        size = max(18, min(width//22,height//(len(lines)+2)))
        font = ImageFont.truetype(font_path,size)
        while size > 12 and draw.textlength(line,font=font) > width*.86:
            size -= 1
            font = ImageFont.truetype(font_path,size)
        draw.text((int(width*.07),y),line,font=font,fill='white')
        y += size*1.6
    image.save(path)


def render_card(image, output, seconds, width, height, audio=None):
    args = ['-loop','1','-i',image]
    args += ['-i',audio] if audio else ['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
    args += ['-t',str(seconds),'-vf',f'scale={width}:{height},fps=30,format=yuv420p,fade=t=in:d=0.25,fade=t=out:st={max(0,seconds-.25)}:d=0.25',
        '-af','aresample=48000,loudnorm=I=-14:TP=-2:LRA=11',
        *video_encode_args(QUALITY_FAST),'-c:a','aac','-ar','48000','-ac','2',
        *METADATA_SCRUB,'-movflags','+faststart',output]
    run(args)


def assemble(path, config, transcript, clip_start, clip_end):
    """Return (clean editorial path, output transcript, duration, timeline)."""
    config = {**normalize_config(config),
              **{k:config[k] for k in ('intro_audio','outro_audio') if config.get(k)}}
    info = media_info(path)
    width,height = info['width'],info['height']
    if not width or not height:
        raise ValueError('Editorial input must contain video')
    directory = os.path.dirname(path)
    out = os.path.join(directory,f"edited_{uuid.uuid4().hex[:8]}_{os.path.basename(path)}")
    segments = [{'start':0.,'end':info['duration']}]
    if config['trim_silence'] and info['audio']:
        segments = silence_keeps(info['duration'],detect_silences(path,info['duration']))
    relative = recut.virtual_transcript(transcript,[{'start':clip_start,'end':clip_end}])
    relative = recut.virtual_transcript(relative,segments)
    body_duration = recut.total_duration(segments)
    import active_speaker
    speakers = active_speaker.read_segments(path)
    remapped_speakers = layout_ranges.remap([{'start':r['start'],'end':r['end'],'layout':str(r['speaker'])} for r in speakers],segments)
    with tempfile.TemporaryDirectory(prefix='editorial_',dir=directory) as work:
        cut = os.path.join(work,'cut.mp4')
        recut.run_cut_concat(path,segments,cut,work,
            runner=lambda command: run(command[1:]))
        parts = []
        offsets = {'intro':0.,'outro':0.}
        for kind in ('intro','outro'):
            audio = config.get(f'{kind}_audio')
            if audio:
                audio_info = media_info(audio)
                if not audio_info['audio'] or not .5 <= audio_info['duration'] <= 15:
                    raise ValueError('Commentary must contain audio and last 0.5–15 seconds')
                offsets[kind] = audio_info['duration']
            elif config['branding']:
                offsets[kind] = 2.5
            if offsets[kind]:
                image = os.path.join(work,f'{kind}.png')
                card_image(image,width,height,[config['channel_name'] or 'ClipKraft',
                    config['topic'] if kind == 'intro' else 'Follow for more'],
                    COLORS[config['niche']],full=True)
                output = os.path.join(work,f'{kind}.mp4')
                render_card(image,output,offsets[kind],width,height,audio)
                if kind == 'intro':
                    parts.append(output)
        body = os.path.join(work,'body.mp4')
        vf = 'fps=30,format=yuv420p'
        if width >= 1080 and height >= 1920:
            vf += ',unsharp=5:5:0.35:3:3:0'
        if config['color_grade']:
            vf += ',eq=contrast=1.04:saturation=1.04:brightness=0.005'
        inputs = ['-i',cut]
        filters, label = [], '0:v'
        lines = [config[k] for k in ('speaker','topic','source') if config[k]]
        if lines:
            card = os.path.join(work,'context.png')
            card_image(card,int(width*.9)//2*2,int(height*.12)//2*2,lines,COLORS[config['niche']])
            inputs += ['-i',card]
            from hook_placement import detect_faces, face_cost
            faces = detect_faces(cut,0.,min(4.,body_duration))
            y = min((.59,.61,.30,.12),key=lambda top:face_cost((.05,top,.95,top+.12),faces))
            filters.append(f'[0:v][1:v]overlay=(W-w)/2:H*{y}:enable=\'lt(t,4)\'[context]')
            label = 'context'
        filters.append(f'[{label}]{vf}[v]')
        if info['audio']:
            if config['sound_design']:
                filters.append("aevalsrc=exprs='0.08*sin(2*PI*75*t)*exp(-10*t)':d=0.5:s=48000[hit]")
                accents = ['[hit]']
                switch_times = [r['start'] for i,r in enumerate(remapped_speakers)
                                if i and r['layout']!=remapped_speakers[i-1]['layout']]
                for i,time in enumerate(switch_times[:40]):
                    label = f'switch{i}'
                    filters.append(f'anoisesrc=color=pink:sample_rate=48000:duration=0.18,volume=0.035,afade=t=out:st=0:d=0.18,adelay={int(time*1000)}:all=1[{label}]')
                    accents.append(f'[{label}]')
                filters.append(f"[0:a]{''.join(accents)}amix=inputs={len(accents)+1}:duration=first:normalize=0,aresample=48000,loudnorm=I=-14:TP=-2:LRA=11[a]")
            else:
                filters.append('[0:a]aresample=48000,loudnorm=I=-14:TP=-2:LRA=11[a]')
        else:
            inputs += ['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
            index = 2 if lines else 1
            filters.append(f'[{index}:a]atrim=duration={body_duration}[a]')
        run([*inputs,'-filter_complex',';'.join(filters),'-map','[v]','-map','[a]',
            '-t',str(body_duration),*video_encode_args(QUALITY_FAST),'-c:a','aac',
            '-ar','48000','-ac','2',*METADATA_SCRUB,body])
        parts.append(body)
        if offsets['outro']:
            parts.append(os.path.join(work,'outro.mp4'))
        listing = os.path.join(work,'concat.txt')
        with open(listing,'w',encoding='utf-8') as f:
            for part in parts:
                # Relative entries are resolved beside concat.txt, not from
                # the process cwd. Jobs normally use relative output paths.
                f.write("file '"+os.path.abspath(part).replace('\\','/').replace("'","'\\''")+"'\n")
        run(['-f','concat','-safe','0','-i',listing,'-c','copy',
            *METADATA_SCRUB,'-movflags','+faststart',out])
    ranges = layout_ranges.remap(layout_ranges.read(path),segments)
    layout_ranges.write(out,[(r['start']+offsets['intro'],r['end']+offsets['intro'],r['layout']) for r in ranges])
    with open(out+'.speakers.json','w',encoding='utf-8') as f:
        json.dump([{'start':r['start']+offsets['intro'],'end':r['end']+offsets['intro'],
                    'speaker':int(r['layout'])} for r in remapped_speakers],f)
    timeline = {'body_segments':segments,'intro_seconds':offsets['intro'],
                'outro_seconds':offsets['outro'],'broll_points':config['broll_points']}
    return out, shifted_transcript(relative,offsets['intro']), body_duration+sum(offsets.values()), timeline
