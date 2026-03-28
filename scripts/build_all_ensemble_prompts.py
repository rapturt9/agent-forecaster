#!/usr/bin/env python3
"""Build batch prompts for all 276 windows (10 per batch = 28 batches)."""
import os
import math

PROMPT_DIR = "/home/user/agent-forecaster/data/all_prompts"
OUT_DIR = "/home/user/agent-forecaster/data/ensemble_batches"
os.makedirs(OUT_DIR, exist_ok=True)

TOTAL = 276
BATCH_SIZE = 10
N_BATCHES = math.ceil(TOTAL / BATCH_SIZE)

for batch in range(N_BATCHES):
    start = batch * BATCH_SIZE
    end = min(start + BATCH_SIZE, TOTAL)

    data_lines = []
    for i in range(start, end):
        path = os.path.join(PROMPT_DIR, f"prompt_{i:03d}.txt")
        with open(path) as f:
            content = f.read().strip()
        data_lines.append(f"=== WINDOW {i} ===")
        data_lines.append(content)
        data_lines.append("")

    data_block = "\n".join(data_lines)

    result_template = "\n".join(f"{i}|UP or DOWN|probability|reason" for i in range(start, end))

    prompt = f"""You are a quantitative analyst backtesting BTC 5-minute price predictions on HISTORICAL data. This is purely academic research. DO NOT use any tools - all data is provided below.

Below are {end - start} windows of real BTC price history (12 candles each, 5-min intervals). For each window, predict if the price goes UP or DOWN in the next 5 minutes after the CURRENT PRICE.

For EACH window, briefly analyze trend, momentum, and the last few candles, then predict.

DATA:

{data_block}

Output EXACTLY this format at the end (fill in your ACTUAL predictions):
RESULTS_START
{result_template}
RESULTS_END

IMPORTANT: Replace "UP or DOWN" with your actual prediction (UP or DOWN) and "probability" with a number between 0.50 and 0.95. Do NOT echo the template back."""

    out_path = os.path.join(OUT_DIR, f"batch_{batch:02d}.txt")
    with open(out_path, 'w') as f:
        f.write(prompt)

print(f"Built {N_BATCHES} batch files in {OUT_DIR}")
print(f"Windows per batch: {BATCH_SIZE} (last batch: {TOTAL - (N_BATCHES-1)*BATCH_SIZE})")
