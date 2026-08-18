"""
stop.py — stop the services scripts/start.py spawned.

Reads logs/*.pid, verifies each pid still matches the expected command
(before killing, so a reused pid can never take down an innocent process),
then taskkills it. Deletes pid files either way.

Run: python scripts/stop.py   (or double-click stop.bat)
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"

# Order matters: backend first, then UI, then n8n.
SERVICES = [
    ("backend", "backend.pid", "uvicorn"),
    ("ui", "ui.pid", "uiserve"),
    ("n8n", "n8n.pid", "n8n"),
]


def cmdline_of(pid: int) -> str | None:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        return out or None
    except Exception:
        return None


def main() -> None:
    stopped: list[str] = []
    skipped: list[str] = []
    for label, pidfile, marker in SERVICES:
        f = LOGS / pidfile
        if not f.exists():
            continue
        try:
            pid = int(f.read_text().strip())
        except ValueError:
            f.unlink(missing_ok=True)
            continue
        cmd = cmdline_of(pid)
        if cmd is None:
            skipped.append(f"{label} (pid {pid}: unverifiable, left alone)")
        elif marker not in cmd:
            skipped.append(f"{label} (pid {pid}: no longer a {marker} process, left alone)")
        else:
            r = subprocess.run(["taskkill", "/T", "/PID", str(pid), "/F"], capture_output=True, text=True)
            if r.returncode == 0:
                stopped.append(f"{label} (pid {pid})")
            else:
                skipped.append(f"{label} (pid {pid}: {r.stderr.strip()})")
        f.unlink(missing_ok=True)
    if stopped:
        print("Stopped: " + ", ".join(stopped))
    if skipped:
        print("Left running: " + ", ".join(skipped))
    if not stopped and not skipped:
        print("Nothing running (no pid files).")


if __name__ == "__main__":
    main()
