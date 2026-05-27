"""Shared pytest fixtures and configuration for the test suite."""

import os
import pytest


# ---------------------------------------------------------------------------
# Set required environment variables before any app module is imported.
# This prevents pydantic-settings from raising ValidationError at import time.
# ---------------------------------------------------------------------------

_REQUIRED_ENV = {
    "DATABASE_HOST": "localhost",
    "DATABASE_PORT": "5432",
    "DATABASE_NAME": "talentkru_test",
    "DATABASE_USER": "test_user",
    "DATABASE_PASSWORD": "test_password",
    "JWT_SIGNING_KEY": "test-jwt-signing-key",
    "ENCRYPTION_KEY": "test-encryption-key",
    "STORAGE_BACKEND": "local",
    "AGENT_API_KEY": "test-agent-api-key",
    "METRICS_USERNAME": "metrics_user",
    "METRICS_PASSWORD": "metrics_password",
}

for _key, _value in _REQUIRED_ENV.items():
    os.environ.setdefault(_key, _value)
