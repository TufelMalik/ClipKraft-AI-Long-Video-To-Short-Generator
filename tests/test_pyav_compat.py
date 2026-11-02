from types import SimpleNamespace
import sys

import pytest

from transcribe_backends import _patch_pyav_metadata_errors


def test_pyav_retry_drops_only_unsupported_metadata_errors_keyword():
    calls = []

    def open_video(file, **kwargs):
        calls.append(kwargs.copy())
        if 'metadata_errors' in kwargs:
            raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")
        return file, kwargs

    av = SimpleNamespace(open=open_video)
    _patch_pyav_metadata_errors(av)

    assert av.open('sample.mp4', mode='r', metadata_errors='ignore') == ('sample.mp4', {'mode': 'r'})
    assert calls == [
        {'mode': 'r', 'metadata_errors': 'ignore'},
        {'mode': 'r'},
    ]


def test_pyav_compat_preserves_unrelated_type_errors():
    def open_video(*_args, **_kwargs):
        raise TypeError('invalid mode')

    av = SimpleNamespace(open=open_video)
    _patch_pyav_metadata_errors(av)

    with pytest.raises(TypeError, match='invalid mode'):
        av.open('sample.mp4', metadata_errors='ignore')


def test_pyav_compat_is_optional_when_asr_dependency_is_not_installed(monkeypatch):
    monkeypatch.setitem(sys.modules, 'av', None)

    _patch_pyav_metadata_errors()
