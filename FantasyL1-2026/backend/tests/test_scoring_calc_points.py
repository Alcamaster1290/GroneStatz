import sys
from unittest.mock import MagicMock
from decimal import Decimal

# Mock dependencies that are not available in the environment to allow importing scoring.py
# This is necessary because the environment lacks packages like sqlalchemy and pydantic.
sys.modules["sqlalchemy"] = MagicMock()
sys.modules["sqlalchemy.orm"] = MagicMock()
sys.modules["app.models"] = MagicMock()
sys.modules["app.services.fantasy"] = MagicMock()

from app.services.scoring import calc_match_points

# Helper classes to mock the database models
class MockPlayer:
    def __init__(self, position=None, team_id=None):
        self.position = position
        self.team_id = team_id

class MockStat:
    def __init__(
        self,
        minutesplayed=0,
        goals=0,
        assists=0,
        saves=0,
        fouls=0,
        yellow_cards=0,
        red_cards=0,
        clean_sheet=None,
        goals_conceded=None
    ):
        self.minutesplayed = minutesplayed
        self.goals = goals
        self.assists = assists
        self.saves = saves
        self.fouls = fouls
        self.yellow_cards = yellow_cards
        self.red_cards = red_cards
        self.clean_sheet = clean_sheet
        self.goals_conceded = goals_conceded

class MockFixture:
    def __init__(self, home_team_id=None, away_team_id=None, home_score=None, away_score=None):
        self.home_team_id = home_team_id
        self.away_team_id = away_team_id
        self.home_score = home_score
        self.away_score = away_score

def test_calc_match_points_basic():
    """Test basic point calculations for goals, assists, minutes, cards."""
    player = MockPlayer(position="M", team_id=1)
    stat = MockStat(
        minutesplayed=90,
        goals=1,      # 4 pts + 3 pts (1//3 * 3 is 0, wait. 1//3 = 0. So no hat trick.)
                      # logic: points += goals * 4; points += (goals // 3) * 3
        assists=1,    # 3 pts
        yellow_cards=0,
        red_cards=0,
        fouls=0
    )
    # goals: 1*4 = 4
    # hat trick: 0
    # assists: 1*3 = 3
    # minutes >= 90: +2
    # total: 4 + 3 + 2 = 9

    points, clean_sheet, conceded = calc_match_points(player, stat, None)
    assert points == 9.0

def test_calc_match_points_hat_trick():
    """Test hat trick bonus."""
    player = MockPlayer(position="F", team_id=1)
    stat = MockStat(minutesplayed=90, goals=3)
    # goals: 3*4 = 12
    # hat trick: 3//3 * 3 = 3
    # minutes: +2
    # total: 12 + 3 + 2 = 17
    points, _, _ = calc_match_points(player, stat, None)
    assert points == 17.0

def test_calc_match_points_cards_and_fouls():
    """Test deductions for cards and fouls."""
    player = MockPlayer(position="D", team_id=1)
    stat = MockStat(
        minutesplayed=90,
        yellow_cards=1, # -3
        red_cards=1,    # -5
        fouls=5         # -1 (5//5)
    )
    # minutes: +2
    # yellow: -3
    # red: -5
    # fouls: -1
    # total: 2 - 3 - 5 - 1 = -7
    points, _, _ = calc_match_points(player, stat, None)
    assert points == -7.0

def test_calc_match_points_goalkeeper_saves():
    """Test goalkeeper points for saves."""
    player = MockPlayer(position="GK", team_id=1)
    stat = MockStat(minutesplayed=90, saves=5)
    # minutes: +2
    # saves: 5//5 = +1
    # clean sheet: default None, so no clean sheet points unless explicitly set or inferred
    # total: 2 + 1 = 3
    points, _, _ = calc_match_points(player, stat, None)
    assert points == 3.0

def test_calc_match_points_clean_sheet_explicit():
    """Test clean sheet points when explicitly provided in stats."""
    player = MockPlayer(position="D", team_id=1)
    stat = MockStat(minutesplayed=90, clean_sheet=1)
    # minutes: +2
    # clean sheet: +3
    # total: 5
    points, cs, _ = calc_match_points(player, stat, None)
    assert points == 5.0
    assert cs == 1

def test_calc_match_points_clean_sheet_inferred_from_fixture():
    """Test clean sheet inferred from fixture when stat is missing."""
    player = MockPlayer(position="D", team_id=1)
    stat = MockStat(minutesplayed=90, clean_sheet=None)
    fixture = MockFixture(home_team_id=1, away_team_id=2, home_score=0, away_score=0)
    # Team 1 conceded 0 (away score).
    # clean_sheet_value becomes 1 because conceded_from_fixture is 0.
    # minutes: +2
    # clean sheet: +3
    # total: 5
    points, cs, conceded = calc_match_points(player, stat, fixture)
    assert points == 5.0
    assert cs == 1
    assert conceded == 0

def test_calc_match_points_conceded_gk():
    """Test goals conceded deduction for GK."""
    player = MockPlayer(position="GK", team_id=1)
    stat = MockStat(minutesplayed=90, goals_conceded=2)
    # minutes: +2
    # conceded: -2
    # clean sheet: No (conceded != 0)
    # total: 0
    points, _, conceded = calc_match_points(player, stat, None)
    assert points == 0.0
    assert conceded == 2

def test_calc_match_points_conceded_inferred():
    """Test goals conceded inferred from fixture."""
    player = MockPlayer(position="GK", team_id=1)
    stat = MockStat(minutesplayed=90, goals_conceded=None)
    fixture = MockFixture(home_team_id=1, away_team_id=2, home_score=2, away_score=1)
    # Team 1 is home. Conceded away_score = 1.
    # minutes: +2
    # conceded: -1
    # total: 1
    points, _, conceded = calc_match_points(player, stat, fixture)
    assert points == 1.0
    assert conceded == 1

def test_calc_match_points_minutes_less_than_90():
    """Test points for minutes played < 90."""
    player = MockPlayer(position="M", team_id=1)
    stat = MockStat(minutesplayed=45)
    # minutes > 0: +1
    # total: 1
    points, _, _ = calc_match_points(player, stat, None)
    assert points == 1.0

def test_calc_match_points_zero_minutes():
    """Test points for 0 minutes played."""
    player = MockPlayer(position="M", team_id=1)
    stat = MockStat(minutesplayed=0)
    # minutes: 0
    # total: 0
    points, _, _ = calc_match_points(player, stat, None)
    assert points == 0.0

def test_calc_match_points_forward_clean_sheet_ignored():
    """Test that forwards do not get clean sheet points."""
    player = MockPlayer(position="F", team_id=1)
    stat = MockStat(minutesplayed=90, clean_sheet=1)
    # minutes: +2
    # clean sheet: ignored for F
    # total: 2
    points, cs, _ = calc_match_points(player, stat, None)
    assert points == 2.0
    assert cs == 1

def test_calc_match_points_forward_clean_sheet_inferred_ignored():
    """Test that forwards do not get clean sheet points even if inferred."""
    player = MockPlayer(position="F", team_id=1)
    stat = MockStat(minutesplayed=90, clean_sheet=None)
    fixture = MockFixture(home_team_id=1, away_team_id=2, home_score=0, away_score=0)
    # conceded_from_fixture is 0.
    # _resolve_fixture_overrides: F is not in {"G", "GK", "D", "M"}. clean_sheet_value remains None.
    # conceded becomes 0.
    # Points logic: checks position again. F not in eligible positions.
    # total: 2
    points, cs, conceded = calc_match_points(player, stat, fixture)
    assert points == 2.0
    assert cs is None
    assert conceded == 0

def test_calc_match_points_clean_sheet_from_conceded_stat_no_fixture():
    """Test clean sheet points inferred from conceded stat (0) when fixture is missing."""
    player = MockPlayer(position="D", team_id=1)
    stat = MockStat(minutesplayed=90, goals_conceded=0, clean_sheet=None)
    # fixture is None.
    # _resolve_fixture_overrides returns (None, 0, None).
    # conceded becomes 0.
    # Points logic: clean_sheet_value is None. But conceded == 0. So points += 3.
    # minutes: +2
    # clean sheet: +3
    # total: 5
    points, cs, conceded = calc_match_points(player, stat, None)
    assert points == 5.0
    assert cs is None
    assert conceded == 0

def test_calc_match_points_override_zero_clean_sheet():
    """Test override behavior when stat says clean sheet is 0 but fixture says 0 conceded."""
    player = MockPlayer(position="D", team_id=1)
    stat = MockStat(minutesplayed=90, clean_sheet=0)
    fixture = MockFixture(home_team_id=1, away_team_id=2, home_score=0, away_score=0)
    # clean_sheet_value starts as 0.
    # conceded_from_fixture is 0.
    # _resolve_fixture_overrides: if clean_sheet_value is 0 and conceded_from_fixture is 0 -> clean_sheet_value becomes 1.
    # minutes: +2
    # clean sheet: +3
    # total: 5
    points, cs, conceded = calc_match_points(player, stat, fixture)
    assert points == 5.0
    assert cs == 1
    assert conceded == 0

def test_calc_match_points_override_zero_conceded():
    """Test override behavior when stat says 0 conceded but fixture says conceded > 0."""
    player = MockPlayer(position="GK", team_id=1)
    stat = MockStat(minutesplayed=90, goals_conceded=0)
    fixture = MockFixture(home_team_id=1, away_team_id=2, home_score=1, away_score=2)
    # Team 1 home. Conceded away_score = 2.
    # goals_conceded_value starts as 0.
    # _resolve_fixture_overrides: if goals_conceded_value is 0 and conceded_from_fixture is 2 -> goals_conceded_value becomes 2.
    # clean_sheet_value starts as None.
    # conceded_from_fixture is 2.
    # _resolve_fixture_overrides: clean_sheet_value becomes 0 (since conceded_from_fixture != 0).
    # minutes: +2
    # conceded: -2
    # total: 0
    points, cs, conceded = calc_match_points(player, stat, fixture)
    assert points == 0.0
    assert conceded == 2
    assert cs == 0
