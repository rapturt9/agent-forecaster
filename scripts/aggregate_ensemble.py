#!/usr/bin/env python3
"""Aggregate ensemble predictions from 5 replicas and score against ground truth."""
import json
import sys
import os
import re
from collections import Counter
import math

def parse_results(text):
    """Parse RESULTS_START...RESULTS_END block from agent output."""
    results = {}
    match = re.search(r'RESULTS_START\s*\n(.*?)\nRESULTS_END', text, re.DOTALL)
    if not match:
        return results
    for line in match.group(1).strip().split('\n'):
        line = line.strip()
        if not line or '|' not in line:
            continue
        parts = line.split('|')
        if len(parts) < 3:
            continue
        try:
            wid = int(parts[0].strip())
            direction = parts[1].strip().upper()
            prob = float(parts[2].strip())
            if direction not in ('UP', 'DOWN'):
                continue
            prob = max(0.50, min(0.95, prob))
            results[wid] = {'direction': direction, 'probability': prob}
        except (ValueError, IndexError):
            continue
    return results


def aggregate(all_replicas):
    """Aggregate predictions from multiple replicas per window."""
    # Collect all predictions per window
    window_preds = {}
    for replica_results in all_replicas:
        for wid, pred in replica_results.items():
            if wid not in window_preds:
                window_preds[wid] = []
            window_preds[wid].append(pred)

    aggregated = {}
    for wid in sorted(window_preds.keys()):
        preds = window_preds[wid]
        n = len(preds)

        # Majority vote for direction
        directions = [p['direction'] for p in preds]
        vote = Counter(directions)
        majority_dir = vote.most_common(1)[0][0]
        agreement = vote.most_common(1)[0][1] / n

        # Convert all to UP-probability and average
        up_probs = []
        for p in preds:
            if p['direction'] == 'UP':
                up_probs.append(p['probability'])
            else:
                up_probs.append(1.0 - p['probability'])
        avg_up_prob = sum(up_probs) / len(up_probs)

        # Final direction from averaged probability
        final_dir = 'UP' if avg_up_prob >= 0.5 else 'DOWN'
        final_prob = avg_up_prob if final_dir == 'UP' else (1.0 - avg_up_prob)

        aggregated[wid] = {
            'direction': final_dir,
            'probability': final_prob,
            'avg_up_prob': avg_up_prob,
            'vote_direction': majority_dir,
            'agreement': agreement,
            'n_replicas': n,
            'individual': preds
        }

    return aggregated


def score(aggregated, ground_truth):
    """Score aggregated predictions against ground truth."""
    correct = 0
    total = 0
    brier_sum = 0.0
    high_conf_correct = 0
    high_conf_total = 0
    unanimous_correct = 0
    unanimous_total = 0

    for gt in ground_truth:
        wid = gt['id']
        if wid not in aggregated:
            continue
        pred = aggregated[wid]
        actual_up = gt['went_up']
        actual_dir = 'UP' if actual_up else 'DOWN'

        # Accuracy
        is_correct = pred['direction'] == actual_dir
        correct += int(is_correct)
        total += 1

        # Brier score
        forecast_prob = pred['avg_up_prob']
        outcome = 1.0 if actual_up else 0.0
        brier = (forecast_prob - outcome) ** 2
        brier_sum += brier

        # High confidence (agreement >= 0.8 AND prob >= 0.6)
        if pred['agreement'] >= 0.8 and pred['probability'] >= 0.60:
            high_conf_correct += int(is_correct)
            high_conf_total += 1

        # Unanimous (all 5 agree)
        if pred['agreement'] == 1.0:
            unanimous_correct += int(is_correct)
            unanimous_total += 1

        pred['actual'] = actual_dir
        pred['correct'] = is_correct
        pred['brier'] = brier

    results = {
        'total': total,
        'correct': correct,
        'accuracy': correct / total if total > 0 else 0,
        'brier_score': brier_sum / total if total > 0 else 0,
        'high_confidence': {
            'total': high_conf_total,
            'correct': high_conf_correct,
            'accuracy': high_conf_correct / high_conf_total if high_conf_total > 0 else 0
        },
        'unanimous': {
            'total': unanimous_total,
            'correct': unanimous_correct,
            'accuracy': unanimous_correct / unanimous_total if unanimous_total > 0 else 0
        }
    }
    return results


def binomial_test(k, n, p=0.5):
    """One-tailed binomial test: P(X >= k) given n trials with prob p."""
    from math import comb
    p_value = sum(comb(n, i) * p**i * (1-p)**(n-i) for i in range(k, n+1))
    return p_value


if __name__ == '__main__':
    # Load ground truth
    gt_path = '/home/user/agent-forecaster/data/windows/ground_truth.json'
    with open(gt_path) as f:
        ground_truth = json.load(f)

    # Load replica results from files passed as args
    results_dir = sys.argv[1] if len(sys.argv) > 1 else '/home/user/agent-forecaster/data/ensemble_results'

    all_replicas = []
    for fname in sorted(os.listdir(results_dir)):
        if fname.endswith('.txt'):
            with open(os.path.join(results_dir, fname)) as f:
                text = f.read()
            parsed = parse_results(text)
            if parsed:
                all_replicas.append(parsed)
                print(f"Loaded {fname}: {len(parsed)} predictions")

    if not all_replicas:
        print("No replica results found!")
        sys.exit(1)

    print(f"\nTotal replicas loaded: {len(all_replicas)}")

    # Aggregate
    aggregated = aggregate(all_replicas)
    print(f"Windows with predictions: {len(aggregated)}")

    # Score
    scores = score(aggregated, ground_truth)

    print(f"\n{'='*60}")
    print(f"ENSEMBLE RESULTS (5-agent majority vote + probability avg)")
    print(f"{'='*60}")
    print(f"Total predictions: {scores['total']}")
    print(f"Correct: {scores['correct']}")
    print(f"Accuracy: {scores['accuracy']:.1%}")
    print(f"Brier Score: {scores['brier_score']:.4f} (random=0.2500)")
    print(f"")
    print(f"High-confidence subset (>=80% agreement, >=60% prob):")
    hc = scores['high_confidence']
    print(f"  N={hc['total']}, Correct={hc['correct']}, Accuracy={hc['accuracy']:.1%}")
    print(f"")
    print(f"Unanimous subset (5/5 agree):")
    un = scores['unanimous']
    print(f"  N={un['total']}, Correct={un['correct']}, Accuracy={un['accuracy']:.1%}")

    # Statistical tests
    print(f"\n{'='*60}")
    print(f"STATISTICAL SIGNIFICANCE")
    print(f"{'='*60}")

    n, k = scores['total'], scores['correct']
    if n > 0:
        p_val = binomial_test(k, n)
        print(f"Binomial test (H0: accuracy=50%): p={p_val:.4f}")
        print(f"  {'SIGNIFICANT at p<0.05 - better than random!' if p_val < 0.05 else 'NOT significant at p<0.05'}")

    if hc['total'] > 0:
        p_val_hc = binomial_test(hc['correct'], hc['total'])
        print(f"\nHigh-confidence binomial test: p={p_val_hc:.4f}")
        print(f"  {'SIGNIFICANT!' if p_val_hc < 0.05 else 'Not significant'}")

    if un['total'] > 0:
        p_val_un = binomial_test(un['correct'], un['total'])
        print(f"\nUnanimous binomial test: p={p_val_un:.4f}")
        print(f"  {'SIGNIFICANT!' if p_val_un < 0.05 else 'Not significant'}")

    # Save detailed results
    out_path = '/home/user/agent-forecaster/data/ensemble_scored.json'
    with open(out_path, 'w') as f:
        json.dump({
            'scores': scores,
            'predictions': {str(k): v for k, v in aggregated.items()}
        }, f, indent=2, default=str)
    print(f"\nDetailed results saved to {out_path}")
