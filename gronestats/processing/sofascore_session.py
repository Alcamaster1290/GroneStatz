"""Sesión de navegador persistente para leer el API JSON de SofaScore.

SofaScore bloquea (403 ``Forbidden``/``challenge``) a los clientes que lanzan un navegador
nuevo por cada petición y a ``api.sofascore.com``. Lo que sí funciona es una sola sesión
de Chrome "calentada" en www.sofascore.com que consulta ``/api/v1/...`` con ``fetch`` desde
la propia página (mismas cookies y cabeceras que la web).

``get_json`` reemplaza el transporte de ScraperFC (``botasaurus_browser_get_json``).
"""
from __future__ import annotations

import atexit
import json
import os
import re
import threading
import time
from typing import Any
from urllib.parse import urlsplit

WEB_ORIGIN = "https://www.sofascore.com"
HEADLESS = os.getenv("GRONESTATS_SOFASCORE_HEADLESS", "0").lower() in {"1", "true", "yes"}
MAX_ATTEMPTS = int(os.getenv("GRONESTATS_SOFASCORE_ATTEMPTS", "5"))
MIN_INTERVAL_SECONDS = float(os.getenv("GRONESTATS_SOFASCORE_MIN_INTERVAL", "0.4"))
CALL_TIMEOUT_SECONDS = float(os.getenv("GRONESTATS_SOFASCORE_CALL_TIMEOUT", "60"))
WARMUP_TIMEOUT_SECONDS = float(os.getenv("GRONESTATS_SOFASCORE_WARMUP_TIMEOUT", "120"))

_lock = threading.RLock()
_driver: Any = None
_last_request_at = 0.0


def api_path(url: str) -> str:
    """Devuelve la ruta ``/api/v1/...`` sin ``/`` final (con ``/`` final SofaScore responde 403)."""
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    return f"{path}?{parts.query}" if parts.query else path


def _run_with_timeout(fn, seconds: float, *args):
    """Ejecuta ``fn`` en un hilo y lanza TimeoutError si no responde.

    Si el Chrome muere o se cierra, las llamadas de botasaurus pueden quedarse colgadas
    para siempre; con esto el bucle de reintentos puede abrir un navegador nuevo.
    """
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = fn(*args)
        except BaseException as exc:  # noqa: BLE001 - se re-lanza en el hilo principal
            box["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        raise TimeoutError(f"{getattr(fn, '__name__', 'call')} sin respuesta tras {seconds:.0f}s")
    if "error" in box:
        raise box["error"]
    return box.get("value")


def _close_driver() -> None:
    global _driver
    if _driver is not None:
        try:
            _driver.close()
        except Exception:
            pass
        _driver = None


def _discard_driver() -> None:
    """Suelta el navegador actual y lo cierra en segundo plano (puede estar colgado)."""
    global _driver
    stale, _driver = _driver, None
    if stale is not None:
        threading.Thread(target=lambda: stale.close(), daemon=True).start()


def _warm_up() -> None:
    """(Re)abre el navegador y visita la home para obtener las cookies normales de la web."""
    global _driver
    _close_driver()
    from botasaurus_driver.driver import Driver

    _driver = Driver(headless=HEADLESS)
    _driver.get(WEB_ORIGIN + "/")
    _driver.sleep(5)


def _fetch(path: str) -> tuple[int, str]:
    script = (
        "return fetch(%s, {credentials: 'include'})"
        ".then(async r => JSON.stringify({s: r.status, b: await r.text()}))" % json.dumps(path)
    )
    out = _driver.run_js(script)
    data = json.loads(out)
    return int(data["s"]), data["b"]


def _navigate(path: str) -> dict[str, Any]:
    """Alternativa: abrir la URL JSON como página. Algunos endpoints (p. ej. /seasons) solo ceden así."""
    try:
        _driver.get(WEB_ORIGIN + path)
        text = (_driver.page_text or "").strip()
        match = re.match(r"^<pre[^>]*>(.*)</pre>$", text, re.IGNORECASE | re.DOTALL)
        parsed = json.loads(match.group(1).strip() if match else text)
    except Exception:
        parsed = {}
    finally:
        try:
            _driver.get(WEB_ORIGIN + "/")
            _driver.sleep(2)
        except Exception:
            pass
    return parsed if isinstance(parsed, dict) else {}


def get_json(url: str) -> dict[str, Any]:
    """GET de una URL del API de SofaScore. Reintenta ante ``403``; devuelve el JSON del error si no cede."""
    global _last_request_at
    path = api_path(url)
    with _lock:
        last_body: dict[str, Any] = {"error": {"code": 0, "reason": "no_response"}}
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if _driver is None:
                try:
                    _run_with_timeout(_warm_up, WARMUP_TIMEOUT_SECONDS)
                except Exception:
                    _discard_driver()
                    time.sleep(min(3 * attempt, 15))
                    continue
            wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
            if wait > 0:
                time.sleep(wait)
            _last_request_at = time.monotonic()
            try:
                status, body = _run_with_timeout(_fetch, CALL_TIMEOUT_SECONDS, path)
            except Exception:
                status, body = 0, ""
            try:
                parsed = json.loads(body) if body else {}
            except ValueError:
                parsed = {}
            if status == 200:
                return parsed
            if parsed:
                last_body = parsed
            if status == 404:
                return last_body
            if status == 0:
                # El navegador no respondió (cerrado o colgado): descartarlo y abrir otro.
                _discard_driver()
                continue
            try:
                navigated = _run_with_timeout(_navigate, CALL_TIMEOUT_SECONDS, path)
            except Exception:
                navigated = {}
            if navigated and "error" not in navigated:
                return navigated
            # 403 (challenge) o 429: esperar y, desde el 2.º intento, recalentar.
            time.sleep(min(3 * attempt, 15))
            if attempt >= 2:
                _discard_driver()
        return last_body


atexit.register(_close_driver)
