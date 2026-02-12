"""Tests for OAuth2 authentication."""

import os
from unittest.mock import MagicMock, patch

import pytest

from cdse.auth import OAuth2Auth
from cdse.exceptions import AuthenticationError


class TestOAuth2Auth:
    """Tests for OAuth2Auth class."""

    def test_init_with_credentials(self):
        """Test initialization with explicit credentials."""
        auth = OAuth2Auth(
            client_id="test-client-id",
            client_secret="test-client-secret",
        )
        assert auth.client_id == "test-client-id"
        assert auth.client_secret == "test-client-secret"

    def test_init_from_env_vars(self):
        """Test initialization from environment variables."""
        with patch.dict(
            os.environ,
            {
                "CDSE_CLIENT_ID": "env-client-id",
                "CDSE_CLIENT_SECRET": "env-client-secret",
            },
        ):
            auth = OAuth2Auth()
            assert auth.client_id == "env-client-id"
            assert auth.client_secret == "env-client-secret"

    def test_init_missing_credentials_raises(self):
        """Test that missing credentials raises AuthenticationError."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove any existing env vars
            os.environ.pop("CDSE_CLIENT_ID", None)
            os.environ.pop("CDSE_CLIENT_SECRET", None)

            with pytest.raises(AuthenticationError) as exc_info:
                OAuth2Auth()

            assert "OAuth2 credentials required" in str(exc_info.value)

    def test_is_valid_no_session(self):
        """Test is_valid returns False when no session."""
        auth = OAuth2Auth("id", "secret")
        assert auth.is_valid() is False

    def test_is_valid_no_token(self):
        """Test is_valid returns False when no token."""
        auth = OAuth2Auth("id", "secret")
        auth._session = MagicMock()
        auth._token = None
        assert auth.is_valid() is False

    @patch("cdse.auth.OAuth2Session")
    @patch("cdse.auth.BackendApplicationClient")
    def test_authenticate_success(self, mock_client, mock_session_cls):
        """Test successful authentication."""
        # Setup mocks
        mock_session = MagicMock()
        mock_session.fetch_token.return_value = {
            "access_token": "test-token",
            "expires_at": 9999999999,
        }
        mock_session_cls.return_value = mock_session

        auth = OAuth2Auth("test-id", "test-secret")
        session = auth.get_session()

        assert session is mock_session
        mock_session.fetch_token.assert_called_once()

    @patch("cdse.auth.OAuth2Session")
    @patch("cdse.auth.BackendApplicationClient")
    def test_authenticate_failure(self, mock_client, mock_session_cls):
        """Test authentication failure raises error."""
        mock_session = MagicMock()
        mock_session.fetch_token.side_effect = Exception("Token error")
        mock_session_cls.return_value = mock_session

        auth = OAuth2Auth("test-id", "test-secret")

        with pytest.raises(AuthenticationError) as exc_info:
            auth.get_session()

        assert "OAuth2 authentication failed" in str(exc_info.value)

    @patch("cdse.auth.OAuth2Session")
    @patch("cdse.auth.BackendApplicationClient")
    def test_get_access_token(self, mock_client, mock_session_cls):
        """Test getting access token."""
        mock_session = MagicMock()
        mock_session.fetch_token.return_value = {
            "access_token": "my-access-token",
            "expires_at": 9999999999,
        }
        mock_session_cls.return_value = mock_session

        auth = OAuth2Auth("test-id", "test-secret")
        token = auth.get_access_token()

        assert token == "my-access-token"

    @patch("cdse.auth.OAuth2Session")
    @patch("cdse.auth.BackendApplicationClient")
    def test_get_bearer_session(self, mock_client, mock_session_cls):
        """Test getting bearer session."""
        mock_oauth_session = MagicMock()
        mock_oauth_session.fetch_token.return_value = {
            "access_token": "bearer-token",
            "expires_at": 9999999999,
        }
        mock_session_cls.return_value = mock_oauth_session

        auth = OAuth2Auth("test-id", "test-secret")
        session = auth.get_bearer_session()

        assert "Authorization" in session.headers
        assert session.headers["Authorization"] == "Bearer bearer-token"
