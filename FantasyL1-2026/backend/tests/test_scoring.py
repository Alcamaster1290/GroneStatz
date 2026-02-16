import sys
from unittest.mock import MagicMock

# Mock dependencies that are not available in the environment to allow importing scoring.py
# This is necessary because the environment lacks packages like sqlalchemy and pydantic.
sys.modules["sqlalchemy"] = MagicMock()
sys.modules["sqlalchemy.orm"] = MagicMock()
sys.modules["app.models"] = MagicMock()
sys.modules["app.services.fantasy"] = MagicMock()

from app.services.scoring import _clamp_price

def test_clamp_price_within_range():
    """Test price clamping when the value is within the default [4.0, 12.0] range."""
    assert _clamp_price(8.0) == 8.0
    assert _clamp_price(4.0) == 4.0
    assert _clamp_price(12.0) == 12.0

def test_clamp_price_below_range():
    """Test price clamping when the value is below the default range."""
    assert _clamp_price(2.0) == 4.0
    assert _clamp_price(0.0) == 4.0
    assert _clamp_price(-5.0) == 4.0

def test_clamp_price_above_range():
    """Test price clamping when the value is above the default range."""
    assert _clamp_price(15.0) == 12.0
    assert _clamp_price(20.0) == 12.0
    assert _clamp_price(100.0) == 12.0

def test_clamp_price_custom_range():
    """Test price clamping with custom min and max values."""
    assert _clamp_price(5.0, min_value=6.0, max_value=10.0) == 6.0
    assert _clamp_price(11.0, min_value=6.0, max_value=10.0) == 10.0
    assert _clamp_price(8.0, min_value=6.0, max_value=10.0) == 8.0

def test_clamp_price_boundary_values():
    """Test price clamping exactly at and just outside the boundary values."""
    # Exactly at boundaries
    assert _clamp_price(4.0, min_value=4.0, max_value=12.0) == 4.0
    assert _clamp_price(12.0, min_value=4.0, max_value=12.0) == 12.0

    # Just outside boundaries
    assert _clamp_price(3.99, min_value=4.0, max_value=12.0) == 4.0
    assert _clamp_price(12.01, min_value=4.0, max_value=12.0) == 12.0

    # Just inside boundaries
    assert _clamp_price(4.01, min_value=4.0, max_value=12.0) == 4.01
    assert _clamp_price(11.99, min_value=4.0, max_value=12.0) == 11.99
