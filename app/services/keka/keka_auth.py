import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class KekaAuthError(Exception):
    """Exception raised for errors during Keka authentication."""
    pass


class KekaAuthManager:
    """
    Manages OAuth2 authentication for Keka API.
    Handles token acquisition, in-memory caching with TTL expiry, and auto-refresh.
    """

    _access_token: Optional[str] = None
    _expires_at: Optional[datetime] = None
    _lock = asyncio.Lock()

    @classmethod
    def get_token_url(cls) -> str:
        """Determines the token endpoint based on configuration."""
        if settings.KEKA_TOKEN_URL:
            return settings.KEKA_TOKEN_URL
        if (settings.KEKA_ENVIRONMENT or "production").lower() == "sandbox":
            return "https://login.kekademo.com/connect/token"
        return "https://login.keka.com/connect/token"

    @classmethod
    def get_credentials(cls) -> dict:
        """Retrieves and validates Keka credentials from environment / settings / .env file."""
        from pathlib import Path
        from dotenv import dotenv_values
        env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
        env_vals = dotenv_values(env_path) if env_path.exists() else {}

        client_id = os.getenv("KEKA_CLIENT_ID") or env_vals.get("KEKA_CLIENT_ID") or settings.KEKA_CLIENT_ID
        client_secret = os.getenv("KEKA_CLIENT_SECRET") or env_vals.get("KEKA_CLIENT_SECRET") or settings.KEKA_CLIENT_SECRET
        api_key = os.getenv("KEKA_API_KEY") or env_vals.get("KEKA_API_KEY") or settings.KEKA_API_KEY
        company_name = (
            os.getenv("KEKA_COMPANY_NAME")
            or os.getenv("KEKA_COMPANY")
            or env_vals.get("KEKA_COMPANY_NAME")
            or env_vals.get("KEKA_COMPANY")
            or settings.KEKA_COMPANY_NAME
            or getattr(settings, "KEKA_COMPANY", "")
        )

        return {
            "client_id": (client_id or "").strip(),
            "client_secret": (client_secret or "").strip(),
            "api_key": (api_key or "").strip(),
            "company_name": (company_name or "").strip(),
        }

    @classmethod
    def is_configured(cls) -> bool:
        """Checks if all required credentials are present."""
        creds = cls.get_credentials()
        return bool(
            creds["client_id"]
            and creds["client_secret"]
            and creds["api_key"]
            and creds["company_name"]
        )

    @classmethod
    def clear_cache(cls) -> None:
        """Clears in-memory token cache."""
        cls._access_token = None
        cls._expires_at = None
        logger.info("Keka access token cache cleared.")

    @classmethod
    async def get_access_token(cls, force_refresh: bool = False) -> str:
        """
        Returns a valid Keka OAuth2 access token.
        Reuses cached token if valid. Requests a new one if expired or force_refresh is True.
        """
        # Fast path without lock if token is still comfortably valid (> 60s buffer)
        now = datetime.now(timezone.utc)
        if (
            not force_refresh
            and cls._access_token
            and cls._expires_at
            and now < (cls._expires_at - timedelta(seconds=60))
        ):
            return cls._access_token

        async with cls._lock:
            # Double check within lock
            now = datetime.now(timezone.utc)
            if (
                not force_refresh
                and cls._access_token
                and cls._expires_at
                and now < (cls._expires_at - timedelta(seconds=60))
            ):
                return cls._access_token

            creds = cls.get_credentials()
            if not creds["client_id"] or not creds["client_secret"] or not creds["api_key"]:
                missing = [k for k, v in creds.items() if not v and k != "company_name"]
                raise KekaAuthError(
                    f"Keka credentials missing in configuration: {', '.join(missing)}. "
                    f"Please set KEKA_CLIENT_ID, KEKA_CLIENT_SECRET, and KEKA_API_KEY in .env"
                )

            token_url = cls.get_token_url()
            logger.info("Requesting new Keka access token from %s...", token_url)

            payload = {
                "grant_type": "kekaapi",
                "scope": "kekaapi",
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
                "api_key": creds["api_key"],
            }

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    response = await client.post(token_url, data=payload, headers=headers)

                if response.status_code != 200:
                    error_detail = response.text
                    try:
                        err_json = response.json()
                        error_detail = err_json.get("error_description") or err_json.get("error") or response.text
                    except Exception:
                        pass

                    logger.error(
                        "Keka token request failed. Status: %s, Details: %s",
                        response.status_code,
                        error_detail,
                    )
                    raise KekaAuthError(
                        f"Failed to authenticate with Keka API (HTTP {response.status_code}): {error_detail}"
                    )

                data = response.json()
                access_token = data.get("access_token")
                expires_in = int(data.get("expires_in", 3600))

                if not access_token:
                    raise KekaAuthError("Keka token response did not contain an 'access_token'")

                cls._access_token = access_token
                cls._expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

                logger.info(
                    "Successfully acquired Keka access token (TTL: %ds, expires at %s UTC)",
                    expires_in,
                    cls._expires_at.strftime("%Y-%m-%d %H:%M:%S"),
                )
                return cls._access_token

            except httpx.RequestError as exc:
                logger.error("Network error while connecting to Keka token service: %s", exc)
                raise KekaAuthError(f"Network error contacting Keka token service: {str(exc)}") from exc
