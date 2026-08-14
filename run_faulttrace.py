"""Cross-platform launcher for the FaultTrace Streamlit application."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(PROJECT_ROOT / "app.py"),
        "--server.address",
        "127.0.0.1",
        "--server.port",
        "8501",
    ]
    return subprocess.call(command, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
