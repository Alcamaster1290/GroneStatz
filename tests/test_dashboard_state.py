from __future__ import annotations

from gronestats.dashboard import state


def test_apply_navigation_action_queues_season_change(monkeypatch) -> None:
    session_state = {
        "selected_season_year": 2025,
        "nav_page": "Temporadas",
        "pending_navigation_action": None,
    }
    reruns: list[str] = []
    monkeypatch.setattr(state.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(state.st, "rerun", lambda: reruns.append("rerun"), raising=False)

    state.apply_navigation_action({"type": "season", "season_year": 2024, "page": "Overview"})

    assert session_state["selected_season_year"] == 2025
    assert session_state["pending_navigation_action"] == {"type": "season", "season_year": 2024, "page": "Overview"}
    assert reruns == ["rerun"]


def test_consume_navigation_action_applies_pending_state(monkeypatch) -> None:
    session_state = {
        "selected_season_year": 2025,
        "nav_page": "Temporadas",
        "pending_navigation_action": {"type": "season", "season_year": 2024, "page": "Overview"},
    }
    monkeypatch.setattr(state.st, "session_state", session_state, raising=False)

    state.consume_navigation_action()

    assert session_state["pending_navigation_action"] is None
    assert session_state["selected_season_year"] == 2024
    assert session_state["nav_page"] == "Overview"
