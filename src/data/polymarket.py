"""Polymarket API client for fetching market data and outcomes.

Uses the Gamma API (metadata/search) and CLOB API (prices).
No authentication required for read-only operations.
"""

import aiohttp
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel


GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
CLOB_BASE_URL = "https://clob.polymarket.com"


class PolymarketMarket(BaseModel):
    """Represents a Polymarket market."""

    condition_id: str
    question: str
    title: str = ""
    market_type: Literal["binary", "categorical", "numerical"] = "binary"
    status: str = "active"
    end_date: datetime | None = None
    resolved: bool = False
    outcome: str | None = None
    outcome_prices: list[float] | None = None
    tokens: list[dict[str, str]] = []
    volume: float = 0.0
    liquidity: float = 0.0
    slug: str = ""
    tags: list[str] = []

    def is_active(self) -> bool:
        return not self.resolved and self.status == "active"

    def is_resolved(self) -> bool:
        return self.resolved

    def yes_price(self) -> float | None:
        if self.outcome_prices and len(self.outcome_prices) >= 1:
            return self.outcome_prices[0]
        return None

    def no_price(self) -> float | None:
        if self.outcome_prices and len(self.outcome_prices) >= 2:
            return self.outcome_prices[1]
        return None


class PolymarketClient:
    """Client for Polymarket Gamma + CLOB APIs (read-only, no auth needed)."""

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def search_markets(
        self,
        query: str = "",
        tag: str = "",
        active: bool = True,
        closed: bool = False,
        limit: int = 20,
    ) -> list[PolymarketMarket]:
        """Search for markets via the Gamma API.

        Args:
            query: Text to search in question/title
            tag: Filter by tag (e.g., "crypto")
            active: Only active markets
            closed: Include closed markets
            limit: Max results

        Returns:
            List of PolymarketMarket objects
        """
        session = await self._get_session()

        params: dict[str, Any] = {"limit": limit}
        if query:
            params["title"] = query
        if tag:
            params["tag"] = tag
        if not closed:
            params["closed"] = "false"
        if active:
            params["active"] = "true"

        async with session.get(f"{GAMMA_BASE_URL}/markets", params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()

        markets = []
        for item in data:
            market = self._parse_market(item)
            if market:
                markets.append(market)
        return markets

    async def get_market(self, condition_id: str) -> PolymarketMarket | None:
        """Get a specific market by condition ID."""
        session = await self._get_session()

        async with session.get(f"{GAMMA_BASE_URL}/markets", params={"id": condition_id}) as resp:
            resp.raise_for_status()
            data = await resp.json()

        if isinstance(data, list) and data:
            return self._parse_market(data[0])
        elif isinstance(data, dict):
            return self._parse_market(data)
        return None

    async def get_events(
        self,
        tag: str = "",
        query: str = "",
        closed: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get events from the Gamma API."""
        session = await self._get_session()

        params: dict[str, Any] = {"limit": limit}
        if tag:
            params["tag"] = tag
        if query:
            params["title"] = query
        if not closed:
            params["closed"] = "false"

        async with session.get(f"{GAMMA_BASE_URL}/events", params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_price(self, token_id: str, side: str = "buy") -> float | None:
        """Get current price for a token from the CLOB API.

        Args:
            token_id: The token ID
            side: "buy" or "sell"

        Returns:
            Price as float (0-1), or None on error
        """
        session = await self._get_session()

        try:
            async with session.get(
                f"{CLOB_BASE_URL}/price",
                params={"token_id": token_id, "side": side},
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return float(data.get("price", 0))
        except Exception:
            return None

    async def get_midpoint(self, token_id: str) -> float | None:
        """Get midpoint price for a token."""
        session = await self._get_session()

        try:
            async with session.get(
                f"{CLOB_BASE_URL}/midpoint",
                params={"token_id": token_id},
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return float(data.get("mid", 0))
        except Exception:
            return None

    async def get_market_outcome(self, condition_id: str) -> dict[str, Any] | None:
        """Get the resolved outcome of a market.

        Returns:
            Dict with resolution info, or None if not resolved
        """
        market = await self.get_market(condition_id)
        if not market or not market.is_resolved():
            return None

        return {
            "condition_id": market.condition_id,
            "resolution": market.outcome or "unknown",
            "market_type": market.market_type,
        }

    def _parse_market(self, data: dict[str, Any]) -> PolymarketMarket | None:
        """Parse a market dict from the API into a PolymarketMarket."""
        try:
            # Parse outcome prices from JSON string
            outcome_prices = None
            raw_prices = data.get("outcomePrices")
            if raw_prices:
                import json
                if isinstance(raw_prices, str):
                    outcome_prices = [float(p) for p in json.loads(raw_prices)]
                elif isinstance(raw_prices, list):
                    outcome_prices = [float(p) for p in raw_prices]

            # Parse tokens
            tokens = []
            raw_tokens = data.get("tokens", [])
            if isinstance(raw_tokens, str):
                import json
                raw_tokens = json.loads(raw_tokens)
            for t in raw_tokens:
                if isinstance(t, dict):
                    tokens.append({
                        "token_id": str(t.get("token_id", "")),
                        "outcome": str(t.get("outcome", "")),
                    })

            # Parse end date
            end_date = None
            if data.get("endDate"):
                try:
                    end_date = datetime.fromisoformat(data["endDate"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            # Parse tags
            tags = data.get("tags", []) or []
            if isinstance(tags, str):
                import json
                try:
                    tags = json.loads(tags)
                except (json.JSONDecodeError, TypeError):
                    tags = []

            return PolymarketMarket(
                condition_id=str(data.get("conditionId", data.get("condition_id", ""))),
                question=data.get("question", data.get("title", "")),
                title=data.get("title", ""),
                status="resolved" if data.get("resolved") else "active",
                end_date=end_date,
                resolved=bool(data.get("resolved", False)),
                outcome=data.get("outcome"),
                outcome_prices=outcome_prices,
                tokens=tokens,
                volume=float(data.get("volume", 0) or 0),
                liquidity=float(data.get("liquidity", 0) or 0),
                slug=data.get("slug", ""),
                tags=tags,
            )
        except Exception:
            return None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
