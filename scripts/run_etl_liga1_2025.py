from __future__ import annotations

import subprocess
import sys
import warnings


def main() -> None:
    warnings.warn(
        "scripts.run_etl_liga1_2025 is deprecated. Use `python -m gronestats.processing.pipeline run "
        "--league \"Liga 1 Peru\" --season 2025 --publish-target all` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    command = [
        sys.executable,
        "-m",
        "gronestats.processing.pipeline",
        "run",
        "--league",
        "Liga 1 Peru",
        "--season",
        "2025",
        "--mode",
        "full",
        "--publish-target",
        "all",
    ]
    raise SystemExit(subprocess.run(command).returncode)


if __name__ == "__main__":
    main()
