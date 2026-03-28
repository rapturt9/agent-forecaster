#!/usr/bin/env python3
"""Simulate Kelly criterion betting on ensemble predictions."""
import json
import math

RESULTS_PATH = "/home/user/agent-forecaster/data/ensemble_results.json"
GT_PATH = "/home/user/agent-forecaster/data/all_windows/ground_truth.json"

with open(RESULTS_PATH) as f:
    results = json.load(f)

with open(GT_PATH) as f:
    ground_truth = json.load(f)
gt_map = {w['id']: w for w in ground_truth}

details = results['details']

# Sort by window ID (chronological)
details.sort(key=lambda x: x['window'])

# === KELLY CRITERION SIMULATION ===
# For a binary bet with probability p of winning, odds b:1
# Kelly fraction f* = (bp - q) / b where q = 1-p
# For a fair bet (b=1): f* = 2p - 1
# For BTC: we're betting on direction with the pct_change as payoff

print("=" * 70)
print("KELLY CRITERION P&L SIMULATION")
print("=" * 70)

# Strategy 1: Bet on ALL predictions
# Strategy 2: Bet only on high-confidence (agreement >= 0.8, prob >= 0.6)
# Strategy 3: Bet only on unanimous (agreement == 1.0)

for strategy_name, filter_fn in [
    ("ALL predictions", lambda d: True),
    ("High-confidence (>=80% agreement, >=60% prob)", lambda d: d['agreement'] >= 0.8 and d['final_prob'] >= 0.60),
    ("Unanimous (100% agreement)", lambda d: d['agreement'] == 1.0),
]:
    print(f"\n{'='*70}")
    print(f"Strategy: {strategy_name}")
    print(f"{'='*70}")

    bankroll = 10000.0  # Start with $10k
    initial = bankroll
    trades = 0
    wins = 0
    max_bankroll = bankroll
    max_drawdown = 0
    daily_pnl = {}  # group by hour blocks

    for d in details:
        if not filter_fn(d):
            continue

        wid = d['window']
        if wid not in gt_map:
            continue

        gt = gt_map[wid]
        pct_change = abs(gt['pct_change']) / 100.0  # Convert to decimal

        # Kelly: estimated edge
        p = d['final_prob']  # our estimated win probability
        q = 1.0 - p

        # For a bet where we win/lose proportional to pct_change
        # Odds b = pct_change payoff (symmetric)
        # Kelly f* = (b*p - q) / b = p - q/b
        # For simplicity, treat as binary bet with odds 1:1
        # f* = 2p - 1

        kelly_fraction = 2 * p - 1
        if kelly_fraction <= 0:
            continue  # No edge, skip

        # Use half-Kelly for safety
        bet_fraction = kelly_fraction * 0.5
        bet_size = bankroll * bet_fraction

        # Did we win?
        won = d['correct']
        if won:
            # Win: gain proportional to actual price move
            profit = bet_size * pct_change * 20  # 20x leverage (typical BTC futures)
            bankroll += profit
            wins += 1
        else:
            # Lose: lose proportional to actual price move
            loss = bet_size * pct_change * 20
            bankroll -= loss

        trades += 1
        max_bankroll = max(max_bankroll, bankroll)
        drawdown = (max_bankroll - bankroll) / max_bankroll
        max_drawdown = max(max_drawdown, drawdown)

        # Track by time block (every ~2 hours = 24 windows)
        time_block = gt.get('current_time', '')[:13]  # YYYY-MM-DD HH
        if time_block not in daily_pnl:
            daily_pnl[time_block] = bankroll

    # Final stats
    total_return = (bankroll - initial) / initial * 100
    print(f"Starting bankroll: ${initial:,.2f}")
    print(f"Final bankroll:    ${bankroll:,.2f}")
    print(f"Total return:      {total_return:+.2f}%")
    print(f"Trades taken:      {trades}")
    print(f"Win rate:          {wins/trades:.1%}" if trades > 0 else "N/A")
    print(f"Max drawdown:      {max_drawdown:.1%}")

    if daily_pnl:
        print(f"\nEquity curve by hour:")
        for t, b in sorted(daily_pnl.items()):
            bar = "█" * int((b / initial) * 20)
            print(f"  {t}: ${b:>10,.2f} {bar}")

print("\n" + "=" * 70)
print("IMPORTANT CAVEATS")
print("=" * 70)
print("""
1. This is a SINGLE DAY backtest on 24h of data - far too little to be confident
2. Adjacent windows overlap heavily (stride=1), so trades are NOT independent
3. Real-world: slippage, fees, latency would eat into edge
4. The 73% high-confidence accuracy may not persist out-of-sample
5. BTC 5-min direction is widely believed to be unpredictable (EMH)
6. This could be overfitting to one particular day's price action
7. Need months of out-of-sample testing before any real deployment
""")

# Independence-adjusted significance
print("=" * 70)
print("INDEPENDENCE-ADJUSTED ANALYSIS")
print("=" * 70)
print("""
With stride=1, adjacent windows share 11/12 candles.
Effective independent samples ≈ N / 12 ≈ 276/12 ≈ 23 independent windows.

For the high-confidence subset (111 predictions, 73% accuracy):
  Effective independent N ≈ 111/12 ≈ 9 predictions
  With 73% accuracy on 9 independent trials: p ≈ 0.09 (NOT significant)

For unanimous subset (142 predictions, 69.7% accuracy):
  Effective independent N ≈ 142/12 ≈ 12 predictions
  With 70% accuracy on 12 independent trials: p ≈ 0.07 (NOT significant)

CONCLUSION: The statistical significance is INFLATED by overlapping windows.
True significance requires non-overlapping (stride=12) evaluation.
""")
