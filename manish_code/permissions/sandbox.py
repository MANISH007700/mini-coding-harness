"""Kernel-enforced limits on what bash can touch.

One policy - read anything, write only inside the project (and the temp dir),
no network - and a different enforcement mechanism per OS.

The macOS profile is adapted from openai/codex (Apache-2.0), simplified.
https://github.com/openai/codex
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path.cwd().resolve()
TMP = Path(tempfile.gettempdir()).resolve()

SECRETS = PROJECT / ".env"  # the API key: never writable or deletable from bash

# .git stays writable (unlike upstream neural-code) so the git-commit skill
# works; permissions.py still denies git push/reset/clean.
PROFILE = f"""(version 1)
(deny default)
(allow process-exec process-fork signal)
(allow file-read*)
(allow sysctl-read)
(deny network*)
(allow file-write* (subpath "{PROJECT}") (subpath "{TMP}") (literal "/dev/null"))
(deny file-write* (literal "{SECRETS}"))
"""


def wrap(command):
    """Wrap a shell command in an OS sandbox. None means we have no sandbox."""
    if sys.platform == "darwin":
        profile = TMP / "manish-code.sb"
        profile.write_text(PROFILE)
        return ["sandbox-exec", "-f", str(profile), "/bin/sh", "-c", command]

    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        return [
            "bwrap",
            "--ro-bind", "/", "/",
            "--bind", str(PROJECT), str(PROJECT),
            "--bind", str(TMP), str(TMP),
            *(["--ro-bind", str(SECRETS), str(SECRETS)] if SECRETS.exists() else []),
            "--dev", "/dev", "--proc", "/proc",
            "--unshare-net", "--die-with-parent",
            "/bin/sh", "-c", command,
        ]

    return None  # Windows, or Linux without bubblewrap


def name():
    if sys.platform == "darwin":
        return "seatbelt"
    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        return "bubblewrap"
    return "none"


def run(command, timeout=120):
    """Run a command, sandboxed when the OS lets us."""
    sandboxed = wrap(command)
    return subprocess.run(
        sandboxed or command,
        shell=sandboxed is None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
