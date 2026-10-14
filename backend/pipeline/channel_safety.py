"""Optional self-host channel profiles and an atomic clip fingerprint ledger."""
import hashlib
import json
import math
import os
import sqlite3
import subprocess

NICHES = {'finance','tech','motivation'}


class SafetyError(ValueError):
    pass


def config_path():
    return os.environ.get('CHANNEL_PROFILES_PATH',os.path.join('.config','channels.json'))


def load_profiles(path=None):
    try:
        with open(path or config_path(),encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return {'channels':[]}
    return validate_profiles(data)


def validate_profiles(data):
    if not isinstance(data,dict) or not isinstance(data.get('channels'),list):
        raise SafetyError('Channel config needs a channels list')
    if len(data['channels']) > 20:
        raise SafetyError('At most 20 channels are supported')
    ids = set()
    for channel in data['channels']:
        if not isinstance(channel,dict):
            raise SafetyError('Every channel must be an object')
        key = channel.get('id')
        if not isinstance(key,str) or not key.strip() or len(key)>100 or key in ids:
            raise SafetyError('Channel IDs must be unique, non-empty strings')
        ids.add(key)
        if channel.get('niche') not in NICHES:
            raise SafetyError('Channel niche must be finance, tech, or motivation')
        creators = channel.get('creators',[])
        if not isinstance(creators,list) or len(creators)>500:
            raise SafetyError('creators must be a list of at most 500 entries')
        for creator in creators:
            if (not isinstance(creator,dict) or not isinstance(creator.get('id'),str)
                    or not creator['id'].strip()):
                raise SafetyError('Every creator needs an id')
    return data


def select_channel(profiles, channel_id, niche):
    channel = next((c for c in profiles['channels'] if c['id']==channel_id),None)
    if channel is None:
        raise SafetyError('Unknown channel; configure it before processing')
    if niche and channel['niche'] != niche:
        raise SafetyError('The clip niche does not match the selected channel')
    return channel


def fingerprint(path):
    """dHash frame sequence plus quantized audio spectrum, before branding.

    Matching is conservative: both modalities and duration must agree. A
    talking-head show's static background alone cannot flag another episode.
    """
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(path)
    count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or not count or not fps:
        cap.release()
        raise SafetyError('Cannot fingerprint an unreadable video')
    duration = count/fps
    hashes = []
    try:
        for fraction in np.linspace(.02,.98,12):
            cap.set(cv2.CAP_PROP_POS_FRAMES,int((count-1)*fraction))
            ok,frame = cap.read()
            if not ok:
                raise SafetyError('Cannot fingerprint all sampled video frames')
            gray = cv2.resize(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),(9,8))
            bits = gray[:,1:] > gray[:,:-1]
            hashes.append(int.from_bytes(np.packbits(bits).tobytes(),'big'))
    finally:
        cap.release()
    command = [os.environ.get('FFMPEG_BINARY','ffmpeg'),'-v','error','-i',path,
        '-vn','-ac','1','-ar','8000','-f','s16le','-']
    result = subprocess.run(command,capture_output=True,timeout=300)
    audio = []
    if result.returncode == 0 and result.stdout:
        samples = np.frombuffer(result.stdout,dtype='<i2').astype(float)
        for start in np.linspace(0,max(0,len(samples)-1024),32).astype(int):
            chunk = samples[start:start+1024]
            if len(chunk)<1024:
                chunk = np.pad(chunk,(0,1024-len(chunk)))
            spectrum = abs(np.fft.rfft(chunk*np.hanning(1024)))
            bands = np.array([np.mean(b) for b in np.array_split(spectrum[1:],16)])
            norm = float(np.linalg.norm(bands))
            audio.extend(np.round(bands/norm*100).astype(int).tolist() if norm>1 else [0]*16)
        if not any(audio):
            audio = []
    digest = hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            digest.update(block)
    return {'sha256':digest.hexdigest(),'duration':round(duration,3),
            'visual':[str(v) for v in hashes],'audio':audio}


def same_clip(a,b):
    if a['sha256']==b['sha256']:
        return True
    if abs(a['duration']-b['duration']) > max(.2,a['duration']*.01):
        return False
    va,vb = a['visual'],b['visual']
    if not va or len(va)!=len(vb):
        return False
    visual = sum((int(x)^int(y)).bit_count() for x,y in zip(va,vb))/(64*len(va))
    aa,ab = a['audio'],b['audio']
    if aa and ab and len(aa)==len(ab):
        norms = math.sqrt(sum(x*x for x in aa)*sum(x*x for x in ab))
        similarity = sum(x*y for x,y in zip(aa,ab))/norms if norms else 0.
        return visual <= .08 and similarity >= .985
    # Silent scenes require near-exact visual agreement.
    return not aa and not ab and visual <= .015


class Ledger:
    def __init__(self,path):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS clips (artifact TEXT PRIMARY KEY, '
                'channel TEXT NOT NULL, creator TEXT NOT NULL, created REAL NOT NULL, fingerprint TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path,timeout=30)

    def claim(self,artifact,channel,creator,signature,now=None,revision_of=None):
        """One transaction: concurrent channel exports cannot both claim a clip."""
        import time
        creator = creator or 'unknown'
        now = time.time() if now is None else now
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for key,other_channel,raw in db.execute('SELECT artifact,channel,fingerprint FROM clips'):
                own_revision = revision_of and (key==revision_of or key.startswith(revision_of+':'))
                if own_revision and other_channel != channel:
                    raise SafetyError('A clip revision cannot be reassigned to another channel')
                if key != artifact and not own_revision and same_clip(signature,json.loads(raw)):
                    raise SafetyError(f'Duplicate clip already assigned to channel {other_channel}')
            db.execute('INSERT OR REPLACE INTO clips VALUES (?,?,?,?,?)',
                (artifact,channel,creator,now,json.dumps(signature)))
            rows = list(db.execute('SELECT artifact,creator FROM clips WHERE channel=? AND created>=?',
                                   (channel,now-7*86400)))
        families = {':'.join(key.split(':')[:2]):c for key,c in rows}
        count = sum(c==creator for c in families.values())
        share = count/len(families) if families else 0
        return {'creator_share':round(share,3),'weekly_clips':len(families),
                'warning':f'{creator} supplies {share:.0%} of this channel\'s weekly clips; aim for 30% or less.' if share>.3 else None}


def ledger():
    return Ledger(os.environ.get('CLIP_LEDGER_PATH',os.path.join('.config','clip-ledger.sqlite3')))
