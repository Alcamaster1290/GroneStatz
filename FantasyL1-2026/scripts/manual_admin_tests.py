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

from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
settings = get_settings()


def assert_status(label: str, response, expected: int = 200) -> dict:
    if response.status_code != expected:
        raise SystemExit(f"{label} failed: {response.status_code} {response.text}")
    return response.json()


def register(email: str, password: str) -> str:
    response = client.post("/auth/register", json={"email": email, "password": password})
    data = assert_status("register", response)
    return data["access_token"]


def login(email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    data = assert_status("login", response)
    return data["access_token"]


def create_team(token: str, name: str) -> dict:
    response = client.post(
        "/fantasy/team",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name},
    )
    return assert_status("create_team", response)


def admin_headers() -> dict:
    return {"X-Admin-Token": settings.ADMIN_TOKEN}


def admin_list_teams() -> list[dict]:
    response = client.get("/admin/teams", headers=admin_headers())
    return assert_status("admin_list_teams", response)


def admin_delete_user(user_id: int) -> dict:
    response = client.delete(f"/admin/users/{user_id}", headers=admin_headers())
    return assert_status("admin_delete_user", response)


def admin_seed_rounds(rounds: int) -> dict:
    response = client.post(f"/admin/seed_season_rounds?rounds={rounds}", headers=admin_headers())
    return assert_status("admin_seed_rounds", response)


def admin_list_rounds() -> list[dict]:
    response = client.get("/admin/rounds", headers=admin_headers())
    return assert_status("admin_list_rounds", response)


def admin_close_round(round_number: int) -> dict:
    response = client.post(
        f"/admin/rounds/close?round_number={round_number}",
        headers=admin_headers(),
    )
    return assert_status("admin_close_round", response)


def reset_request(email: str) -> dict:
    response = client.post("/auth/reset/request", json={"email": email})
    return assert_status("reset_request", response)


def reset_confirm(email: str, code: str, new_password: str) -> dict:
    response = client.post(
        "/auth/reset/confirm",
        json={"email": email, "code": code, "new_password": new_password},
    )
    return assert_status("reset_confirm", response)


def main() -> None:
    suffix = uuid.uuid4().hex[:8]
    email_delete = f"qa_delete_{suffix}@example.com"
    email_reset = f"qa_reset_{suffix}@example.com"
    password = "Test1234!"

    print("== Registro usuarios ==")
    token_delete = register(email_delete, password)
    token_reset = register(email_reset, password)
    print(f"created {email_delete}")
    print(f"created {email_reset}")

    print("\n== Crear equipos ==")
    create_team(token_delete, f"Equipo Delete {suffix}")
    create_team(token_reset, f"Equipo Reset {suffix}")
    print("teams created")

    print("\n== Admin: eliminar usuario ==")
    teams_before = admin_list_teams()
    user_row = next((team for team in teams_before if team["user_email"] == email_delete), None)
    if not user_row:
        raise SystemExit("user for deletion not found in admin list")
    admin_delete_user(user_row["user_id"])
    teams_after = admin_list_teams()
    still_exists = any(team["user_email"] == email_delete for team in teams_after)
    print(f"delete user ok, still_exists={still_exists}")
    if still_exists:
        raise SystemExit("user still present after deletion")

    print("\n== Admin: cerrar ronda ==")
    admin_seed_rounds(1)
    rounds = admin_list_rounds()
    round_one = next((round for round in rounds if round["round_number"] == 1), None)
    if not round_one:
        raise SystemExit("round 1 not found after seed")
    admin_close_round(1)
    rounds_after = admin_list_rounds()
    round_one_after = next((round for round in rounds_after if round["round_number"] == 1), None)
    print(f"round 1 closed={round_one_after['is_closed']}")
    if not round_one_after["is_closed"]:
        raise SystemExit("round 1 not closed")

    print("\n== Reset de password ==")
    reset_resp = reset_request(email_reset)
    code = reset_resp.get("reset_code")
    if not code:
        if settings.APP_ENV in {"test", "qa"}:
            raise SystemExit("reset_code missing in non-prod env")
        print("reset_code omitted (prod expected)")
    else:
        reset_confirm(email_reset, code, "NewPass123!")
        login(email_reset, "NewPass123!")
        print("reset password ok")

    print("\n== Cleanup usuarios ==")
    teams_final = admin_list_teams()
    reset_row = next((team for team in teams_final if team["user_email"] == email_reset), None)
    if not reset_row:
        raise SystemExit("user for cleanup not found in admin list")
    admin_delete_user(reset_row["user_id"])
    teams_after_cleanup = admin_list_teams()
    still_exists_reset = any(team["user_email"] == email_reset for team in teams_after_cleanup)
    print(f"cleanup ok, still_exists_reset={still_exists_reset}")
    if still_exists_reset:
        raise SystemExit("reset user still present after cleanup")

    print("\nALL OK")


if __name__ == "__main__":
    main()
