#!/usr/bin/env python3
"""Collect all ensemble agent results from task output files and score them."""
import json
import os
import re
import sys
from collections import Counter
from math import comb

TASKS_DIR = "/tmp/claude-0/-home-user-agent-forecaster/79c94298-8ff5-4ff7-a79f-e32edbe2d1a2/tasks"
GT_PATH = "/home/user/agent-forecaster/data/all_windows/ground_truth.json"
OUT_PATH = "/home/user/agent-forecaster/data/ensemble_results.json"

def parse_results_from_text(text):
    """Parse RESULTS_START...RESULTS_END block."""
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


def extract_results_from_output(filepath):
    """Extract RESULTS from a task output file (JSONL format or plain text)."""
    try:
        with open(filepath) as f:
            content = f.read()
    except:
        return {}

    # Try to find results in the raw content
    results = parse_results_from_text(content)
    if results:
        return results

    # Try parsing as JSONL and looking in assistant messages
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            # Look in assistant message content
            if obj.get('type') == 'assistant':
                msg = obj.get('message', {})
                content_list = msg.get('content', [])
                for item in content_list:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        r = parse_results_from_text(item['text'])
                        if r:
                            results.update(r)
                    elif isinstance(item, str):
                        r = parse_results_from_text(item)
                        if r:
                            results.update(r)
        except json.JSONDecodeError:
            continue

    return results


def binomial_test(k, n, p=0.5):
    """One-tailed binomial test: P(X >= k)."""
    return sum(comb(n, i) * p**i * (1-p)**(n-i) for i in range(k, n+1))


def main():
    # Load ground truth
    with open(GT_PATH) as f:
        ground_truth = json.load(f)
    gt_map = {w['id']: w for w in ground_truth}

    # Collect all results from task output files
    all_replicas = []
    files_found = 0
    files_with_results = 0

    for fname in sorted(os.listdir(TASKS_DIR)):
        if not fname.endswith('.output'):
            continue
        filepath = os.path.join(TASKS_DIR, fname)
        results = extract_results_from_output(filepath)
        if results:
            # Check if these are from our ensemble (window IDs 0-275)
            valid_ids = [k for k in results.keys() if 0 <= k <= 275]
            if valid_ids:
                all_replicas.append(results)
                files_with_results += 1
        files_found += 1

    print(f"Scanned {files_found} output files, {files_with_results} had valid ensemble results")

    # Aggregate predictions per window
    window_preds = {}
    for replica in all_replicas:
        for wid, pred in replica.items():
            if wid not in window_preds:
                window_preds[wid] = []
            window_preds[wid].append(pred)

    print(f"Windows with predictions: {len(window_preds)}")

    # Show coverage
    replica_counts = Counter(len(v) for v in window_preds.values())
    print(f"Replica count distribution: {dict(sorted(replica_counts.items()))}")

    # Aggregate and score
    correct = 0
    total = 0
    brier_sum = 0.0
    high_conf_correct = 0
    high_conf_total = 0
    unanimous_correct = 0
    unanimous_total = 0
    details = []

    for wid in sorted(window_preds.keys()):
        if wid not in gt_map:
            continue
        gt = gt_map[wid]
        preds = window_preds[wid]
        n = len(preds)

        # Convert all to UP-probability
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

        # Majority vote
        directions = [p['direction'] for p in preds]
        vote = Counter(directions)
        majority_dir = vote.most_common(1)[0][0]
        agreement = vote.most_common(1)[0][1] / n

        actual_up = gt['went_up']
        actual_dir = 'UP' if actual_up else 'DOWN'
        is_correct = final_dir == actual_dir

        # Brier score
        outcome = 1.0 if actual_up else 0.0
        brier = (avg_up_prob - outcome) ** 2

        correct += int(is_correct)
        total += 1
        brier_sum += brier

        # High confidence: agreement >= 80% AND final_prob >= 60%
        if agreement >= 0.8 and final_prob >= 0.60:
            high_conf_correct += int(is_correct)
            high_conf_total += 1

        # Unanimous
        if agreement == 1.0:
            unanimous_correct += int(is_correct)
            unanimous_total += 1

        details.append({
            'window': wid,
            'n_replicas': n,
            'avg_up_prob': round(avg_up_prob, 4),
            'final_dir': final_dir,
            'final_prob': round(final_prob, 4),
            'agreement': round(agreement, 2),
            'actual': actual_dir,
            'correct': is_correct,
            'brier': round(brier, 4)
        })

    # Print results
    print(f"\n{'='*60}")
    print(f"ENSEMBLE RESULTS (5-agent avg probability)")
    print(f"{'='*60}")
    print(f"Total predictions: {total}")
    print(f"Correct: {correct}")
    print(f"Accuracy: {correct/total:.1%}" if total > 0 else "N/A")
    print(f"Brier Score: {brier_sum/total:.4f} (random=0.2500)" if total > 0 else "N/A")

    print(f"\nHigh-confidence subset (>=80% agreement, >=60% prob):")
    if high_conf_total > 0:
        print(f"  N={high_conf_total}, Correct={high_conf_correct}, Accuracy={high_conf_correct/high_conf_total:.1%}")
    else:
        print(f"  N=0")

    print(f"\nUnanimous subset (all agents agree):")
    if unanimous_total > 0:
        print(f"  N={unanimous_total}, Correct={unanimous_correct}, Accuracy={unanimous_correct/unanimous_total:.1%}")
    else:
        print(f"  N=0")

    # Statistical tests
    print(f"\n{'='*60}")
    print(f"STATISTICAL SIGNIFICANCE")
    print(f"{'='*60}")

    if total > 0:
        p_val = binomial_test(correct, total)
        print(f"Overall: {correct}/{total} correct, p={p_val:.6f}")
        print(f"  {'*** SIGNIFICANT at p<0.05 ***' if p_val < 0.05 else 'Not significant at p<0.05'}")
        print(f"  {'*** SIGNIFICANT at p<0.01 ***' if p_val < 0.01 else ''}")

    if high_conf_total > 0:
        p_hc = binomial_test(high_conf_correct, high_conf_total)
        print(f"\nHigh-confidence: {high_conf_correct}/{high_conf_total}, p={p_hc:.6f}")
        print(f"  {'*** SIGNIFICANT ***' if p_hc < 0.05 else 'Not significant'}")

    if unanimous_total > 0:
        p_un = binomial_test(unanimous_correct, unanimous_total)
        print(f"\nUnanimous: {unanimous_correct}/{unanimous_total}, p={p_un:.6f}")
        print(f"  {'*** SIGNIFICANT ***' if p_un < 0.05 else 'Not significant'}")

    # Save
    output = {
        'summary': {
            'total': total,
            'correct': correct,
            'accuracy': round(correct/total, 4) if total > 0 else 0,
            'brier_score': round(brier_sum/total, 4) if total > 0 else 0,
            'high_confidence': {'n': high_conf_total, 'correct': high_conf_correct},
            'unanimous': {'n': unanimous_total, 'correct': unanimous_correct}
        },
        'details': details
    }
    with open(OUT_PATH, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nDetailed results saved to {OUT_PATH}")


if __name__ == '__main__':
    main()
