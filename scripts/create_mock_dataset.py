"""Create a mock dataset for testing without Kalshi API."""

import json
from pathlib import Path
from datetime import datetime, timedelta


def create_mock_dataset(output_file: str = "dataset/mock_markets.json"):
    """Create mock Kalshi-like markets for testing."""

    # Create some realistic forecasting questions
    markets = [
        {
            "ticker": "MOCK-BTC-100K",
            "title": "Bitcoin to reach $100K by end of 2024",
            "question": "Will Bitcoin (BTC) reach $100,000 by December 31, 2024?",
            "market_type": "binary",
            "status": "open",
            "category": "Crypto",
            "close_time": (datetime.now() + timedelta(days=30)).isoformat(),
            "expiration_time": (datetime.now() + timedelta(days=35)).isoformat(),
            "resolution": None,
            "resolution_value": None,
            "is_active": True,
            "is_resolved": False,
        },
        {
            "ticker": "MOCK-AI-BREAKTHROUGH",
            "title": "Major AI breakthrough announced in 2024",
            "question": "Will a major AI research lab announce a significant breakthrough in Q1 2025?",
            "market_type": "binary",
            "status": "open",
            "category": "Technology",
            "close_time": (datetime.now() + timedelta(days=45)).isoformat(),
            "expiration_time": (datetime.now() + timedelta(days=50)).isoformat(),
            "resolution": None,
            "resolution_value": None,
            "is_active": True,
            "is_resolved": False,
        },
        {
            "ticker": "MOCK-FED-RATE",
            "title": "Fed interest rate decision",
            "question": "Will the Federal Reserve cut interest rates in the next meeting?",
            "market_type": "binary",
            "status": "open",
            "category": "Economics",
            "close_time": (datetime.now() + timedelta(days=20)).isoformat(),
            "expiration_time": (datetime.now() + timedelta(days=25)).isoformat(),
            "resolution": None,
            "resolution_value": None,
            "is_active": True,
            "is_resolved": False,
        },
        {
            "ticker": "MOCK-CLIMATE-TEMP",
            "title": "Global temperature anomaly",
            "question": "What will be the global temperature anomaly in 2024?",
            "market_type": "numerical",
            "status": "open",
            "category": "Climate",
            "close_time": (datetime.now() + timedelta(days=60)).isoformat(),
            "expiration_time": (datetime.now() + timedelta(days=65)).isoformat(),
            "resolution": None,
            "resolution_value": None,
            "is_active": True,
            "is_resolved": False,
            "min_value": 0.5,
            "max_value": 2.0,
        },
        {
            "ticker": "MOCK-ELECTION",
            "title": "US Presidential Election outcome",
            "question": "Will the incumbent party win the 2024 US Presidential election?",
            "market_type": "binary",
            "status": "open",
            "category": "Politics",
            "close_time": (datetime.now() + timedelta(days=90)).isoformat(),
            "expiration_time": (datetime.now() + timedelta(days=95)).isoformat(),
            "resolution": None,
            "resolution_value": None,
            "is_active": True,
            "is_resolved": False,
        },
    ]

    dataset = {
        "collected_at": datetime.now().isoformat(),
        "total_markets": len(markets),
        "source": "mock",
        "markets": markets,
    }

    # Save to file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(dataset, f, indent=2)

    print(f"Mock dataset created: {output_file}")
    print(f"Total markets: {len(markets)}")
    for market in markets:
        print(f"  • {market['ticker']}: {market['title']}")

    return dataset


if __name__ == "__main__":
    create_mock_dataset()
