"""Fetch checksum-pinned OpenCV models and their licenses for anonymous IDs."""
import argparse
import hashlib
from pathlib import Path
import urllib.request

MODELS = {
    'face_recognition_sface':('face_recognition_sface_2021dec.onnx',
        '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79'),
}


def download(directory):
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    for model,(filename,digest) in MODELS.items():
        path = directory/filename
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==digest:
            continue
        url = f'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/{model}/{filename}'
        temporary = directory/(filename+'.download')
        try:
            with urllib.request.urlopen(url,timeout=120) as source,temporary.open('wb') as target:
                total = 0
                while block := source.read(1024*1024):
                    total += len(block)
                    if total > 50*1024*1024:
                        raise ValueError('Model exceeds the expected size limit')
                    target.write(block)
            if hashlib.sha256(temporary.read_bytes()).hexdigest()!=digest:
                raise ValueError('Speaker model checksum does not match the pinned model')
            temporary.replace(path)
            license_url = f'https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/{model}/LICENSE'
            with urllib.request.urlopen(license_url,timeout=30) as source:
                (directory/(model+'-LICENSE')).write_bytes(source.read())
        finally:
            temporary.unlink(missing_ok=True)
        print(f'Installed {filename}')


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir',default='.cache/speaker-models')
    download(parser.parse_args().dir)
