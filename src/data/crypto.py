"""Cryptocurrency price data fetcher using free public APIs."""

import aiohttp
from datetime import datetime
from typing import Any


async def get_btc_price() -> dict[str, Any]:
    """Fetch current BTC/USD price from CoinGecko (no API key needed).

    Returns:
        Dict with price, timestamp, and source info
    """
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_last_updated_at": "true",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json()

    btc_data = data["bitcoin"]
    return {
        "price": btc_data["usd"],
        "change_24h_pct": btc_data.get("usd_24h_change"),
        "last_updated": datetime.fromtimestamp(btc_data["last_updated_at"]).isoformat(),
        "fetched_at": datetime.now().isoformat(),
        "source": "coingecko",
    }


async def get_btc_price_fallback() -> dict[str, Any]:
    """Fallback BTC price fetcher using CoinCap API.

    Returns:
        Dict with price, timestamp, and source info
    """
    url = "https://api.coincap.io/v2/assets/bitcoin"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()

    btc_data = data["data"]
    return {
        "price": float(btc_data["priceUsd"]),
        "change_24h_pct": float(btc_data["changePercent24Hr"]),
        "fetched_at": datetime.now().isoformat(),
        "source": "coincap",
    }


async def fetch_btc_price() -> dict[str, Any]:
    """Fetch BTC price with fallback.

    Tries CoinGecko first, falls back to CoinCap.

    Returns:
        Dict with price info
    """
    try:
        return await get_btc_price()
    except Exception:
        return await get_btc_price_fallback()
