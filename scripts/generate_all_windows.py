#!/usr/bin/env python3
"""Generate all 276 prediction windows from the full 289-candle BTC dataset."""
import json
import os
from datetime import datetime

DATA_PATH = "/home/user/agent-forecaster/data/btc_1d.json"
OUT_DIR = "/home/user/agent-forecaster/data/all_windows"
PROMPT_DIR = "/home/user/agent-forecaster/data/all_prompts"
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(PROMPT_DIR, exist_ok=True)

with open(DATA_PATH) as f:
    data = json.load(f)

prices = data['prices']
LOOKBACK = 12  # 12 candles of history
STRIDE = 1

windows = []
for i in range(len(prices) - LOOKBACK - 1):
    history = prices[i:i + LOOKBACK]
    current = prices[i + LOOKBACK]
    target = prices[i + LOOKBACK + 1]

    current_price = current[1]
    next_price = target[1]
    went_up = next_price > current_price
    pct_change = (next_price - current_price) / current_price * 100

    current_time = datetime.utcfromtimestamp(current[0] / 1000).strftime('%Y-%m-%d %H:%M')
    next_time = datetime.utcfromtimestamp(target[0] / 1000).strftime('%Y-%m-%d %H:%M')

    w = {
        'id': i,
        'history': [{'ts': h[0], 'time': datetime.utcfromtimestamp(h[0]/1000).strftime('%Y-%m-%d %H:%M'), 'price': h[1]} for h in history],
        'current_price': current_price,
        'current_time': current_time,
        'next_price': next_price,
        'next_time': next_time,
        'went_up': went_up,
        'pct_change': pct_change
    }
    windows.append(w)

    # Build prompt text
    lines = []
    prev_price = None
    for h in history:
        t = datetime.utcfromtimestamp(h[0] / 1000).strftime('%Y-%m-%d %H:%M')
        p = h[1]
        if prev_price is not None:
            delta = p - prev_price
            sign = '+' if delta >= 0 else ''
            lines.append(f"{t} | ${p:,.2f}  ({sign}${delta:,.2f})")
        else:
            lines.append(f"{t} | ${p:,.2f}")
        prev_price = p
    lines.append("")
    lines.append(f"CURRENT PRICE: ${current_price:,.2f} at {current_time}")

    prompt_path = os.path.join(PROMPT_DIR, f"prompt_{i:03d}.txt")
    with open(prompt_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

# Save ground truth
gt_path = os.path.join(OUT_DIR, "ground_truth.json")
with open(gt_path, 'w') as f:
    json.dump(windows, f, indent=2)

up_count = sum(1 for w in windows if w['went_up'])
down_count = len(windows) - up_count
print(f"Generated {len(windows)} windows")
print(f"UP: {up_count} ({up_count/len(windows):.1%}), DOWN: {down_count} ({down_count/len(windows):.1%})")
print(f"Time range: {windows[0]['current_time']} to {windows[-1]['current_time']}")
print(f"Prompts in: {PROMPT_DIR}")
print(f"Ground truth in: {gt_path}")
