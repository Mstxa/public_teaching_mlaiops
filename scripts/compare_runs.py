"""Lab 2 — rank tracked runs by metric AND by cost per point.

    python scripts/compare_runs.py --experiment itcs355-lab2

Writes reports/lab2-comparison.md. The cost-per-point column is what the lab is about:
the highest-scoring run is frequently not the one you should register.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mlflow
import pandas as pd

from src import config


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", default="itcs355-lab2")
    ap.add_argument("--metric", default="val_roc_auc")
    ap.add_argument("--out", type=Path, default=Path("reports/lab2-comparison.md"))
    args = ap.parse_args()

    cfg = config.load(strict=False)
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    exp = mlflow.get_experiment_by_name(args.experiment)
    if exp is None:
        print(f"No experiment named {args.experiment!r}. Run `make tune` first.")
        return 1

    runs = mlflow.search_runs(experiment_ids=[exp.experiment_id])
    if runs.empty:
        print("No runs found.")
        return 1

    metric_col = f"metrics.{args.metric}"
    cost_col = "metrics.cost_thb"
    total_estimated_cost = runs[cost_col].sum()
    table = pd.DataFrame({
        "run_id": runs["run_id"].str[:8],
        args.metric: runs[metric_col].round(4),
        "est_cost_thb": runs[cost_col].round(4),
        "n_estimators": runs.get("params.n_estimators"),
        "max_depth": runs.get("params.max_depth"),
        "min_samples_leaf": runs.get("params.min_samples_leaf"),
    })
    gain = (table[args.metric] - table[args.metric].min()) * 100
    table["thb_per_point"] = (table["est_cost_thb"] / gain.where(gain > 0)).round(4)
    table = table.sort_values(args.metric, ascending=False)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Lab 2 — Run comparison",
        "",
        f"Experiment `{args.experiment}` · {len(table)} trials · "
        f"estimated compute cost {total_estimated_cost:.4f} THB",
        "",
        "Cost uses a conservative planning rate, not the final Cloud Billing amount.",
        "",
        "`thb_per_point` is cost per percentage point of "
        f"{args.metric} above the worst trial. Cheap improvements rank low; expensive "
        "improvements rank high, however good the headline number is. "
        "The worst trial has no improvement, so its value is undefined.",
        "",
        table.to_markdown(index=False),
        "",
        "## Selection and justification",
        "",
    ]
    if args.out.exists() and "## Selection and justification\n" in args.out.read_text():
        lines.append(args.out.read_text().split("## Selection and justification\n", 1)[1].strip())
    else:
        lines.append("TODO(Lab 2): justify the selected model in 200 words or fewer.")
    args.out.write_text("\n".join(lines))
    print(f"wrote {args.out}  ({len(table)} trials)")
    print(table.head(5).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
