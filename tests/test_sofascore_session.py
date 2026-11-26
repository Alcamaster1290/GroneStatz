from __future__ import annotations

import pytest

from gronestats.processing.sofascore_session import api_path


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
