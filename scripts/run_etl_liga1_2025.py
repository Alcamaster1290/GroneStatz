import subprocess
import sys


def run(cmd: list[str]) -> None:
    print(f"==> {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main() -> None:
    py = sys.executable
    run([py, "-m", "gronestats.processing.data_loader_unprep_liga1_2025"])
    run([py, "-m", "gronestats.processing.prep_and_test_data_liga1_2025"])


if __name__ == "__main__":
    main()
