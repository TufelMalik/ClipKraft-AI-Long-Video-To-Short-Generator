"""Local launcher failures must be visible and must only stop owned servers."""
from types import SimpleNamespace

import pytest
import run as launcher


def test_busy_port_does_not_kill_its_owner(monkeypatch):
    class Socket:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def bind(self, addr): raise OSError('busy')
    monkeypatch.setattr(launcher.socket, 'socket', lambda *a: Socket())
    with pytest.raises(RuntimeError, match='already in use'):
        launcher.check_ports()


def test_startup_exit_is_reported_instead_of_claiming_ready(monkeypatch):
    monkeypatch.setattr(launcher, 'server_ready', lambda *a: True)
    with pytest.raises(RuntimeError, match='frontend exited during startup'):
        launcher.wait_for_startup(SimpleNamespace(poll=lambda: None), SimpleNamespace(poll=lambda: 1))


def test_startup_requires_both_http_servers(monkeypatch):
    checks = []
    monkeypatch.setattr(launcher, 'server_ready', lambda url: checks.append(url) or True)
    child = SimpleNamespace(poll=lambda: None)
    launcher.wait_for_startup(child, child)
    assert checks == ['http://127.0.0.1:8000/health', 'http://127.0.0.1:5173/']


def test_readiness_probe_requests_html_for_vites_spa(monkeypatch):
    requests = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr(launcher, 'urlopen', lambda req, **kwargs: requests.append(req) or Response())
    assert launcher.server_ready('http://127.0.0.1:5173/')
    assert 'text/html' in requests[0].get_header('Accept')


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    vite = tmp_path / 'node_modules/vite/bin/vite.js'
    vite.parent.mkdir(parents=True)
    vite.touch()
    monkeypatch.setattr(launcher, 'DASHBOARD_DIR', tmp_path)
    monkeypatch.setattr(launcher, 'REPO_ROOT', tmp_path)
    monkeypatch.setattr(launcher, 'check_ports', lambda: None)
    monkeypatch.setattr(launcher, 'get_python_exe', lambda: 'python')
    monkeypatch.setattr(launcher.shutil, 'which', lambda _: 'node')
    monkeypatch.setattr(launcher, 'wait_for_startup', lambda *a: None)
    stopped = []
    monkeypatch.setattr(launcher, 'stop_server', lambda p: stopped.append(p) if p is not None else None)
    return stopped


def test_failed_frontend_spawn_cleans_up_owned_backend(runtime, monkeypatch):
    backend = object()
    def start(name, *args):
        if name == 'frontend': raise OSError('failed to spawn')
        return backend
    monkeypatch.setattr(launcher, 'start_server', start)
    assert launcher.main(['--no-browser']) == 1
    assert backend in runtime


def test_failed_startup_returns_nonzero_and_cleans_up_both(runtime, monkeypatch):
    children = []
    def start(*args):
        child = object()
        children.append(child)
        return child
    monkeypatch.setattr(launcher, 'start_server', start)
    def fail(*args): raise RuntimeError('not ready')
    monkeypatch.setattr(launcher, 'wait_for_startup', fail)
    assert launcher.main(['--no-browser']) == 1
    assert runtime == list(reversed(children))


def test_stop_server_does_not_touch_already_exited_process(monkeypatch):
    def unexpected(*args, **kwargs): pytest.fail('must not taskkill an exited process')
    monkeypatch.setattr(launcher.subprocess, 'run', unexpected)
    launcher.stop_server(SimpleNamespace(poll=lambda: 0))


def test_frontend_exit_restarts_without_stopping_backend(runtime, monkeypatch):
    backend = SimpleNamespace(poll=lambda: None)
    first_frontend = SimpleNamespace(poll=lambda: 1, returncode=1)
    next_frontend = SimpleNamespace(poll=lambda: None)
    frontend_calls = []
    def start(name, *args):
        if name == 'backend': return backend
        frontend_calls.append(name)
        return first_frontend if len(frontend_calls) == 1 else next_frontend
    monkeypatch.setattr(launcher, 'start_server', start)
    def sleep(delay):
        # Retry delay happens before the replacement starts; the backend must
        # remain untouched. Stop the test at the following supervisor tick.
        assert runtime == []
        if delay == 0.5: raise KeyboardInterrupt
    monkeypatch.setattr(launcher.time, 'sleep', sleep)
    assert launcher.main(['--no-browser']) == 0
    assert len(frontend_calls) == 2
    assert runtime == [next_frontend, backend]


def test_backend_exit_restarts_without_stopping_frontend(runtime, monkeypatch):
    first_backend = SimpleNamespace(poll=lambda: 3221225477, returncode=3221225477)
    next_backend = SimpleNamespace(poll=lambda: None)
    frontend = SimpleNamespace(poll=lambda: None)
    backend_calls = []
    def start(name, *args):
        if name == 'frontend': return frontend
        backend_calls.append(name)
        return first_backend if len(backend_calls) == 1 else next_backend
    monkeypatch.setattr(launcher, 'start_server', start)
    def sleep(delay):
        assert runtime == []
        if delay == 0.5: raise KeyboardInterrupt
    monkeypatch.setattr(launcher.time, 'sleep', sleep)
    assert launcher.main(['--no-browser']) == 0
    assert len(backend_calls) == 2
    assert runtime == [frontend, next_backend]
