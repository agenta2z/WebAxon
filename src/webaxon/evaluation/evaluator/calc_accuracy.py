"""Calculate accuracy from evaluation results JSONL file.

Copied from _dev/external/evaluation_framework/evaluators/online_mind2web/calc_accuracy.py
"""

import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description="Calculate accuracy from evaluation results.")
    ap.add_argument("--results_file", required=True, help="Path to the eval results JSON file.")
    args = ap.parse_args()

    results_file = Path(args.results_file)
    if not results_file.exists():
        print(f"Error: Results file not found: {results_file}")
        return

    successes = 0
    total = 0

    with results_file.open() as f:
        for line in f:
            if not line.strip():
                continue
            try:
                result = json.loads(line)
                predicted_label = result.get("predicted_label", 0)
                successes += predicted_label
                total += 1
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON line: {e}")

    if total == 0:
        print("Error: No valid results found in file.")
        return

    accuracy = (successes / total) * 100
    print(f"\n{'='*60}")
    print(f"  FINAL ACCURACY: {accuracy:.2f}%")
    print(f"{'='*60}")
    print(f"  Successes: {successes}")
    print(f"  Total:     {total}")
    print(f"  Failures:  {total - successes}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
