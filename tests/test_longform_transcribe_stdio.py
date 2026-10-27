"""The real worker entrypoint must survive Windows pipe encoding defaults."""
import json
import os
from pathlib import Path
import subprocess
import sys


def test_worker_unicode_progress_and_transcript_under_cp1252(tmp_path):
    worker = Path(__file__).resolve().parents[1] / 'backend/services/longform_transcribe.py'
    target = tmp_path / 'transcript.json'
    # Stub inference only; execute the actual worker CLI, logging and atomic write.
    bootstrap = r'''
import contextlib, runpy, sys, types
module = types.ModuleType('transcribe_backends')
def transcribe(path):
    print('\U0001f399 Transcribing \u0939\u093f\u0928\u094d\u0926\u0940')
    return {'language':'hi', 'segments':[{'text':'\u0939\u093f\u0928\u094d\u0926\u0940', 'words':[]}]}
module.transcribe_media = transcribe
module.host_asr_slot = contextlib.nullcontext
module.release_models = lambda: print('\U0001f9f9 Models released')
sys.modules['transcribe_backends'] = module
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
'''
    env = {**os.environ, 'PYTHONIOENCODING': 'cp1252', 'PYTHONUTF8': '0'}
    result = subprocess.run([sys.executable, '-c', bootstrap, str(worker), 'fixture.mp4', str(target)],
        env=env, capture_output=True, check=True)
    assert '\U0001f399' in result.stdout.decode('utf-8')
    assert json.loads(target.read_text(encoding='utf-8'))['segments'][0]['text'] == '\u0939\u093f\u0928\u094d\u0926\u0940'
    assert not target.with_suffix('.tmp').exists()
