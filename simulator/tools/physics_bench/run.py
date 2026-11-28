"""Run the fixed-seed benchmark from any working directory."""
import argparse
import csv
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.physics_bench.cases import cases
from tools.physics_bench.reference import COMPARATORS
from tools.physics_bench.report import HERE, check, render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "output")
    out = parser.parse_args().out
    out.mkdir(parents=True, exist_ok=True)
    success = True
    print("case | metrics | result")
    with (out / "summary.csv").open("w", newline="", encoding="utf8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("case", "metric", "value", "case_result",
                         "analogue_value", "source", "conditions", "evidence"))
        for result in cases():
            errors = check(result)
            status = ", ".join(errors) or "PASS"
            render(result, out)
            for metric, value in result.metrics.items():
                comparator = COMPARATORS.get((result.name, metric))
                evidence = "類比參考、非 X1 事實" if comparator else "模擬回歸基準"
                writer.writerow((result.name, metric, value, status, *(comparator or ("", "", "")), evidence))
            values = ", ".join(f"{k}={v:.5g}" for k, v in result.metrics.items())
            print(f"{result.name} | {values} | {status}", flush=True)
            if result.name == "timing":
                for column, label in enumerate(result.columns[1:], 1):
                    costs = result.rows[:, column]
                    p95, p99 = np.percentile(costs, [95, 99])
                    print(f"  {label}: p95={p95:.3f}, p99={p99:.3f}, max={max(costs):.3f}, "
                          f">2 ms={sum(costs > 2)}/{len(costs)}, >10 ms={sum(costs > 10)}/{len(costs)}")
            success &= not errors
    return int(not success)


if __name__ == "__main__":
    sys.exit(main())
