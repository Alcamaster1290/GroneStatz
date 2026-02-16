import os
import pytest
from unittest.mock import patch
from pydantic import ValidationError
from app.core.config import Settings

def test_admin_token_required():
    """Test that Settings cannot be instantiated without ADMIN_TOKEN."""
    # Create a copy of the environment without ADMIN_TOKEN
    new_env = os.environ.copy()
    if "ADMIN_TOKEN" in new_env:
        del new_env["ADMIN_TOKEN"]

    # We need to ensure we don't pick up .env file that might have it
    new_env["APP_ENV"] = "test-security"
    new_env["ENV_FILE"] = "/dev/null" # Point to empty file

    # Use patch.dict to replace os.environ with our modified copy
    # clear=True ensures we ONLY use what's in new_env (plus standard environment vars if we copied them)
    # Since we copied os.environ, clear=True is effectively replacing os.environ with our copy.

    with patch.dict(os.environ, new_env, clear=True):
        with pytest.raises(ValidationError) as excinfo:
            Settings(_env_file=None, _env_file_encoding='utf-8')

    assert "ADMIN_TOKEN" in str(excinfo.value)
    assert "Field required" in str(excinfo.value)

def test_admin_token_from_env():
    """Test that Settings loads ADMIN_TOKEN from environment variable."""
    # We patch only ADMIN_TOKEN, keeping other environment variables intact
    with patch.dict(os.environ, {"ADMIN_TOKEN": "secure-token-123"}):
        settings = Settings(_env_file=None)
        assert settings.ADMIN_TOKEN == "secure-token-123"
