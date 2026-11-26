from __future__ import annotations

import base64

import pytest

from gronestats.processing import sofascore_session
from gronestats.processing.sofascore_session import api_path, get_image


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://api.sofascore.com/api/v1/unique-tournament/406/seasons/", "/api/v1/unique-tournament/406/seasons"),
        ("https://www.sofascore.com/api/v1/event/15714347", "/api/v1/event/15714347"),
        ("https://api.sofascore.com/api/v1/event/1/lineups/", "/api/v1/event/1/lineups"),
        ("https://api.sofascore.com/api/v1/x/?page=2", "/api/v1/x?page=2"),
    ],
)
def test_api_path_strips_host_and_trailing_slash(url: str, expected: str) -> None:
    # SofaScore responde 403 si la ruta termina en '/'.
    assert api_path(url) == expected


def _fake_browser(monkeypatch: pytest.MonkeyPatch, replies: list[tuple[int, str, str]]) -> list[str]:
    """Un navegador falso: ``_fetch_binary`` devuelve las respuestas en orden y anota las rutas pedidas."""
    paths: list[str] = []

    def fetch(path: str) -> tuple[int, str, str]:
        paths.append(path)
        return replies.pop(0)

    monkeypatch.setattr(sofascore_session, "_driver", object())
    monkeypatch.setattr(sofascore_session, "_fetch_binary", fetch)
    monkeypatch.setattr(sofascore_session, "_warm_up", lambda: setattr(sofascore_session, "_driver", object()))
    monkeypatch.setattr(sofascore_session, "_discard_driver", lambda: setattr(sofascore_session, "_driver", None))
    monkeypatch.setattr(sofascore_session, "MIN_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(sofascore_session, "MAX_ATTEMPTS", 2)
    monkeypatch.setattr(sofascore_session.time, "sleep", lambda seconds: None)
    return paths


def test_get_image_returns_the_bytes_of_an_image_response(monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"\x89PNG\r\n\x1a\n" + bytes(range(256))
    paths = _fake_browser(monkeypatch, [(200, "image/png", base64.b64encode(data).decode())])

    result = get_image("https://api.sofascore.com/api/v1/player/7/image")

    assert result == {"content_type": "image/png", "data": data}
    assert paths == ["/api/v1/player/7/image"]


def test_get_image_reports_a_404_without_retrying(monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _fake_browser(monkeypatch, [(404, "application/json", "")])

    result = get_image("https://api.sofascore.com/api/v1/player/8/image")

    assert result["error"]["code"] == 404
    assert len(paths) == 1  # no hay foto: reintentar no la crea


def test_get_image_treats_a_200_that_is_not_an_image_as_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _fake_browser(monkeypatch, [(200, "text/html; charset=utf-8", base64.b64encode(b"<html>challenge</html>").decode())])

    result = get_image("https://api.sofascore.com/api/v1/player/9/image")

    assert result["error"]["code"] == 200 and "not_an_image" in result["error"]["reason"]
    assert len(paths) == 1


def test_get_image_gives_up_with_the_last_error_after_the_allowed_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _fake_browser(monkeypatch, [(403, "text/html", ""), (403, "text/html", "")])

    result = get_image("https://api.sofascore.com/api/v1/player/10/image")

    assert result["error"]["code"] == 403
    assert len(paths) == 2
