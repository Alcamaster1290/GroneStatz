import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Mocking all required modules before importing data_pipeline
import sys
from unittest.mock import MagicMock

m = MagicMock()
sys.modules["duckdb"] = m
sys.modules["sqlalchemy"] = m
sys.modules["sqlalchemy.orm"] = m
sys.modules["app.core.config"] = m
sys.modules["app.db.session"] = m
sys.modules["app.services.fantasy"] = m
sys.modules["pydantic_settings"] = m

# Mocking imports within app.services.data_pipeline
# We need to provide the actual functions for Testing
import app.services.data_pipeline as dp

class TestDataPipelineSecurity(unittest.TestCase):
    def test_quote_ident(self):
        self.assertEqual(dp._quote_ident("table"), '"table"')
        self.assertEqual(dp._quote_ident('table"name'), '"table""name"')

    def test_safe_ident_or_null(self):
        self.assertEqual(dp._safe_ident_or_null("column"), '"column"')
        self.assertEqual(dp._safe_ident_or_null(None), "NULL")

    @patch("app.services.data_pipeline.Path")
    @patch("app.services.data_pipeline.duckdb.connect")
    def test_ingest_parquets_to_duckdb_security(self, mock_connect, mock_path):
        mock_con = MagicMock()
        mock_connect.return_value = mock_con

        mock_settings = MagicMock()
        mock_settings.PARQUET_DIR = "/tmp/parquets"
        mock_settings.DUCKDB_PATH = "/tmp/fantasy.duckdb"

        # Setup path mocks
        mock_parquet_dir = MagicMock()
        mock_parquet_dir.exists.return_value = True

        # EXPECTED_PARQUETS mock
        with patch("app.services.data_pipeline.EXPECTED_PARQUETS", {"test.parquet": "test_table"}):
            mock_parquet_path = MagicMock()
            mock_parquet_path.exists.return_value = True
            mock_parquet_path.as_posix.return_value = "/tmp/parquets/test.parquet"

            # Control sequence of Path() creations:
            # 1. parquet_dir = Path(settings.PARQUET_DIR)
            # 2. duckdb_path = Path(settings.DUCKDB_PATH)
            # 3. parquet_path = parquet_dir / parquet_name

            # We need to mock how / works with MagicMock
            mock_parquet_dir.__truediv__.return_value = mock_parquet_path

            mock_path.side_effect = [mock_parquet_dir, MagicMock()]

            dp.ingest_parquets_to_duckdb(mock_settings)

            # Verify that execute was called with quoted table name and parameter binding
            found = False
            for call in mock_con.execute.call_args_list:
                if call.args[0] == 'CREATE OR REPLACE TABLE "test_table" AS SELECT * FROM read_parquet(?)' and \
                   call.args[1] == ["/tmp/parquets/test.parquet"]:
                    found = True
                    break
            self.assertTrue(found, f"Expected call not found. Calls: {mock_con.execute.call_args_list}")

    @patch("app.services.data_pipeline.SessionLocal")
    @patch("app.services.data_pipeline.get_or_create_season")
    @patch("app.services.data_pipeline.duckdb.connect")
    @patch("app.services.data_pipeline.Path")
    def test_sync_duckdb_to_postgres_security(self, mock_path, mock_connect, mock_season, mock_session_local):
        mock_con = MagicMock()
        mock_connect.return_value = mock_con

        mock_path.return_value.exists.return_value = True

        mock_settings = MagicMock()
        mock_settings.DUCKDB_PATH = "/tmp/fantasy.duckdb"

        # Mocking con.table().columns
        mock_teams_table = MagicMock()
        mock_teams_table.columns = ["team_id", "name_short", "name_full"]
        mock_players_table = MagicMock()
        mock_players_table.columns = ["player_id", "name", "position", "team_id", "price", "short_name"]

        mock_con.table.side_effect = lambda name: mock_teams_table if name == "teams" else mock_players_table

        mock_con.execute.return_value.fetchall.return_value = []

        dp.sync_duckdb_to_postgres(mock_settings)

        # Check that team SELECT uses quoted identifiers
        execute_calls = [call.args[0] for call in mock_con.execute.call_args_list if isinstance(call.args[0], str)]

        team_select = next((c for c in execute_calls if "FROM teams" in c), None)
        self.assertIsNotNone(team_select, f"Team SELECT not found. Calls: {execute_calls}")
        self.assertIn('"team_id" as id', team_select)
        self.assertIn('"name_short" as name_short', team_select)
        self.assertIn('"name_full" as name_full', team_select)

        # Check that players SELECT uses quoted identifiers
        player_select = next((c for c in execute_calls if "FROM players_fantasy" in c and "SELECT player_id" in c), None)
        self.assertIsNotNone(player_select, f"Player SELECT not found. Calls: {execute_calls}")
        self.assertIn('"short_name" as short_name', player_select)

if __name__ == "__main__":
    unittest.main()
