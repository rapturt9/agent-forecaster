"""BTC 5-min direction backtest on REAL historical price data.

Uses CoinGecko 5-min price data. For each prediction window, the
forecaster sees the prior 1 hour (12 candles) of price action and
predicts whether the next 5-min candle will go up or down.

Forecaster strategies use real technical signals:
  - Momentum (trend of last N candles)
  - Mean reversion (oversold/overbought)
  - Volatility breakout
  - Volume-weighted momentum (uses volume data)
  - Ensemble of all signals

Outputs a table with real timestamps, predictions, reasoning, and Brier scores.
"""

import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.scorer import brier_score, log_score


# ---------------------------------------------------------------------------
# Load real data
# ---------------------------------------------------------------------------

@dataclass
class Candle:
    timestamp: datetime
    price: float
    volume: float


def load_real_data() -> tuple[list[Candle], list[Candle]]:
    """Load real BTC data from CoinGecko JSON files.

    Returns:
        (price_candles_5m, volume_candles_hourly)
    """
    data_dir = Path(__file__).parent.parent / "data"

    # 5-min prices (1 day)
    with open(data_dir / "btc_1d.json") as f:
        d1 = json.load(f)

    prices_5m = []
    for p in d1["prices"]:
        prices_5m.append(Candle(
            timestamp=datetime.fromtimestamp(p[0] / 1000),
            price=p[1],
            volume=0.0,
        ))

    # Merge volume data if available
    volumes = d1.get("total_volumes", [])
    vol_by_ts = {}
    for v in volumes:
        ts_key = int(v[0] / (5 * 60 * 1000))  # 5-min bucket
        vol_by_ts[ts_key] = v[1]

    for c in prices_5m:
        ts_key = int(c.timestamp.timestamp() / (5 * 60))
        c.volume = vol_by_ts.get(ts_key, 0.0)

    return prices_5m


# ---------------------------------------------------------------------------
# Technical signal forecasters
# ---------------------------------------------------------------------------

def calc_returns(candles: list[Candle]) -> list[float]:
    """Calculate sequential returns."""
    returns = []
    for i in range(1, len(candles)):
        r = (candles[i].price - candles[i - 1].price) / candles[i - 1].price
        returns.append(r)
    return returns


def calc_rsi(returns: list[float], period: int = 12) -> float:
    """Calculate RSI from returns."""
    if len(returns) < period:
        return 50.0
    recent = returns[-period:]
    gains = [r for r in recent if r > 0]
    losses = [-r for r in recent if r < 0]
    avg_gain = sum(gains) / period if gains else 0.0001
    avg_loss = sum(losses) / period if losses else 0.0001
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_ema(values: list[float], span: int) -> float:
    """Calculate EMA of a list."""
    if not values:
        return 0.0
    alpha = 2 / (span + 1)
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return ema


def forecast_momentum(history: list[Candle]) -> tuple[float, str]:
    """Momentum: trend strength of last 12 candles."""
    returns = calc_returns(history)
    if len(returns) < 3:
        return 0.50, "insufficient data"

    # Weighted recent returns (more weight on recent)
    weights = [i + 1 for i in range(len(returns))]
    total_w = sum(weights)
    weighted_return = sum(r * w for r, w in zip(returns, weights)) / total_w

    # Map to probability: positive return -> higher P(up)
    # Scale factor tuned to 5-min BTC vol (~0.2%)
    signal = weighted_return / 0.002  # normalize
    signal = max(-2, min(2, signal))  # clip
    prob = 0.50 + signal * 0.15  # map to [0.20, 0.80]
    prob = max(0.15, min(0.85, prob))

    direction = "bullish" if weighted_return > 0 else "bearish"
    reason = f"weighted 1h return={weighted_return*100:.4f}%, {direction} momentum"
    return prob, reason


def forecast_mean_reversion(history: list[Candle]) -> tuple[float, str]:
    """Mean reversion: RSI-based overbought/oversold."""
    returns = calc_returns(history)
    rsi = calc_rsi(returns)

    # RSI > 70 = overbought -> predict down
    # RSI < 30 = oversold -> predict up
    # RSI ~50 = neutral
    if rsi > 70:
        prob = 0.30 + (100 - rsi) / 100  # more overbought -> lower prob
        reason = f"RSI={rsi:.1f} overbought, expecting pullback"
    elif rsi < 30:
        prob = 0.70 - rsi / 100  # more oversold -> higher prob
        reason = f"RSI={rsi:.1f} oversold, expecting bounce"
    else:
        # Near neutral, slight mean reversion
        deviation = (rsi - 50) / 50  # -1 to 1
        prob = 0.50 - deviation * 0.10
        reason = f"RSI={rsi:.1f} neutral, slight mean-reversion signal"

    prob = max(0.15, min(0.85, prob))
    return prob, reason


def forecast_volatility_breakout(history: list[Candle]) -> tuple[float, str]:
    """Volatility breakout: high vol + direction = continuation."""
    returns = calc_returns(history)
    if len(returns) < 6:
        return 0.50, "insufficient data"

    recent_3 = returns[-3:]
    older = returns[:-3]

    recent_vol = (sum(r**2 for r in recent_3) / len(recent_3)) ** 0.5
    older_vol = (sum(r**2 for r in older) / len(older)) ** 0.5 if older else recent_vol

    vol_ratio = recent_vol / older_vol if older_vol > 0 else 1.0
    recent_direction = sum(recent_3) / len(recent_3)

    if vol_ratio > 1.5:
        # Volatility expanding -> trend continuation
        signal = 0.12 if recent_direction > 0 else -0.12
        reason = f"vol expansion ({vol_ratio:.2f}x), {'bullish' if recent_direction > 0 else 'bearish'} breakout"
    elif vol_ratio < 0.5:
        # Volatility contracting -> squeeze, predict breakout in direction of slight lean
        signal = 0.05 if recent_direction > 0 else -0.05
        reason = f"vol squeeze ({vol_ratio:.2f}x), anticipating breakout"
    else:
        signal = recent_direction / 0.003 * 0.05
        reason = f"normal vol ({vol_ratio:.2f}x), weak directional signal"

    prob = 0.50 + max(-0.25, min(0.25, signal))
    prob = max(0.15, min(0.85, prob))
    return prob, reason


def forecast_ema_crossover(history: list[Candle]) -> tuple[float, str]:
    """EMA crossover: fast EMA vs slow EMA."""
    prices = [c.price for c in history]
    if len(prices) < 8:
        return 0.50, "insufficient data"

    ema_fast = calc_ema(prices, 4)   # ~20 min
    ema_slow = calc_ema(prices, 12)  # ~60 min

    spread = (ema_fast - ema_slow) / ema_slow
    signal = spread / 0.001  # normalize by typical spread
    signal = max(-2, min(2, signal))

    prob = 0.50 + signal * 0.12
    prob = max(0.15, min(0.85, prob))

    position = "above" if ema_fast > ema_slow else "below"
    reason = f"EMA4 {position} EMA12, spread={spread*100:.4f}%"
    return prob, reason


def forecast_ensemble(history: list[Candle]) -> tuple[float, str]:
    """Ensemble: weighted average of all signals."""
    p_mom, r_mom = forecast_momentum(history)
    p_mr, r_mr = forecast_mean_reversion(history)
    p_vb, r_vb = forecast_volatility_breakout(history)
    p_ema, r_ema = forecast_ema_crossover(history)

    # Weight by typical reliability
    weights = {
        "momentum": 0.30,
        "mean_reversion": 0.25,
        "vol_breakout": 0.20,
        "ema_cross": 0.25,
    }
    prob = (
        p_mom * weights["momentum"]
        + p_mr * weights["mean_reversion"]
        + p_vb * weights["vol_breakout"]
        + p_ema * weights["ema_cross"]
    )
    prob = max(0.15, min(0.85, prob))

    reason = f"ensemble: mom={p_mom:.2f} mr={p_mr:.2f} vb={p_vb:.2f} ema={p_ema:.2f}"
    return prob, reason


FORECASTERS = {
    "momentum": forecast_momentum,
    "mean_reversion": forecast_mean_reversion,
    "vol_breakout": forecast_volatility_breakout,
    "ema_crossover": forecast_ema_crossover,
    "ensemble": forecast_ensemble,
}


# ---------------------------------------------------------------------------
# Backtest runner
# ---------------------------------------------------------------------------

@dataclass
class PredictionRow:
    timestamp: str
    start_price: str
    end_price: str
    actual: str
    pct_change: str
    forecast_prob: str
    predicted: str
    correct: str
    brier: str
    reasoning: str


def run_backtest(candles: list[Candle], forecaster_name: str, lookback: int = 12):
    """Run backtest on real data.

    Args:
        candles: List of 5-min candles
        forecaster_name: Which forecaster to use
        lookback: Number of candles to look back (12 = 1 hour)
    """
    forecaster = FORECASTERS[forecaster_name]
    rows: list[PredictionRow] = []
    brier_scores = []
    log_scores = []
    correct_count = 0

    # Start predicting after we have enough history
    for i in range(lookback, len(candles) - 1):
        history = candles[i - lookback:i]
        current = candles[i]
        next_candle = candles[i + 1]

        went_up = next_candle.price > current.price
        pct_change = ((next_candle.price - current.price) / current.price) * 100

        prob, reason = forecaster(history)
        predicted_up = prob > 0.50

        bs = brier_score(prob, went_up)
        ls = log_score(prob, went_up)
        is_correct = predicted_up == went_up

        brier_scores.append(bs)
        log_scores.append(ls)
        if is_correct:
            correct_count += 1

        rows.append(PredictionRow(
            timestamp=current.timestamp.strftime("%Y-%m-%d %H:%M"),
            start_price=f"${current.price:,.2f}",
            end_price=f"${next_candle.price:,.2f}",
            actual="UP" if went_up else "DOWN",
            pct_change=f"{pct_change:+.4f}%",
            forecast_prob=f"{prob:.3f}",
            predicted="UP" if predicted_up else "DOWN",
            correct="Y" if is_correct else "N",
            brier=f"{bs:.4f}",
            reasoning=reason,
        ))

    n = len(rows)
    avg_brier = sum(brier_scores) / n if n else 0
    avg_log = sum(log_scores) / n if n else 0
    accuracy = correct_count / n if n else 0

    return rows, avg_brier, avg_log, accuracy


def print_table(rows: list[PredictionRow], forecaster_name: str, avg_brier: float, avg_log: float, accuracy: float):
    """Print results as a formatted table."""
    print(f"\n{'='*140}")
    print(f"  FORECASTER: {forecaster_name.upper()}  |  Predictions: {len(rows)}  |  Brier: {avg_brier:.4f}  |  LogScore: {avg_log:.4f}  |  Accuracy: {accuracy:.1%}")
    print(f"{'='*140}")
    print(f"  {'Timestamp':<18} {'Start':>12} {'End':>12} {'Change':>10} {'Actual':>6} {'P(up)':>7} {'Pred':>6} {'OK':>3} {'Brier':>7}  Reasoning")
    print(f"  {'-'*17} {'-'*12} {'-'*12} {'-'*10} {'-'*6} {'-'*7} {'-'*6} {'-'*3} {'-'*7}  {'-'*40}")

    for r in rows:
        print(f"  {r.timestamp:<18} {r.start_price:>12} {r.end_price:>12} {r.pct_change:>10} {r.actual:>6} {r.forecast_prob:>7} {r.predicted:>6} {r.correct:>3} {r.brier:>7}  {r.reasoning[:55]}")


def save_results(all_results: dict, output_dir: Path) -> Path:
    """Save all results to JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"backtest_real_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filepath, "w") as f:
        json.dump(all_results, f, indent=2)
    return filepath


def main():
    import argparse
    parser = argparse.ArgumentParser(description="BTC 5-min real data backtest")
    parser.add_argument("--forecaster", choices=list(FORECASTERS.keys()) + ["all"], default="all")
    parser.add_argument("--lookback", type=int, default=12, help="Lookback candles (12=1hr)")
    args = parser.parse_args()

    print("Loading real BTC 5-min price data...")
    candles = load_real_data()
    print(f"  Loaded {len(candles)} candles")
    print(f"  Range: {candles[0].timestamp} to {candles[-1].timestamp}")
    print(f"  Price: ${candles[0].price:,.2f} -> ${candles[-1].price:,.2f}")

    n_up = sum(1 for i in range(len(candles) - 1) if candles[i + 1].price > candles[i].price)
    n_total = len(candles) - 1
    print(f"  Base rate: {n_up}/{n_total} up ({n_up/n_total:.1%})")

    forecasters_to_run = list(FORECASTERS.keys()) if args.forecaster == "all" else [args.forecaster]

    all_results = {
        "data_range": f"{candles[0].timestamp} to {candles[-1].timestamp}",
        "num_candles": len(candles),
        "lookback": args.lookback,
        "base_rate_up": n_up / n_total,
        "forecasters": {},
    }

    comparison = []

    for name in forecasters_to_run:
        rows, avg_brier, avg_log, accuracy = run_backtest(candles, name, args.lookback)
        print_table(rows, name, avg_brier, avg_log, accuracy)

        comparison.append((name, avg_brier, avg_log, accuracy, len(rows)))

        all_results["forecasters"][name] = {
            "avg_brier": round(avg_brier, 6),
            "avg_log_score": round(avg_log, 6),
            "direction_accuracy": round(accuracy, 4),
            "num_predictions": len(rows),
            "predictions": [
                {
                    "timestamp": r.timestamp,
                    "start_price": r.start_price,
                    "end_price": r.end_price,
                    "actual": r.actual,
                    "pct_change": r.pct_change,
                    "forecast_prob": r.forecast_prob,
                    "predicted": r.predicted,
                    "correct": r.correct,
                    "brier": r.brier,
                    "reasoning": r.reasoning,
                } for r in rows
            ],
        }

    # Comparison table
    print(f"\n\n{'='*90}")
    print(f"  COMPARISON (lower Brier = better, 0.25 = random)")
    print(f"{'='*90}")
    print(f"  {'Forecaster':<22} {'Predictions':>12} {'Brier':>10} {'LogScore':>10} {'Accuracy':>10}")
    print(f"  {'-'*22} {'-'*12} {'-'*10} {'-'*10} {'-'*10}")
    for name, bs, ls, acc, n in sorted(comparison, key=lambda x: x[1]):
        marker = " <-- best" if bs == min(c[1] for c in comparison) else ""
        print(f"  {name:<22} {n:>12} {bs:>10.4f} {ls:>10.4f} {acc:>9.1%}{marker}")
    print(f"  {'random baseline':<22} {'':>12} {'0.2500':>10} {'-0.6931':>10} {'50.0%':>10}")

    # Save
    output_dir = Path("forecasts/backtests")
    filepath = save_results(all_results, output_dir)
    print(f"\n  Results saved to: {filepath}")


if __name__ == "__main__":
    main()
