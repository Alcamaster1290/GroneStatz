import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add backend directory to path
backend_path = Path(__file__).resolve().parents[1] / "backend"
sys.path.append(str(backend_path))

try:
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.deps import get_db
    from app.models import Season, Round, Team, PlayerCatalog, Fixture
    # We don't import get_settings here to avoid early execution issues, we'll patch it.
except ImportError as e:
    print(f"Error importing app: {e}")
    sys.exit(1)

def verify_zeroclaw():
    client = TestClient(app)
    token = "test-token"

    headers = {"X-ZeroClaw-Token": token}

    print("Verifying ZeroClaw endpoints...")

    # We need to mock get_settings in app.api.zeroclaw
    with patch("app.api.zeroclaw.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.ZEROCLAW_API_KEY = token
        mock_get_settings.return_value = mock_settings

        # 0. Invalid Token (First check security)
        print("Checking invalid token...")
        response = client.get("/zeroclaw/status", headers={"X-ZeroClaw-Token": "invalid"})
        if response.status_code != 401:
            print(f"FAILED: Invalid token should return 401, got {response.status_code}")
            print(response.json())
            sys.exit(1)
        print("SUCCESS: Invalid token rejected")

        # Mocking for valid requests
        # We need to mock get_db to return a mock session
        mock_session = MagicMock()

        # Override the dependency
        app.dependency_overrides[get_db] = lambda: mock_session

        # We also need to patch the service functions that use the DB
        with patch("app.api.zeroclaw.get_or_create_season") as mock_get_season, \
             patch("app.api.zeroclaw.get_current_round") as mock_get_round:

            # Setup mock objects
            mock_season = MagicMock(spec=Season)
            mock_season.id = 1
            mock_season.name = "2026 Season"
            mock_get_season.return_value = mock_season

            mock_round = MagicMock(spec=Round)
            mock_round.round_number = 5
            mock_round.is_closed = False
            mock_round.starts_at = datetime.now()
            mock_get_round.return_value = mock_round

            # 1. Status
            print("Checking /zeroclaw/status...")
            response = client.get("/zeroclaw/status", headers=headers)
            if response.status_code != 200:
                print(f"FAILED: /zeroclaw/status returned {response.status_code}")
                print(response.json())
            else:
                print("SUCCESS: /zeroclaw/status")
                print(response.json())

            # 2. Teams
            mock_team = MagicMock(spec=Team)
            mock_team.id = 1
            mock_team.name_full = "Alianza Lima"
            mock_team.name_short = "ALI"

            mock_session.execute.return_value.scalars.return_value.all.return_value = [mock_team]

            print("Checking /zeroclaw/teams...")
            response = client.get("/zeroclaw/teams", headers=headers)
            if response.status_code != 200:
                print(f"FAILED: /zeroclaw/teams returned {response.status_code}")
                print(response.json())
            else:
                print("SUCCESS: /zeroclaw/teams")
                print(response.json())

            # 3. Players
            mock_player = MagicMock(spec=PlayerCatalog)
            mock_player.player_id = 10
            mock_player.name = "Paolo Guerrero"
            mock_player.team_id = 1
            mock_player.position = "F"
            mock_player.price_current = 10.5
            mock_player.is_injured = False

            mock_session.execute.return_value.all.return_value = [(mock_player, 50.0)]

            print("Checking /zeroclaw/players...")
            response = client.get("/zeroclaw/players?limit=5", headers=headers)
            if response.status_code != 200:
                print(f"FAILED: /zeroclaw/players returned {response.status_code}")
                print(response.json())
            else:
                print("SUCCESS: /zeroclaw/players")
                print(response.json())

            # 4. Fixtures
            mock_fixture = MagicMock(spec=Fixture)
            mock_fixture.id = 100
            mock_fixture.home_team_id = 1
            mock_fixture.away_team_id = 2
            mock_fixture.kickoff_at = datetime.now()
            mock_fixture.status = "Programado"
            mock_fixture.home_score = None
            mock_fixture.away_score = None

            mock_session.execute.return_value.all.return_value = [(mock_fixture, 5)]

            print("Checking /zeroclaw/fixtures...")
            response = client.get("/zeroclaw/fixtures", headers=headers)
            if response.status_code != 200:
                print(f"FAILED: /zeroclaw/fixtures returned {response.status_code}")
                print(response.json())
            else:
                print("SUCCESS: /zeroclaw/fixtures")
                print(response.json())

    # 5. Check Not Configured
    # Mock settings with empty key
    with patch("app.api.zeroclaw.get_settings") as mock_get_settings_empty:
        mock_settings_empty = MagicMock()
        mock_settings_empty.ZEROCLAW_API_KEY = ""
        mock_get_settings_empty.return_value = mock_settings_empty

        print("Checking not configured (empty key)...")
        response = client.get("/zeroclaw/status", headers=headers)
        if response.status_code != 503:
            print(f"FAILED: Should return 503 when not configured, got {response.status_code}")
            print(response.json())
        else:
            print("SUCCESS: Not configured correctly returned 503")

    print("\nVerification complete.")

if __name__ == "__main__":
    verify_zeroclaw()
