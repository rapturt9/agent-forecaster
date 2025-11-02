"""Script to collect Kalshi markets into a local dataset for benchmarking."""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

from src.data.kalshi import KalshiClient


async def collect_kalshi_dataset(
    output_file: str = "dataset/kalshi_markets.json",
    limit: int = 20,
    status: str = "open",
):
    """Collect Kalshi markets and save to JSON dataset.

    Args:
        output_file: Path to save dataset
        limit: Number of markets to collect
        status: Market status filter
    """
    print(f"Collecting {limit} Kalshi markets...")

    async with KalshiClient() as kalshi:
        markets = await kalshi.get_markets(limit=limit, status=status)

        dataset = {
            "collected_at": datetime.now().isoformat(),
            "total_markets": len(markets),
            "markets": []
        }

        for market in markets:
            market_data = {
                "ticker": market.ticker,
                "title": market.title,
                "question": market.question,
                "market_type": market.market_type,
                "status": market.status,
                "category": market.category,
                "close_time": market.close_time.isoformat() if market.close_time else None,
                "expiration_time": market.expiration_time.isoformat() if market.expiration_time else None,
                "resolution": market.resolution,
                "resolution_value": market.resolution_value,
                "is_active": market.is_active(),
                "is_resolved": market.is_resolved(),
            }

            # Add range for numerical markets
            if market.market_type == "numerical":
                market_data["min_value"] = market.min_value
                market_data["max_value"] = market.max_value

            dataset["markets"].append(market_data)
            print(f"  ✓ {market.ticker}: {market.title[:60]}")

        # Save to file
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(dataset, f, indent=2)

        print(f"\nDataset saved to: {output_file}")
        print(f"Total markets: {len(markets)}")
        print(f"Active: {sum(1 for m in markets if m.is_active())}")
        print(f"Resolved: {sum(1 for m in markets if m.is_resolved())}")

        return dataset


if __name__ == "__main__":
    asyncio.run(collect_kalshi_dataset())
