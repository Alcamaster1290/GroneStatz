"""Arranque local de la v1: construye el release si falta y levanta la API y la web, con un solo comando.

    py -3.11 scripts/dev_web.py                 # http://127.0.0.1:3000 (abre el navegador)
    py -3.11 scripts/dev_web.py --rebuild       # reconstruye el release antes de arrancar
    py -3.11 scripts/dev_web.py --no-browser --api-port 8010 --web-port 3010

Ctrl+C detiene las dos. La web se sirve compilada (`next start`); si falta la compilación, la hace.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
BUNDLE = ROOT / "gronestats" / "data" / "Liga 1 Peru" / "web"


def run(command: list[str], cwd: Path) -> None:
    print("→", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def wait_for(url: str, name: str, seconds: int = 120) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=5).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise SystemExit(f"{name} no respondió en {seconds} s ({url})")


def stop(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":  # npm.cmd lanza a node como hijo: hay que cerrar el árbol
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    else:
        process.terminate()


def main() -> int:
    parser = argparse.ArgumentParser(description="Levanta la API y la web de GroneStats en local.")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--web-port", type=int, default=3000)
    parser.add_argument("--rebuild", action="store_true", help="Reconstruye el release de servicio antes de arrancar.")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("Falta Node.js (npm). Instálalo desde https://nodejs.org")
    if args.rebuild or not (BUNDLE / "current" / "manifest.json").exists():
        run([sys.executable, "-m", "gronestats.web_bundle.build"], ROOT)
    if not (WEB / "node_modules").exists():
        run([npm, "install", "--no-audit", "--no-fund"], WEB)
    if not (WEB / ".next" / "BUILD_ID").exists():
        run([npm, "run", "build"], WEB)

    api_url = f"http://127.0.0.1:{args.api_port}"
    web_url = f"http://127.0.0.1:{args.web_port}"
    api = subprocess.Popen([sys.executable, "-m", "gronestats.api"], cwd=ROOT, env={**os.environ, "GRONESTATS_API_PORT": str(args.api_port)})
    web = subprocess.Popen([npm, "run", "start", "--", "-p", str(args.web_port)], cwd=WEB, env={**os.environ, "GRONESTATS_API_URL": api_url, "GRONESTATS_PUBLIC_API_URL": api_url})
    try:
        wait_for(f"{api_url}/v1/release", "La API")
        wait_for(web_url, "La web")
        print(f"\nAPI  {api_url}/v1/release\nWeb  {web_url}\nCtrl+C para detener.\n")
        if not args.no_browser:
            webbrowser.open(web_url)
        while api.poll() is None and web.poll() is None:
            time.sleep(1)
        print("Un proceso terminó; deteniendo el otro.")
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        stop(web)
        stop(api)


if __name__ == "__main__":
    raise SystemExit(main())
