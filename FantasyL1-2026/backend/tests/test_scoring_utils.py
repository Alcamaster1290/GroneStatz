import sys
from unittest.mock import MagicMock

# Mock dependencies before importing the module under test
sys.modules["sqlalchemy"] = MagicMock()
sys.modules["sqlalchemy.orm"] = MagicMock()
sys.modules["app.models"] = MagicMock()
sys.modules["app.services.fantasy"] = MagicMock()

import pytest
from app.services.scoring import _clamp_price, _price_delta

def test_price_delta_positive():
    """Test price delta for positive points."""
    assert _price_delta(1.0) == 0.0
    assert _price_delta(2.0) == 0.0
    assert _price_delta(3.0) == pytest.approx(0.1)
    assert _price_delta(5.9) == pytest.approx(0.1)
    assert _price_delta(6.0) == pytest.approx(0.2)
    assert _price_delta(9.0) == pytest.approx(0.3)

def test_price_delta_zero():
    """Test price delta for zero points."""
    assert _price_delta(0.0) == pytest.approx(-0.2)

def test_price_delta_negative():
    """Test price delta for negative points."""
    assert _price_delta(-1.0) == pytest.approx(-0.2)
    assert _price_delta(-1.9) == pytest.approx(-0.2)
    assert _price_delta(-2.0) == pytest.approx(-0.3)
    assert _price_delta(-3.0) == pytest.approx(-0.3)
    assert _price_delta(-4.0) == pytest.approx(-0.4)

def test_clamp_price_within_range():
    """Test that value is returned as-is when within range."""
    assert _clamp_price(5.0) == 5.0
    assert _clamp_price(10.0) == 10.0
    assert _clamp_price(4.0) == 4.0
    assert _clamp_price(12.0) == 12.0

def test_clamp_price_below_min():
    """Test that value is clamped to min_value when below it."""
    assert _clamp_price(3.0) == 4.0
    assert _clamp_price(0.0) == 4.0
    assert _clamp_price(-1.0) == 4.0

def test_clamp_price_above_max():
    """Test that value is clamped to max_value when above it."""
    assert _clamp_price(13.0) == 12.0
    assert _clamp_price(100.0) == 12.0

def test_clamp_price_custom_range():
    """Test with custom min and max values."""
    assert _clamp_price(5.0, min_value=6.0, max_value=8.0) == 6.0
    assert _clamp_price(7.0, min_value=6.0, max_value=8.0) == 7.0
    assert _clamp_price(9.0, min_value=6.0, max_value=8.0) == 8.0

def test_clamp_price_min_equals_max():
    """Test edge case where min_value equals max_value."""
    assert _clamp_price(5.0, min_value=6.0, max_value=6.0) == 6.0
    assert _clamp_price(7.0, min_value=6.0, max_value=6.0) == 6.0
