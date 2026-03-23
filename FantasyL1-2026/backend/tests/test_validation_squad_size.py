import sys
import unittest
from decimal import Decimal
from unittest.mock import MagicMock

# Mock dependencies that are not available in the environment
sys.modules["sqlalchemy"] = MagicMock()
sys.modules["sqlalchemy.orm"] = MagicMock()
sys.modules["app.models"] = MagicMock()

from app.services.validation import validate_squad

class TestSquadSizeValidation(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()

    def _setup_mock_players(self, player_ids):
        mock_players = [
            MagicMock(player_id=pid, position='M', team_id=1, price_current=Decimal("5.0"))
            for pid in player_ids
        ]
        self.db.execute.return_value.scalars.return_value.all.return_value = mock_players

    def test_validate_squad_size_under(self):
        """Test validation fails when squad has fewer than 15 players (14)."""
        player_ids = list(range(14))
        self._setup_mock_players(player_ids)
        errors = validate_squad(self.db, player_ids)
        self.assertIn("squad_must_have_15_players", errors)

    def test_validate_squad_size_exact(self):
        """Test validation passes size check when squad has exactly 15 players."""
        player_ids = list(range(15))
        self._setup_mock_players(player_ids)
        errors = validate_squad(self.db, player_ids)
        self.assertNotIn("squad_must_have_15_players", errors)

    def test_validate_squad_size_over(self):
        """Test validation fails when squad has more than 15 players (16)."""
        player_ids = list(range(16))
        self._setup_mock_players(player_ids)
        errors = validate_squad(self.db, player_ids)
        self.assertIn("squad_must_have_15_players", errors)
