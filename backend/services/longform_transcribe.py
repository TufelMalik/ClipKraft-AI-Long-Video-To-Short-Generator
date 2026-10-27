"""Dedicated cancellable ASR process; no selection, crops, captions or paid API calls."""
import json
import os
import sys
from pathlib import Path

if __name__ == '__main__':
    # Redirected Windows pipes default to cp1252; ASR progress includes Unicode.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
    from transcribe_backends import transcribe_media, release_models, host_asr_slot
    with host_asr_slot():
        try:
            transcript = transcribe_media(sys.argv[1])
        finally:
            release_models()
    destination = Path(sys.argv[2])
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(transcript, ensure_ascii=False), encoding='utf-8')
    os.replace(temporary, destination)
