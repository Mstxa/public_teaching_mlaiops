"""Record the Lab 2 trial estimate; reconcile it when Billing catches up."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

BILLING_OBSERVATION = Path("reports/lab2-billing-observation.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actual-thb", type=float,
                        help="Observed project Usage cost before credits, in THB")
    parser.add_argument("--billing-scope", default="project, Lab 2 usage period",
                        help="Filters/date range used in Cloud Billing")
    args = parser.parse_args()
    if args.actual_thb is not None and args.actual_thb < 0:
        parser.error("Actual cost cannot be negative")

    observation = json.loads(BILLING_OBSERVATION.read_text()) if BILLING_OBSERVATION.exists() else None
    actual_thb = float(observation["usage_cost_thb"]) if observation else args.actual_thb
    if observation and args.actual_thb is not None and not math.isclose(args.actual_thb, actual_thb, abs_tol=0.0001):
        parser.error("--actual-thb differs from the saved Billing observation")

    state = json.loads(Path("reports/lab2_remote_checkpoint.json").read_text())
    completed = sorted(state["completed"], key=lambda item: item["trial"])
    failed = state.get("failed_attempts", [])
    estimate = sum(float(item["cost_thb_estimate"]) for item in completed + failed)
    if observation:
        services = observation["services_thb"]
        if not math.isclose(sum(float(value) for value in services.values()), actual_thb, abs_tol=0.011):
            parser.error("Service costs do not add up to the observed usage cost")
        actual_lines = [
            f"Cloud Billing observed project usage cost before credits: {actual_thb:.4f} THB.",
            f"Net billed after Free Trial credits: {float(observation['net_after_credits_thb']):.4f} THB.",
            "The observed project usage cost to date is below the 150 THB Lab 2 budget.",
            f"Billing report checked on: {observation['observed_on']}.",
            f"Billing scope: {observation['scope']}.",
            "Service usage costs: " + "; ".join(
                f"{name} {float(value):.2f} THB" for name, value in services.items()
            ) + ".",
            "Billing evidence: " + ", ".join(
                f"[{name}]({path})" for name, path in observation["evidence_paths"].items()
            ) + ".",
        ]
    elif actual_thb is not None:
        actual_lines = [
            f"Cloud Billing observed project usage cost before credits: {actual_thb:.4f} THB.",
            f"Billing scope: {args.billing_scope}.",
            "Service breakdown and Free Trial credits were not entered.",
        ]
    else:
        actual_lines = [
            "Cloud Billing observed project usage cost before credits: pending.",
            f"Billing scope: {args.billing_scope}.",
            "Billing status: usage for the Lab 2 run date has not appeared yet; do not treat an incomplete report as zero cost.",
        ]
    lines = [
        "# Lab 2 cost reconciliation", "",
        f"Completed Spot trials: {len(completed)}; failed attempts: {len(failed)}.",
        f"Estimated Vertex training compute: {estimate:.4f} THB.",
        *actual_lines,
        "Comparison: the estimate covers only the 12 training trials, while the Billing observation covers the full project and may include the earlier smoke job and other services.", "",
        "The estimate uses a planning rate of 12 THB/hour and excludes the earlier smoke job, "
        "storage, registry, logs, network, and taxes. The Cloud Billing amount may include "
        "those charges. Do not treat the difference between these scopes as an exact trial cost error.", "",
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
    if actual_thb is None:
        print(f"estimate {estimate:.4f} THB; actual Cloud Billing cost pending")
    else:
        print(f"estimate {estimate:.4f} THB; observed project usage {actual_thb:.4f} THB")


if __name__ == "__main__":
    main()
