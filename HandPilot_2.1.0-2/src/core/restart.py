from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time


_HELPER = r'''
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path(sys.argv[1]).resolve()
args = sys.argv[2:]
time.sleep(1.25)
env = os.environ.copy()
env.pop("HANDPILOT_RESTARTING", None)
entry = root / "main.py"
cmd = [sys.executable, str(entry), *args]
subprocess.Popen(
    cmd,
    cwd=str(root),
    env=env,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
    close_fds=True,
)
'''


def request_application_restart(root: str | Path, argv: list[str] | None = None) -> None:
    """Launch a detached relaunch helper, then let the current GUI exit."""
    project_root = Path(root).resolve()
    entry = project_root / "main.py"
    if not entry.exists():
        raise FileNotFoundError(f"HandPilot entrypoint not found: {entry}")

    args = [str(value) for value in (argv or [])]
    env = os.environ.copy()
    env["HANDPILOT_RESTARTING"] = "1"

    subprocess.Popen(
        [sys.executable, "-c", _HELPER, str(project_root), *args],
        cwd=str(project_root),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
