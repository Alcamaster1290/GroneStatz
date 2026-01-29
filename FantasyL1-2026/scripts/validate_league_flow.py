from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("ENV_FILE", str(ROOT / ".env.test"))
os.environ.setdefault("APP_ENV", "test")
sys.path.append(str(ROOT / "backend"))

from app.main import app  # noqa: E402

client = TestClient(app)


def assert_status(label: str, response, expected: int = 200) -> dict:
    if response.status_code != expected:
        raise SystemExit(f"{label} failed: {response.status_code} {response.text}")
    return response.json()


def register(email: str, password: str) -> str:
    response = client.post("/auth/register", json={"email": email, "password": password})
    data = assert_status("register", response)
    return data["access_token"]


def create_team(token: str, name: str) -> None:
    response = client.post(
        "/fantasy/team",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name},
    )
    assert_status("create_team", response)


def create_league(token: str, name: str) -> dict:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name},
    )
    return assert_status("create_league", response)


def join_league(token: str, code: str) -> dict:
    response = client.post(
        "/leagues/join",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": code},
    )
    return assert_status("join_league", response)


def get_my_league(token: str) -> dict:
    response = client.get("/leagues/me", headers={"Authorization": f"Bearer {token}"})
    return assert_status("get_my_league", response)


def get_ranking_general(token: str) -> dict:
    response = client.get("/ranking/general", headers={"Authorization": f"Bearer {token}"})
    return assert_status("ranking_general", response)


def get_ranking_league(token: str) -> dict:
    response = client.get("/ranking/league", headers={"Authorization": f"Bearer {token}"})
    return assert_status("ranking_league", response)


def leave_league(token: str) -> dict:
    response = client.post("/leagues/leave", headers={"Authorization": f"Bearer {token}"})
    return assert_status("leave_league", response)


def remove_member(token: str, fantasy_team_id: int) -> dict:
    response = client.delete(
        f"/leagues/members/{fantasy_team_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return assert_status("remove_member", response)


def expect_league_not_found(token: str) -> None:
    response = client.get("/leagues/me", headers={"Authorization": f"Bearer {token}"})
    if response.status_code != 404:
        raise SystemExit(f"expected 404 league_not_found, got {response.status_code} {response.text}")


def main() -> None:
    suffix = uuid.uuid4().hex[:8]
    email_a = f"qa_league_a_{suffix}@example.com"
    email_b = f"qa_league_b_{suffix}@example.com"
    password = "Test1234!"

    token_a = register(email_a, password)
    token_b = register(email_b, password)

    team_a = f"Equipo QA A {suffix}"
    team_b = f"Equipo QA B {suffix}"
    create_team(token_a, team_a)
    create_team(token_b, team_b)

    league = create_league(token_a, f"Liga QA {suffix}")
    join_league(token_b, league["code"])

    league_a = get_my_league(token_a)
    league_b = get_my_league(token_b)

    if league_a["code"] != league["code"] or league_b["code"] != league["code"]:
        raise SystemExit("league membership mismatch")

    if not league_a.get("is_admin"):
        raise SystemExit("creator should be admin")
    if league_b.get("is_admin"):
        raise SystemExit("joiner should not be admin")

    ranking_general = get_ranking_general(token_a)
    ranking_league = get_ranking_league(token_a)

    general_names = {entry["team_name"] for entry in ranking_general["entries"]}
    league_names = {entry["team_name"] for entry in ranking_league["entries"]}

    if team_a not in general_names or team_b not in general_names:
        raise SystemExit("general ranking missing QA teams")

    if team_a not in league_names or team_b not in league_names:
        raise SystemExit("league ranking missing QA teams")

    # Owner leaves -> transfer admin to remaining member
    leave_league(token_a)
    expect_league_not_found(token_a)
    league_b_after = get_my_league(token_b)
    if not league_b_after.get("is_admin"):
        raise SystemExit("admin should transfer to remaining member")

    # Last member leaves -> league deleted
    leave_league(token_b)
    expect_league_not_found(token_b)

    # Admin removes another member
    league2 = create_league(token_a, f"Liga QA2 {suffix}")
    join_league(token_b, league2["code"])
    ranking_league_2 = get_ranking_league(token_a)
    member_ids = [entry["fantasy_team_id"] for entry in ranking_league_2["entries"]]
    target = next((mid for mid in member_ids if mid != league2["owner_fantasy_team_id"]), None)
    if not target:
        raise SystemExit("missing member to remove")
    remove_member(token_a, target)
    expect_league_not_found(token_b)

    print("OK: ligas privadas, admin, transferencia y ranking")


if __name__ == "__main__":
    main()
