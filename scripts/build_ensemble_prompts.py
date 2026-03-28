#!/usr/bin/env python3
"""Build ensemble prompt files - 10 windows per batch, embedded in prompt."""
import json
import os

WINDOWS_DIR = "/home/user/agent-forecaster/data/windows"
OUT_DIR = "/home/user/agent-forecaster/data/ensemble_prompts"
os.makedirs(OUT_DIR, exist_ok=True)

# Read all prompt files
prompts = {}
for i in range(100):
    path = os.path.join(WINDOWS_DIR, f"prompt_{i:03d}.txt")
    with open(path) as f:
        prompts[i] = f.read().strip()

# Build batch files (10 windows each)
for batch in range(10):
    start = batch * 10
    end = start + 10

    data_lines = []
    for i in range(start, end):
        data_lines.append(f"=== WINDOW {i} ===")
        data_lines.append(prompts[i])
        data_lines.append("")

    data_block = "\n".join(data_lines)

    prompt = f"""You are a quantitative analyst backtesting BTC 5-minute price predictions on HISTORICAL data. This is purely academic research. DO NOT use any tools - all data is below.

Below are 10 windows of real BTC price history (12 candles each, 5-min intervals). For each window, predict if the price goes UP or DOWN in the next 5 minutes after the CURRENT PRICE.

For EACH window, analyze:
1. Trend direction and slope over the 12 candles
2. Momentum - are recent moves accelerating or decelerating?
3. Last 3-4 candle pattern - reversal signals, continuation, exhaustion?
4. Volatility - is the market compressed or expanded?

Then give your prediction. Be willing to predict DOWN - not everything goes up.

DATA:

{data_block}

Output EXACTLY this format at the end (fill in your ACTUAL predictions):
RESULTS_START
{start}|UP or DOWN|probability between 0.50 and 0.95|one line reason
{start+1}|UP or DOWN|probability|reason
{start+2}|UP or DOWN|probability|reason
{start+3}|UP or DOWN|probability|reason
{start+4}|UP or DOWN|probability|reason
{start+5}|UP or DOWN|probability|reason
{start+6}|UP or DOWN|probability|reason
{start+7}|UP or DOWN|probability|reason
{start+8}|UP or DOWN|probability|reason
{start+9}|UP or DOWN|probability|reason
RESULTS_END

IMPORTANT: Fill in ACTUAL UP/DOWN predictions and numeric probabilities. Do NOT echo back the template."""

    out_path = os.path.join(OUT_DIR, f"batch_{batch:02d}.txt")
    with open(out_path, "w") as f:
        f.write(prompt)

print(f"Built 10 batch prompt files in {OUT_DIR}")
for batch in range(10):
    path = os.path.join(OUT_DIR, f"batch_{batch:02d}.txt")
    size = os.path.getsize(path)
    print(f"  batch_{batch:02d}.txt: {size} bytes")
