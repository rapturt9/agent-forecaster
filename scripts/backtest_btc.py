"""100-round BTC 5-min direction backtest.

Supports two modes:
  - mock: Uses baseline forecasters (no network needed) for pipeline validation
  - agent: Uses SimpleForecastingAgent with real research tools (needs API keys)

Usage:
  python scripts/backtest_btc.py --mode mock --rounds 100
  python scripts/backtest_btc.py --mode agent --rounds 100 --batch-size 10
"""

import asyncio
import json
import math
import random
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.scorer import brier_score, log_score, ForecastScorer
from src.evaluation.validator import ForecastValidator


# ---------------------------------------------------------------------------
# Synthetic BTC price data
# ---------------------------------------------------------------------------

@dataclass
class PriceWindow:
    """A single 5-min BTC price window."""
    round_num: int
    start_price: float
    end_price: float
    timestamp: str
    went_up: bool
    pct_change: float


def generate_synthetic_windows(
    n: int = 100,
    start_price: float = 87_000.0,
    volatility_pct: float = 0.3,
    seed: int | None = 42,
) -> list[PriceWindow]:
    """Generate n synthetic 5-min BTC price windows.

    Uses a geometric random walk calibrated to real BTC 5-min volatility
    (~0.2-0.4% per 5 min, slight upward drift).
    """
    if seed is not None:
        random.seed(seed)

    windows = []
    price = start_price
    ts = datetime(2026, 3, 28, 9, 0, 0)

    for i in range(n):
        # Log-normal return: slight positive drift + vol
        drift = 0.00002  # tiny upward drift per 5 min
        sigma = volatility_pct / 100
        log_return = random.gauss(drift, sigma)
        new_price = price * math.exp(log_return)

        went_up = new_price > price
        pct_change = ((new_price - price) / price) * 100

        windows.append(PriceWindow(
            round_num=i + 1,
            start_price=round(price, 2),
            end_price=round(new_price, 2),
            timestamp=ts.isoformat(),
            went_up=went_up,
            pct_change=round(pct_change, 4),
        ))

        price = new_price
        ts += timedelta(minutes=5)

    return windows


# ---------------------------------------------------------------------------
# Mock forecasters (baselines)
# ---------------------------------------------------------------------------

def forecast_random(window: PriceWindow) -> float:
    """Random baseline: always 0.50."""
    return 0.50


def forecast_always_up(window: PriceWindow) -> float:
    """Always predicts 60% up (slight bullish bias)."""
    return 0.60


def forecast_momentum(window: PriceWindow, prev_windows: list[PriceWindow]) -> float:
    """Simple momentum: if last N windows were up, predict up."""
    if len(prev_windows) < 3:
        return 0.50

    recent = prev_windows[-3:]
    ups = sum(1 for w in recent if w.went_up)
    # Map 0-3 ups to 0.35 - 0.65 probability
    return 0.35 + (ups / 3) * 0.30


def forecast_mean_reversion(window: PriceWindow, prev_windows: list[PriceWindow]) -> float:
    """Mean reversion: if price went up recently, predict down."""
    if len(prev_windows) < 3:
        return 0.50

    recent = prev_windows[-3:]
    ups = sum(1 for w in recent if w.went_up)
    # Opposite of momentum
    return 0.65 - (ups / 3) * 0.30


def forecast_volatility_adjusted(window: PriceWindow, prev_windows: list[PriceWindow]) -> float:
    """Adjusts confidence based on recent volatility."""
    if len(prev_windows) < 5:
        return 0.50

    recent = prev_windows[-5:]
    avg_abs_change = sum(abs(w.pct_change) for w in recent) / 5

    # High vol -> closer to 0.50 (less confident)
    # Low vol -> slight directional lean based on last move
    if avg_abs_change > 0.3:
        # High volatility, stay close to 50/50
        return 0.50
    else:
        # Low vol, lean with last direction
        last_up = recent[-1].went_up
        return 0.55 if last_up else 0.45


MOCK_FORECASTERS = {
    "random_50_50": forecast_random,
    "always_up_60": forecast_always_up,
    "momentum_3": None,  # needs prev_windows, handled specially
    "mean_reversion_3": None,
    "volatility_adjusted": None,
}


# ---------------------------------------------------------------------------
# Backtest engine
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    """Results from a single backtest round."""
    round_num: int
    start_price: float
    end_price: float
    went_up: bool
    pct_change: float
    forecast_prob: float
    brier: float
    log_scr: float
    direction_correct: bool
    forecaster: str
    timestamp: str


@dataclass
class BacktestSummary:
    """Aggregate backtest summary."""
    forecaster: str
    num_rounds: int
    avg_brier: float
    avg_log_score: float
    direction_accuracy: float
    calibration_error: float
    num_correct: int
    num_wrong: int
    avg_confidence: float
    results: list[dict] = field(default_factory=list)


def run_mock_backtest(
    windows: list[PriceWindow],
    forecaster_name: str,
) -> BacktestSummary:
    """Run backtest with a mock forecaster."""
    validator = ForecastValidator()
    results: list[BacktestResult] = []

    for i, w in enumerate(windows):
        prev = windows[:i]

        # Get forecast
        if forecaster_name == "random_50_50":
            prob = forecast_random(w)
        elif forecaster_name == "always_up_60":
            prob = forecast_always_up(w)
        elif forecaster_name == "momentum_3":
            prob = forecast_momentum(w, prev)
        elif forecaster_name == "mean_reversion_3":
            prob = forecast_mean_reversion(w, prev)
        elif forecaster_name == "volatility_adjusted":
            prob = forecast_volatility_adjusted(w, prev)
        else:
            prob = 0.50

        prob = max(0.01, min(0.99, prob))

        bs = brier_score(prob, w.went_up)
        ls = log_score(prob, w.went_up)
        direction_correct = (prob > 0.5) == w.went_up or (prob == 0.5)

        validator.validate_against_outcome(prob, w.went_up)

        results.append(BacktestResult(
            round_num=w.round_num,
            start_price=w.start_price,
            end_price=w.end_price,
            went_up=w.went_up,
            pct_change=w.pct_change,
            forecast_prob=prob,
            brier=bs,
            log_scr=ls,
            direction_correct=direction_correct,
            forecaster=forecaster_name,
            timestamp=w.timestamp,
        ))

    n = len(results)
    perf = validator.get_performance_summary()
    cal_err = perf.get("calibration", {}).get("calibration_error", 0.0)

    return BacktestSummary(
        forecaster=forecaster_name,
        num_rounds=n,
        avg_brier=sum(r.brier for r in results) / n,
        avg_log_score=sum(r.log_scr for r in results) / n,
        direction_accuracy=sum(r.direction_correct for r in results) / n,
        calibration_error=float(cal_err),
        num_correct=sum(r.direction_correct for r in results),
        num_wrong=sum(not r.direction_correct for r in results),
        avg_confidence=sum(abs(r.forecast_prob - 0.5) for r in results) / n,
        results=[asdict(r) for r in results],
    )


def print_summary(s: BacktestSummary) -> None:
    """Print a single forecaster's summary."""
    print(f"\n  {s.forecaster}")
    print(f"    Brier Score:        {s.avg_brier:.4f}  (0=perfect, 0.25=random)")
    print(f"    Log Score:          {s.avg_log_score:.4f}")
    print(f"    Direction Accuracy: {s.direction_accuracy:.1%}  ({s.num_correct}/{s.num_rounds})")
    print(f"    Calibration Error:  {s.calibration_error:.4f}")
    print(f"    Avg Confidence:     {s.avg_confidence:.4f}  (distance from 0.50)")


def run_all_mock_backtests(rounds: int = 100) -> list[BacktestSummary]:
    """Run all mock forecasters and return summaries."""
    windows = generate_synthetic_windows(n=rounds)

    # Stats on the synthetic data
    n_up = sum(w.went_up for w in windows)
    n_down = rounds - n_up
    avg_abs = sum(abs(w.pct_change) for w in windows) / rounds

    print(f"\n{'='*70}")
    print(f"  BTC 5-MIN DIRECTION BACKTEST ({rounds} rounds)")
    print(f"{'='*70}")
    print(f"\n  Data: Synthetic geometric random walk")
    print(f"  Start price: ${windows[0].start_price:,.2f}")
    print(f"  End price:   ${windows[-1].end_price:,.2f}")
    print(f"  Up/Down:     {n_up}/{n_down} ({n_up/rounds:.0%} up)")
    print(f"  Avg |change|: {avg_abs:.4f}%")

    forecaster_names = [
        "random_50_50",
        "always_up_60",
        "momentum_3",
        "mean_reversion_3",
        "volatility_adjusted",
    ]

    summaries = []
    for name in forecaster_names:
        s = run_mock_backtest(windows, name)
        summaries.append(s)

    # Print comparison table
    print(f"\n{'='*70}")
    print(f"  RESULTS COMPARISON")
    print(f"{'='*70}")

    print(f"\n  {'Forecaster':<25} {'Brier':>8} {'LogScr':>8} {'DirAcc':>8} {'CalErr':>8}")
    print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    for s in sorted(summaries, key=lambda x: x.avg_brier):
        print(f"  {s.forecaster:<25} {s.avg_brier:>8.4f} {s.avg_log_score:>8.4f} {s.direction_accuracy:>7.1%} {s.calibration_error:>8.4f}")

    print(f"\n  Baseline (random 50/50): Brier = 0.2500")
    print(f"  Any Brier < 0.2500 indicates skill above random chance.")

    # Individual details
    print(f"\n{'='*70}")
    print(f"  DETAILED RESULTS")
    print(f"{'='*70}")
    for s in summaries:
        print_summary(s)

    return summaries


def save_results(summaries: list[BacktestSummary], output_dir: Path) -> Path:
    """Save backtest results to JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Summary file
    summary_data = {
        "backtest": "btc_5min_direction",
        "mode": "mock",
        "timestamp": datetime.now().isoformat(),
        "num_rounds": summaries[0].num_rounds if summaries else 0,
        "forecasters": [],
    }

    for s in summaries:
        entry = {
            "name": s.forecaster,
            "avg_brier_score": round(s.avg_brier, 6),
            "avg_log_score": round(s.avg_log_score, 6),
            "direction_accuracy": round(s.direction_accuracy, 4),
            "calibration_error": round(s.calibration_error, 6),
            "num_correct": s.num_correct,
            "num_wrong": s.num_wrong,
            "rounds": s.results,
        }
        summary_data["forecasters"].append(entry)

    filepath = output_dir / f"backtest_mock_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filepath, "w") as f:
        json.dump(summary_data, f, indent=2)

    return filepath


def main():
    import argparse
    parser = argparse.ArgumentParser(description="BTC 5-min direction backtest")
    parser.add_argument("--mode", choices=["mock", "agent"], default="mock",
                        help="Forecaster mode (default: mock)")
    parser.add_argument("--rounds", type=int, default=100,
                        help="Number of rounds (default: 100)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for synthetic data (default: 42)")
    parser.add_argument("--save", action="store_true", default=True,
                        help="Save results to JSON")
    args = parser.parse_args()

    if args.mode == "mock":
        summaries = run_all_mock_backtests(rounds=args.rounds)

        if args.save:
            output_dir = Path("forecasts/backtests")
            filepath = save_results(summaries, output_dir)
            print(f"\n  Results saved to: {filepath}")
    else:
        print("Agent mode requires network access and API keys.")
        print("Run: python scripts/eval_btc_5min.py --rounds 100")
        print("Or implement agent batching in this script.")


if __name__ == "__main__":
    main()
