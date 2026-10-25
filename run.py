"""Supervise the two local OpenShorts servers without killing unrelated processes."""
import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen
import webbrowser

REPO_ROOT = Path(__file__).resolve().parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"


def get_python_exe():
    candidates = dict.fromkeys([sys.executable, str(REPO_ROOT / ".venv/Scripts/python.exe")])
    for candidate in candidates:
        if not Path(candidate).is_file():
            continue
        try:
            result = subprocess.run([candidate, "-c",
                "import uvicorn, fastapi, cv2, torch, scenedetect, mediapipe, ultralytics, google.genai"],
                capture_output=True, timeout=60)
            if result.returncode == 0:
                return candidate
        except (OSError, subprocess.TimeoutExpired):
            continue
    raise RuntimeError("No Python runtime has the backend/video dependencies. Install requirements.txt first.")


def check_ports(ports=(8000, 5173)):
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as exc:
                raise RuntimeError(f"Port {port} is already in use. Keep the existing server or stop it before relaunching.") from exc


def server_ready(url):
    try:
        # Vite's SPA fallback serves '/' only to HTML clients. A generic probe
        # can receive 404 while the browser page is perfectly healthy.
        with urlopen(Request(url, headers={"Accept": "text/html,application/json"}), timeout=1) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


def start_server(name, command, cwd, env, log_dir):
    log_path = log_dir / f"{name}.log"
    proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")

    def relay():
        with log_path.open("a", encoding="utf-8") as log:
            for line in proc.stdout:
                log.write(line)
                log.flush()
                try:
                    print(f"[{name}] {line.rstrip()}", flush=True)
                except (UnicodeEncodeError, OSError):
                    pass
        proc.stdout.close()

    threading.Thread(target=relay, daemon=True).start()
    return proc


def stop_server(proc):
    # Only stop children this launcher owns, never every listener on a port.
    if proc is None or proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def wait_for_startup(backend, frontend=None, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for name, proc in [("backend", backend), ("frontend", frontend)]:
            if proc is None:
                continue
            code = proc.poll()
            if code is not None:
                raise RuntimeError(f"{name} exited during startup (exit {code}). See .cache/launcher/{name}.log")
        if server_ready("http://127.0.0.1:8000/health") and (
                frontend is None or server_ready("http://127.0.0.1:5173/")):
            return
        time.sleep(0.5)
    raise RuntimeError("Servers did not become ready within 90 seconds. See .cache/launcher/*.log")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    backend = frontend = None
    try:
        check_ports()
        python_exe = get_python_exe()
        node = shutil.which("node")
        vite = DASHBOARD_DIR / "node_modules/vite/bin/vite.js"
        if not node or not vite.is_file():
            raise RuntimeError("Frontend dependencies are missing. Install Node.js and run npm install in dashboard.")
        log_dir = REPO_ROOT / ".cache/launcher"
        log_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
                   VITE_PROXY_TARGET="http://127.0.0.1:8000")
        print(f"Starting OpenShorts with {python_exe}. Logs: {log_dir}", flush=True)
        backend_command = [python_exe, "-X", "faulthandler", "-m", "uvicorn", "app:app",
                           "--host", "127.0.0.1", "--port", "8000"]
        backend = start_server("backend", backend_command, REPO_ROOT, env, log_dir)
        # Existing browser tabs reconnect as soon as Vite starts. Bring up the
        # API first so that initial /api/config cannot fail during ML startup.
        wait_for_startup(backend)
        frontend_command = [node, str(vite), "--host", "127.0.0.1", "--port", "5173", "--strictPort"]
        frontend = start_server("frontend", frontend_command, DASHBOARD_DIR, env, log_dir)
        wait_for_startup(backend, frontend)
        print("OpenShorts ready: http://localhost:5173 | Ctrl+C stops both servers.", flush=True)
        if not args.no_browser:
            webbrowser.open("http://localhost:5173/")
        restarts = 0
        backend_restarts = 0
        while True:
            if backend.poll() is not None:
                if backend_restarts >= 3:
                    raise RuntimeError(f"Backend repeatedly exited. See {log_dir / 'backend.log'}")
                backend_restarts += 1
                print(f"Backend exited (exit {backend.returncode}); restarting ({backend_restarts}/3).", flush=True)
                time.sleep(backend_restarts)
                backend = start_server("backend", backend_command, REPO_ROOT, env, log_dir)
                wait_for_startup(backend)
            if frontend.poll() is not None:
                if restarts >= 3:
                    raise RuntimeError("Frontend repeatedly exited. See .cache/launcher/frontend.log")
                restarts += 1
                print(f"Frontend exited (exit {frontend.returncode}); restarting ({restarts}/3).", flush=True)
                time.sleep(restarts)
                frontend = start_server("frontend", frontend_command, DASHBOARD_DIR, env, log_dir)
                wait_for_startup(backend, frontend)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping OpenShorts...", flush=True)
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"OpenShorts could not stay running: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        stop_server(frontend)
        stop_server(backend)


if __name__ == "__main__":
    raise SystemExit(main())
