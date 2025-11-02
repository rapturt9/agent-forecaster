"""Kalshi API client for fetching market questions and outcomes."""

import os
import base64
import httpx
from datetime import datetime
from typing import Any, Literal
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from pydantic import BaseModel


class KalshiMarket(BaseModel):
    """Represents a Kalshi market/question."""

    ticker: str
    title: str
    question: str
    market_type: Literal["binary", "categorical", "numerical"]
    status: str
    close_time: datetime | None = None
    expiration_time: datetime | None = None
    resolution: str | None = None
    resolution_value: Any | None = None
    category: str | None = None
    ranged_group_name: str | None = None
    min_value: float | None = None
    max_value: float | None = None

    def is_active(self) -> bool:
        """Check if market is currently active for forecasting."""
        return self.status in ["open", "active"]

    def is_resolved(self) -> bool:
        """Check if market has been resolved."""
        return self.status == "settled" and self.resolution is not None


class KalshiClient:
    """Client for interacting with Kalshi API."""

    BASE_URL = "https://trading-api.kalshi.com/trade-api/v2"

    def __init__(self, email: str | None = None, api_key: str | None = None, private_key: str | None = None):
        """Initialize Kalshi client.

        Args:
            email: Kalshi account email (defaults to KALSHI_EMAIL env var)
            api_key: Kalshi API key ID (defaults to KALSHI_API_KEY or KALSHI_API_ID env var)
            private_key: Kalshi RSA private key (defaults to KALSHI_PRIVATE_KEY env var)
        """
        self.email = email or os.getenv("KALSHI_EMAIL")
        # Support both KALSHI_API_KEY and KALSHI_API_ID
        self.api_key = api_key or os.getenv("KALSHI_API_KEY") or os.getenv("KALSHI_API_ID")
        private_key_str = private_key or os.getenv("KALSHI_PRIVATE_KEY", "")

        # Handle escaped newlines and quotes in private key
        if private_key_str:
            private_key_str = private_key_str.replace('\\n', '\n').strip('"').strip("'")

        if not all([self.email, self.api_key, private_key_str]):
            raise ValueError(
                "Kalshi credentials not found. Set KALSHI_EMAIL, KALSHI_API_KEY (or KALSHI_API_ID), "
                "and KALSHI_PRIVATE_KEY environment variables."
            )

        # Load private key
        try:
            self.private_key = serialization.load_pem_private_key(
                private_key_str.encode(),
                password=None,
                backend=default_backend()
            )
        except Exception as e:
            raise ValueError(f"Failed to load private key: {e}")

        self.client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=30.0)
        self.access_token: str | None = None

    async def _sign_message(self, message: str) -> str:
        """Sign a message with the RSA private key."""
        signature = self.private_key.sign(
            message.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode()

    async def _login(self) -> None:
        """Authenticate with Kalshi API."""
        timestamp = str(int(datetime.now().timestamp() * 1000))
        message = f"{timestamp}POST/trade-api/v2/login"
        signature = await self._sign_message(message)

        response = await self.client.post(
            "/login",
            json={"email": self.email, "key_id": self.api_key},
            headers={
                "KALSHI-ACCESS-SIGNATURE": signature,
                "KALSHI-ACCESS-TIMESTAMP": timestamp,
            }
        )
        response.raise_for_status()
        data = response.json()
        self.access_token = data["token"]

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid access token."""
        if not self.access_token:
            await self._login()

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make an authenticated request to Kalshi API."""
        await self._ensure_authenticated()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"

        response = await self.client.request(method, endpoint, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    async def get_markets(
        self,
        limit: int = 100,
        status: str | None = "open",
        series_ticker: str | None = None,
    ) -> list[KalshiMarket]:
        """Fetch markets from Kalshi.

        Args:
            limit: Maximum number of markets to return
            status: Filter by market status ("open", "closed", "settled")
            series_ticker: Filter by series ticker

        Returns:
            List of Kalshi markets
        """
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if series_ticker:
            params["series_ticker"] = series_ticker

        data = await self._request("GET", "/markets", params=params)

        markets = []
        for market_data in data.get("markets", []):
            # Determine market type
            market_type = "binary"  # Default
            if market_data.get("ranged_group_name"):
                market_type = "numerical"
            elif len(market_data.get("subtitle", "")) > 50:  # Heuristic for categorical
                market_type = "categorical"

            market = KalshiMarket(
                ticker=market_data["ticker"],
                title=market_data.get("title", ""),
                question=market_data.get("subtitle", market_data.get("title", "")),
                market_type=market_type,
                status=market_data["status"],
                close_time=datetime.fromisoformat(market_data["close_time"].replace("Z", "+00:00"))
                if market_data.get("close_time")
                else None,
                expiration_time=datetime.fromisoformat(
                    market_data["expiration_time"].replace("Z", "+00:00")
                )
                if market_data.get("expiration_time")
                else None,
                resolution=market_data.get("result"),
                category=market_data.get("category"),
                ranged_group_name=market_data.get("ranged_group_name"),
            )
            markets.append(market)

        return markets

    async def get_market(self, ticker: str) -> KalshiMarket:
        """Fetch a specific market by ticker.

        Args:
            ticker: Market ticker symbol

        Returns:
            KalshiMarket object
        """
        data = await self._request("GET", f"/markets/{ticker}")
        market_data = data["market"]

        # Determine market type
        market_type = "binary"
        if market_data.get("ranged_group_name"):
            market_type = "numerical"
        elif len(market_data.get("subtitle", "")) > 50:
            market_type = "categorical"

        return KalshiMarket(
            ticker=market_data["ticker"],
            title=market_data.get("title", ""),
            question=market_data.get("subtitle", market_data.get("title", "")),
            market_type=market_type,
            status=market_data["status"],
            close_time=datetime.fromisoformat(market_data["close_time"].replace("Z", "+00:00"))
            if market_data.get("close_time")
            else None,
            expiration_time=datetime.fromisoformat(
                market_data["expiration_time"].replace("Z", "+00:00")
            )
            if market_data.get("expiration_time")
            else None,
            resolution=market_data.get("result"),
            category=market_data.get("category"),
            ranged_group_name=market_data.get("ranged_group_name"),
            min_value=market_data.get("floor_strike"),
            max_value=market_data.get("cap_strike"),
        )

    async def get_market_outcome(self, ticker: str) -> dict[str, Any] | None:
        """Get the resolved outcome of a market (for validation only).

        Args:
            ticker: Market ticker symbol

        Returns:
            Dictionary with outcome information, or None if not resolved
        """
        market = await self.get_market(ticker)

        if not market.is_resolved():
            return None

        return {
            "ticker": market.ticker,
            "resolution": market.resolution,
            "resolution_value": market.resolution_value,
            "market_type": market.market_type,
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
