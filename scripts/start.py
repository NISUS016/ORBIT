"""
start.py — one-command dev startup for Orbit.

Starts whatever is missing and opens the UI:
  n8n (port 5678) -> backend (port 8000) -> deploy workflows if unwired ->
  UI static server (port 8080) -> open browser.

Run: python scripts/start.py   (or double-click start.bat)
Any already-running piece is detected and left alone.
Logs: everything this script spawns writes to logs/ (backend.log, n8n.log, ui.log).
Pids: spawns are tracked in logs/*.pid so scripts/stop.py can shut them down.
Services are detached from this console — close the window freely.
"""

import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
UI = ROOT / "ui"
LOGS = ROOT / "logs"

N8N_PORT = 5678
BACKEND_PORT = 8000
UI_PORT = 8080
UI_URL = f"http://localhost:{UI_PORT}"

PYTHON = BACKEND / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)


def write_pid(key: str, pid: int) -> None:
    LOGS.mkdir(exist_ok=True)
    (LOGS / f"{key}.pid").write_text(str(pid), encoding="utf-8")


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.8)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def wait_port(port: int, timeout: float, label: str) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open(port):
            return True
        time.sleep(0.5)
    print(f"  [WARN] {label} did not open port {port} in {timeout:.0f}s - check its logs above.")
    return False


def port_owner(port: int) -> int | None:
    """PID of the process LISTENING on the given port (via netstat)."""
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    except OSError:
        return None
    for line in out.splitlines():
        parts = line.split()
        if (
            len(parts) >= 5
            and parts[0] == "TCP"
            and parts[1].endswith(f":{port}")
            and parts[3] == "LISTENING"
        ):
            try:
                return int(parts[4])
            except ValueError:
                return None
    return None


def backend_is_current() -> bool:
    """True if the server on :8000 serves the newest API surface (/settings)."""
    try:
        resp = httpx.get(f"http://127.0.0.1:{BACKEND_PORT}/settings", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def spawn(cmd: list[str], cwd: Path, label: str, logfile: str | None = None,
          pidkey: str | None = None) -> subprocess.Popen | None:
    """Spawn a child fully detached from this console; stdout/stderr go to
    logs/<logfile> when given, and the pid is recorded in logs/<pidkey>.pid."""
    LOGS.mkdir(exist_ok=True)
    sink = None
    if logfile:
        sink = open(LOGS / logfile, "a", encoding="utf-8", errors="replace")
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(cwd),
            stdout=sink if sink else subprocess.DEVNULL,
            stderr=sink if sink else subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    except FileNotFoundError:
        print(f"  [FAIL] cannot run {label}: {cmd[0]} not found on PATH")
        return None
    if pidkey:
        write_pid(pidkey, proc.pid)
    where = f" -> logs/{logfile}" if logfile else ""
    print(f"  [OK] {label} starting (pid {proc.pid}){where}")
    return proc


def kill_process(pid: int) -> None:
    """Non-elevated kill attempt (works for our own / same-session processes)."""
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)


def kill_elevated(pid: int) -> bool:
    """Kill a process from another session: spawn an elevated taskkill
    (one UAC click) and WAIT for it. Returns False if the user declined."""
    ps_cmd = (
        "try { Start-Process -FilePath 'taskkill' -ArgumentList '/PID "
        + str(pid)
        + " /F' -Verb RunAs -Wait -WindowStyle Hidden -ErrorAction Stop; exit 0 } "
        "catch { exit 1 }"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, timeout=90,
        )
        return proc.returncode == 0
    except Exception:
        return False


def free_port(start: int, stop: int = 8100) -> int:
    """First port in [start, stop) that is not in use."""
    for port in range(start, stop):
        if not port_open(port):
            return port
    return start


def write_backend_js(backend_port: int) -> None:
    """ui/backend.js tells the frontend which port the backend is on.
    Written only when the backend is NOT on the default 8000."""
    target = UI / "backend.js"
    if backend_port == BACKEND_PORT:
        if target.exists():
            target.unlink()
        return
    target.write_text(
        f'window.ORBIT_BACKEND = "http://localhost:{backend_port}";\n',
        encoding="utf-8",
    )
    print(f"  [OK] wrote {target} so the UI talks to port {backend_port}")


def backend_section(port: int) -> None:
    """Ensure a current backend is running on `port`, starting it if needed."""
    if port_open(port):
        if backend_is_current() or port != BACKEND_PORT:
            print(f"  [OK] backend already running on port {port}")
        else:
            # Stale build on the default port: normal kill first
            pid = port_owner(port)
            print(f"  [WARN] stale backend (pid {pid}) on port {port} - stopping it...")
            if pid:
                kill_process(pid)
                time.sleep(1.5)
            if port_open(port):
                # Still there: it runs in another session — ask for admin once
                if os.environ.get("ORBIT_NO_ELEVATE") != "1" and pid:
                    print("  [..] running in another session - requesting admin rights (1 UAC click)...")
                    kill_elevated(pid)
                    deadline = time.time() + 15
                    while time.time() < deadline and port_open(port):
                        time.sleep(0.5)
                if port_open(port):
                    # UAC declined or still stuck: move the backend to a free port
                    alt = free_port(BACKEND_PORT + 1)
                    print(f"  [WARN] port {port} is stuck - using port {alt} for the backend instead.")
                    port = alt
    if not port_open(port):
        print(f"  [..] backend not running - starting it on port {port}...")
        spawn(
            [str(PYTHON), "-m", "uvicorn", "main:app", "--port", str(port)],
            BACKEND, "backend", logfile="backend.log", pidkey="backend",
        )
        deadline = time.time() + 30
        ok = False
        while time.time() < deadline:
            try:
                httpx.get(f"http://127.0.0.1:{port}/health", timeout=2)
                ok = True
                break
            except Exception:
                time.sleep(0.5)
        print(f"  [OK] backend healthy on port {port}" if ok else
              "  [WARN] backend not healthy yet - see logs/backend.log")
        owner = port_owner(port)
        if ok and owner:
            write_pid("backend", owner)
    write_backend_js(port)


def load_env() -> dict:
    """Settings from backend/credentials.json (primary) + .env (legacy)."""
    values = {}
    import json

    creds = BACKEND / "credentials.json"
    if creds.exists():
        try:
            data = json.loads(creds.read_text(encoding="utf-8"))
            n8n = data.get("n8n", {})
            values["N8N_BASE_URL"] = n8n.get("base_url", "")
            values["N8N_API_KEY"] = n8n.get("api_key", "")
            for name, url in (n8n.get("webhooks") or {}).items():
                values[f"N8N_{name.upper()}_WEBHOOK"] = url
            values["LLM_PROVIDER"] = data.get("active_provider", "")
        except Exception:
            pass
    for env_file in (BACKEND / ".env", ROOT / ".env"):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    values.setdefault(k.strip(), v.strip().strip("'\""))
            break
    return values


def webhooks_wired(env: dict) -> bool:
    return all(env.get(k) for k in ("N8N_RESEARCH_WEBHOOK", "N8N_SUMMARIZER_WEBHOOK", "N8N_EXTRACTOR_WEBHOOK"))


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    env = load_env()
    n8n_base = env.get("N8N_BASE_URL", f"http://localhost:{N8N_PORT}")
    n8n_port = int(env.get("N8N_PORT") or N8N_PORT)

    print("Orbit one-command start\n-----------------------")

    # 1. n8n
    if port_open(n8n_port):
        print(f"  [OK] n8n already running at {n8n_base}")
    else:
        print("  [..] n8n not running - starting it...")
        spawn(["n8n", "start"], ROOT, "n8n", logfile="n8n.log", pidkey="n8n")
        wait_port(n8n_port, 90.0, "n8n")
        owner = port_owner(n8n_port)
        if owner:
            write_pid("n8n", owner)
        if not port_open(n8n_port):
            print("  [FAIL] n8n is required - install it (npm i -g n8n) and try again.")
            return

    # 2. Backend (handles stale/invisible processes automatically)
    backend_section(BACKEND_PORT)

    # 3. Deploy workflows if the webhook URLs are not wired yet
    if not webhooks_wired(env):
        print("  [..] webhooks not wired - deploying workflows to n8n...")
        proc = subprocess.run(
            [str(PYTHON), str(ROOT / "scripts" / "deploy.py")],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        print("".join(f"      {line}" for line in proc.stdout.splitlines(True)))
        if proc.returncode != 0:
            print(f"  [WARN] deploy failed ({proc.returncode}) - known tasks will fall through to the factory.")
    else:
        print("  [OK] webhooks already wired in .env")

    # 4. UI static server
    if port_open(UI_PORT):
        print(f"  [OK] UI already served on port {UI_PORT}")
    else:
        print(f"  [..] UI not served - starting static server on port {UI_PORT}...")
        spawn(
            [str(PYTHON), str(ROOT / "scripts" / "uiserve.py"), str(UI_PORT), str(UI)],
            ROOT, "UI server", logfile="ui.log", pidkey="ui",
        )
        wait_port(UI_PORT, 15.0, "UI server")
        owner = port_owner(UI_PORT)
        if owner:
            write_pid("ui", owner)

    print(f"\nAll set! Opening {UI_URL}")
    if os.environ.get("ORBIT_NO_BROWSER") != "1":
        webbrowser.open(UI_URL)
    print("Services run detached from this window - you can close it anytime.")
    print(f"To stop everything: python {ROOT / 'scripts' / 'stop.py'}")


if __name__ == "__main__":
    main()