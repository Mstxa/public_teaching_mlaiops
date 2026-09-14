"""Record the Lab 2 trial estimate; reconcile it when Billing catches up."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actual-thb", type=float,
                        help="Observed Usage cost in THB after Lab 2 appears in Cloud Billing")
    parser.add_argument("--billing-scope", default="project, Lab 2 usage period",
                        help="Filters/date range used in Cloud Billing")
    args = parser.parse_args()
    if args.actual_thb is not None and args.actual_thb < 0:
        parser.error("Actual cost cannot be negative")

    state = json.loads(Path("reports/lab2_remote_checkpoint.json").read_text())
    completed = sorted(state["completed"], key=lambda item: item["trial"])
    failed = state.get("failed_attempts", [])
    estimate = sum(float(item["cost_thb_estimate"]) for item in completed + failed)
    actual_lines = (
        [f"Cloud Billing observed amount: {args.actual_thb:.4f} THB.",
         f"Difference (observed minus estimate): {args.actual_thb - estimate:+.4f} THB.",
         "Billing status: observed amount entered; verify its date range and service scope."]
        if args.actual_thb is not None else
        ["Cloud Billing observed amount: pending.",
         "Difference: pending.",
         "Billing status: usage for the Lab 2 run date has not appeared yet; do not treat an incomplete report as zero cost."]
    )
    lines = [
        "# Lab 2 cost reconciliation", "",
        f"Completed Spot trials: {len(completed)}; failed attempts: {len(failed)}.",
        f"Estimated Vertex training compute: {estimate:.4f} THB.",
        *actual_lines,
        f"Billing scope: {args.billing_scope}.", "",
        "The estimate uses a planning rate of 12 THB/hour and excludes the earlier smoke job, "
        "storage, registry, logs, network, and taxes. The Cloud Billing amount may include "
        "those charges; compare scopes before interpreting the difference.", "",
        "| Trial | Job | Duration (s) | Estimated THB |", "|---:|---|---:|---:|",
    ]
    for item in completed:
        lines.append(
            f"| {item['trial']:02d} | `{item['job_id']}` | "
            f"{float(item['duration_s']):.0f} | {float(item['cost_thb_estimate']):.4f} |"
        )
    for item in failed:
        lines.append(
            f"| {item['trial']:02d} failed | `{item['job_id']}` | — | "
            f"{float(item['cost_thb_estimate']):.4f} |"
        )
    output = Path("reports/lab2-cost.md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")
    print(f"wrote {output}")
    if args.actual_thb is None:
        print(f"estimate {estimate:.4f} THB; actual Cloud Billing cost pending")
    else:
        print(f"estimate {estimate:.4f} THB; observed {args.actual_thb:.4f} THB")


if __name__ == "__main__":
    main()
