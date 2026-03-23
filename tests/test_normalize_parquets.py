import pandas as pd
import pytest
from gronestats.processing.normalize_parquets import normalize_position

def test_normalize_position_mappings():
    # Test G mappings
    s = pd.Series(["GK", "GOALKEEPER", "ARQ"])
    expected = pd.Series(["G", "G", "G"], dtype="string")
    pd.testing.assert_series_equal(normalize_position(s), expected)

    # Test D mappings
    s = pd.Series(["DEF", "DF", "DEFENDER"])
    expected = pd.Series(["D", "D", "D"], dtype="string")
    pd.testing.assert_series_equal(normalize_position(s), expected)

    # Test M mappings
    s = pd.Series(["MID", "MF", "MIDFIELDER"])
    expected = pd.Series(["M", "M", "M"], dtype="string")
    pd.testing.assert_series_equal(normalize_position(s), expected)

    # Test F mappings
    s = pd.Series(["FWD", "FW", "FORWARD", "DEL", "ST"])
    expected = pd.Series(["F", "F", "F", "F", "F"], dtype="string")
    pd.testing.assert_series_equal(normalize_position(s), expected)

def test_normalize_position_case_and_whitespace():
    s = pd.Series(["  gk  ", "Gk", "  def  ", "Df"])
    expected = pd.Series(["G", "G", "D", "D"], dtype="string")
    pd.testing.assert_series_equal(normalize_position(s), expected)

def test_normalize_position_unknown_values():
    s = pd.Series(["COACH", "REFEREE", "G", "D"])
    expected = pd.Series(["COACH", "REFEREE", "G", "D"], dtype="string")
    pd.testing.assert_series_equal(normalize_position(s), expected)

def test_normalize_position_null_values():
    s = pd.Series(["GK", None, pd.NA])
    # x = s.astype("string").str.strip().str.upper() will result in <NA> for None and pd.NA
    expected = pd.Series(["G", pd.NA, pd.NA], dtype="string")
    pd.testing.assert_series_equal(normalize_position(s), expected)
