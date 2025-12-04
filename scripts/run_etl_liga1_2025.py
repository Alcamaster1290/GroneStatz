import subprocess
import sys


def run(cmd: str) -> None:
    print(f"==> {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main() -> None:
    py = sys.executable
    run(f"{py} -m gronestats.processing.data_loader_unprep_liga1_2025")
    run(f"{py} -m gronestats.processing.prep_and_test_data_liga1_2025")


if __name__ == "__main__":
    main()
