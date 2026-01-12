"""OAuth2 authentication for Copernicus Data Space Ecosystem."""

import os
import time
from typing import Optional

import requests
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

from cdse.exceptions import AuthenticationError


class OAuth2Auth:
    """OAuth2 authentication handler for CDSE.

    This class manages OAuth2 client credentials authentication
    for the Copernicus Data Space Ecosystem.

    Attributes:
        TOKEN_URL: CDSE OAuth2 token endpoint

    Example:
        >>> auth = OAuth2Auth("client_id", "client_secret")
        >>> session = auth.get_session()
        >>> # Use session for API requests
    """

    TOKEN_URL = (
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE"
        "/protocol/openid-connect/token"
    )

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """Initialize OAuth2 authentication.

        Args:
            client_id: OAuth2 client ID. If not provided, reads from
                CDSE_CLIENT_ID environment variable.
            client_secret: OAuth2 client secret. If not provided, reads from
                CDSE_CLIENT_SECRET environment variable.

        Raises:
            AuthenticationError: If credentials are not provided or invalid.
        """
        self.client_id = client_id or os.environ.get("CDSE_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("CDSE_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise AuthenticationError(
                "OAuth2 credentials required. Provide client_id and client_secret "
                "or set CDSE_CLIENT_ID and CDSE_CLIENT_SECRET environment variables."
            )

        self._session: Optional[OAuth2Session] = None
        self._token: Optional[dict] = None
        self._token_expires_at: float = 0

    def get_session(self) -> OAuth2Session:
        """Get an authenticated OAuth2 session.

        Returns:
            Authenticated OAuth2Session ready for API requests.

        Raises:
            AuthenticationError: If authentication fails.
        """
        if self._session is None or not self.is_valid():
            self._authenticate()

        return self._session

    def get_access_token(self) -> str:
        """Get the current access token.

        Returns:
            The OAuth2 access token string.

        Raises:
            AuthenticationError: If no valid token available.
        """
        if self._token is None or not self.is_valid():
            self._authenticate()

        return self._token.get("access_token", "")

    def _authenticate(self) -> None:
        """Perform OAuth2 client credentials authentication.

        Raises:
            AuthenticationError: If authentication fails.
        """
        try:
            # Create OAuth2 client using client credentials grant
            client = BackendApplicationClient(client_id=self.client_id)
            self._session = OAuth2Session(client=client)

            # Fetch access token
            self._token = self._session.fetch_token(
                token_url=self.TOKEN_URL,
                client_id=self.client_id,
                client_secret=self.client_secret,
                include_client_id=True,
            )

            # Store expiration time
            self._token_expires_at = self._token.get("expires_at", time.time() + 600)

        except Exception as e:
            raise AuthenticationError(f"OAuth2 authentication failed: {e}")

    def is_valid(self) -> bool:
        """Check if the current token is valid.

        Returns:
            True if token exists and is not expired, False otherwise.
        """
        if self._session is None or self._token is None:
            return False

        # Check expiration with 60-second buffer
        return time.time() < (self._token_expires_at - 60)

    def refresh(self) -> None:
        """Refresh the authentication token.

        Forces re-authentication to get a new token.
        """
        self._authenticate()

    def get_bearer_session(self) -> requests.Session:
        """Get a standard requests Session with Bearer token.

        Useful for APIs that don't support OAuth2Session directly.

        Returns:
            requests.Session with Authorization header set.
        """
        access_token = self.get_access_token()
        session = requests.Session()
        session.headers["Authorization"] = f"Bearer {access_token}"
        return session
