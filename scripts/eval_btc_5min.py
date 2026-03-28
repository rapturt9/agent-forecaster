"""Evaluate forecasting agent on BTC 5-minute price direction.

Workflow:
1. Fetch current BTC price + Polymarket BTC market context
2. Ask the forecaster: "Will BTC be higher in 5 minutes?"
3. Wait 5 minutes
4. Fetch BTC price again
5. Score the forecast against the actual outcome

Can run multiple rounds for a more robust evaluation.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.data.crypto import fetch_btc_price
from src.data.polymarket import PolymarketClient
from src.agent.simple_forecaster import SimpleForecastingAgent
from src.evaluation.scorer import brier_score, log_score, ForecastScorer
from src.evaluation.validator import ForecastValidator


WAIT_SECONDS = 5 * 60  # 5 minutes


def build_question(price: float) -> str:
    """Build the forecasting question with current price context."""
    return (
        f"Will the price of Bitcoin (BTC/USD) be higher than ${price:,.2f} "
        f"in exactly 5 minutes from now?"
    )


def build_context(price_data: dict, polymarket_context: str = "") -> str:
    """Build context string from price data and Polymarket info."""
    parts = [
        f"Current BTC price: ${price_data['price']:,.2f}",
        f"Fetched at: {price_data['fetched_at']}",
    ]
    if price_data.get("change_24h_pct") is not None:
        parts.append(f"24h change: {price_data['change_24h_pct']:.2f}%")
    if polymarket_context:
        parts.append(f"Polymarket context: {polymarket_context}")
    return " | ".join(parts)


async def fetch_polymarket_btc_context() -> str:
    """Fetch relevant BTC markets from Polymarket for context."""
    try:
        async with PolymarketClient() as client:
            markets = await client.search_markets(query="Bitcoin", tag="crypto", limit=5)
            if not markets:
                markets = await client.search_markets(query="BTC", limit=5)

            if not markets:
                return ""

            lines = []
            for m in markets[:3]:
                yes_p = m.yes_price()
                price_str = f" (Yes: {yes_p:.0%})" if yes_p is not None else ""
                lines.append(f"- {m.question}{price_str}")
            return "Active Polymarket BTC markets: " + "; ".join(lines)
    except Exception as e:
        return f"(Polymarket fetch failed: {e})"


async def run_single_round(
    agent: SimpleForecastingAgent,
    round_num: int,
    output_dir: Path,
) -> dict | None:
    """Run a single forecast-wait-evaluate round.

    Returns:
        Result dict or None on error
    """
    print(f"\n{'='*70}")
    print(f"  ROUND {round_num}")
    print(f"{'='*70}")

    # 1. Fetch current price + Polymarket context
    print("\n[1/4] Fetching current BTC price + Polymarket context...")
    try:
        price_before, poly_ctx = await asyncio.gather(
            fetch_btc_price(),
            fetch_polymarket_btc_context(),
        )
    except Exception as e:
        print(f"  ERROR fetching data: {e}")
        return None

    start_price = price_before["price"]
    print(f"  BTC price: ${start_price:,.2f}  (source: {price_before['source']})")
    if poly_ctx:
        print(f"  Polymarket: {poly_ctx[:120]}...")

    # 2. Generate forecast
    question = build_question(start_price)
    context = build_context(price_before, poly_ctx)

    print(f"\n[2/4] Forecasting: {question}")
    try:
        forecast = await agent.forecast(
            question=question,
            question_type="binary",
            context=context,
        )
        forecast_prob = float(forecast.forecast_value)
        # Clamp to valid range
        forecast_prob = max(0.01, min(0.99, forecast_prob))
    except Exception as e:
        print(f"  ERROR generating forecast: {e}")
        import traceback
        traceback.print_exc()
        return None

    print(f"  Forecast (P(up)): {forecast_prob:.4f}")
    print(f"  Confidence: {forecast.confidence}")
    print(f"  Reasoning: {forecast.reasoning[:200]}...")

    # 3. Wait 5 minutes
    print(f"\n[3/4] Waiting {WAIT_SECONDS // 60} minutes for price to settle...")
    for remaining in range(WAIT_SECONDS, 0, -30):
        mins, secs = divmod(remaining, 60)
        print(f"  {mins}m {secs}s remaining...", end="\r")
        await asyncio.sleep(min(30, remaining))
    print(f"  Done waiting.                    ")

    # 4. Fetch new price and evaluate
    print("\n[4/4] Fetching new BTC price...")
    try:
        price_after = await fetch_btc_price()
    except Exception as e:
        print(f"  ERROR fetching price: {e}")
        return None

    end_price = price_after["price"]
    went_up = end_price > start_price
    price_change = end_price - start_price
    pct_change = (price_change / start_price) * 100

    print(f"  BTC price: ${end_price:,.2f}")
    print(f"  Change: ${price_change:+,.2f} ({pct_change:+.4f}%)")
    print(f"  Direction: {'UP' if went_up else 'DOWN' if end_price < start_price else 'FLAT'}")

    # Score
    bs = brier_score(forecast_prob, went_up)
    ls = log_score(forecast_prob, went_up)

    print(f"\n  --- Scores ---")
    print(f"  Brier Score:  {bs:.4f}  (0=perfect, 0.25=random, 1=worst)")
    print(f"  Log Score:    {ls:.4f}  (higher=better)")

    predicted_direction = "UP" if forecast_prob > 0.5 else "DOWN"
    actual_direction = "UP" if went_up else "DOWN"
    correct = predicted_direction == actual_direction
    print(f"  Predicted: {predicted_direction} | Actual: {actual_direction} | {'CORRECT' if correct else 'WRONG'}")

    # Save result
    result = {
        "round": round_num,
        "question": question,
        "forecast": forecast_prob,
        "actual_outcome": went_up,
        "start_price": start_price,
        "end_price": end_price,
        "price_change": price_change,
        "pct_change": pct_change,
        "brier_score": bs,
        "log_score": ls,
        "direction_correct": correct,
        "reasoning": forecast.reasoning[:500],
        "confidence": forecast.confidence,
        "timestamp_start": price_before["fetched_at"],
        "timestamp_end": price_after["fetched_at"],
        "metadata": {
            "wait_seconds": WAIT_SECONDS,
            "price_source": price_before["source"],
        },
    }

    output_file = output_dir / f"btc_5min_round_{round_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n  Saved: {output_file}")

    return result


async def run_evaluation(num_rounds: int = 1):
    """Run the full BTC 5-min direction evaluation."""
    print("\n" + "#" * 70)
    print("  BTC 5-Minute Direction Forecast Evaluation")
    print("#" * 70)
    print(f"\nRounds: {num_rounds}")
    print(f"Wait per round: {WAIT_SECONDS // 60} minutes")
    print(f"Total estimated time: ~{num_rounds * (WAIT_SECONDS // 60 + 2)} minutes\n")

    output_dir = Path("forecasts/btc_5min")
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    validator = ForecastValidator()

    async with SimpleForecastingAgent() as agent:
        for i in range(1, num_rounds + 1):
            result = await run_single_round(agent, i, output_dir)
            if result:
                results.append(result)

                # Also feed into the validator for aggregate stats
                validator.validate_against_outcome(
                    forecast_prob=result["forecast"],
                    outcome=result["actual_outcome"],
                    question=result["question"],
                    metadata=result["metadata"],
                )

            # Brief pause between rounds
            if i < num_rounds:
                print("\n  Pausing 5s before next round...")
                await asyncio.sleep(5)

    # Print summary
    print("\n\n" + "=" * 70)
    print("  EVALUATION SUMMARY")
    print("=" * 70)

    if not results:
        print("\n  No successful rounds. Check errors above.")
        return

    n = len(results)
    avg_brier = sum(r["brier_score"] for r in results) / n
    avg_log = sum(r["log_score"] for r in results) / n
    direction_accuracy = sum(r["direction_correct"] for r in results) / n
    avg_pct_change = sum(abs(r["pct_change"]) for r in results) / n

    print(f"\n  Rounds completed:      {n}/{num_rounds}")
    print(f"  Avg Brier Score:       {avg_brier:.4f}  (0=perfect, 0.25=random)")
    print(f"  Avg Log Score:         {avg_log:.4f}")
    print(f"  Direction Accuracy:    {direction_accuracy:.1%}  ({sum(r['direction_correct'] for r in results)}/{n})")
    print(f"  Avg |Price Change|:    {avg_pct_change:.4f}%")

    # Calibration from validator
    perf = validator.get_performance_summary()
    if perf.get("calibration", {}).get("calibration_error") is not None:
        print(f"  Calibration Error:     {perf['calibration']['calibration_error']:.4f}")

    print(f"\n  Results saved to: {output_dir}/")

    # Save summary
    summary = {
        "evaluation": "btc_5min_direction",
        "num_rounds": num_rounds,
        "completed_rounds": n,
        "avg_brier_score": avg_brier,
        "avg_log_score": avg_log,
        "direction_accuracy": direction_accuracy,
        "avg_abs_pct_change": avg_pct_change,
        "results": results,
        "timestamp": datetime.now().isoformat(),
    }

    summary_file = output_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Summary saved to: {summary_file}")


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="BTC 5-min direction forecast evaluation")
    parser.add_argument("-n", "--rounds", type=int, default=1, help="Number of evaluation rounds (default: 1)")
    parser.add_argument("--wait", type=int, default=300, help="Wait time in seconds between price checks (default: 300)")
    args = parser.parse_args()

    global WAIT_SECONDS
    WAIT_SECONDS = args.wait

    asyncio.run(run_evaluation(num_rounds=args.rounds))


if __name__ == "__main__":
    main()
