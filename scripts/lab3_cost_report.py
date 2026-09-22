"""Generate the reproducible Lab 3 serving-cost report."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from src import costs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="gcp")
    parser.add_argument("--instance", default="n1-standard-2")
    parser.add_argument("--rps", type=float, default=55.735)
    parser.add_argument("--utilisation", type=float, default=1.0)
    parser.add_argument("--larger-instance", default="n1-standard-4")
    parser.add_argument("--larger-rps", type=float, default=78.564936)
    parser.add_argument("--batch-hours", type=float, default=0.5)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports/lab3-cost.md"),
    )
    args = parser.parse_args()

    rate = costs.hourly_rate(args.provider, args.instance)
    larger_rate = costs.hourly_rate(
        args.provider,
        args.larger_instance,
    )
    unit_cost = costs.cost_per_1k_predictions(
        rate,
        args.rps,
        args.utilisation,
    )
    larger_unit_cost = costs.cost_per_1k_predictions(
        larger_rate,
        args.larger_rps,
        args.utilisation,
    )
    batch_job_thb = rate * args.batch_hours
    breakeven = costs.batch_breakeven_rps(
        rate,
        batch_job_thb=batch_job_thb,
    )

    content = f"""# Lab 3 cost report

Recorded `{datetime.now(timezone.utc).isoformat()}`.

## Warm endpoint

- Provider: `{args.provider}`
- Instance: `{args.instance}`
- Hourly rate: {rate:.2f} THB/hour
- Measured throughput: {args.rps:.3f} requests/second
- Utilisation assumption: {args.utilisation:.0%}

    THB per 1,000
      = hourly rate * 1,000
        / (throughput * 3,600 * utilisation)
      = {unit_cost:.6f} THB

## One-size-up comparison

| Instance | THB/hour | Throughput (req/s) | THB/1,000 |
|---|---:|---:|---:|
| `{args.instance}` | {rate:.2f} | {args.rps:.3f} | {unit_cost:.5f} |
| `{args.larger_instance}` | {larger_rate:.2f} | {args.larger_rps:.3f} | {larger_unit_cost:.5f} |

The larger instance changes unit cost by
{((larger_unit_cost / unit_cost) - 1) * 100:+.2f}%.

## Batch inference break-even

Assumption: one scheduled batch run per day uses `{args.instance}` for
{args.batch_hours:.2f} hours and costs {batch_job_thb:.2f} THB.

The repository planning model gives a break-even request rate of
{breakeven:.4f} req/s, approximately {breakeven * 86400:.1f}
predictions per day.

Below that volume, scheduled batch inference is cheaper than keeping
the endpoint warm. Above it, the latency requirement and available
batch window determine which mode is appropriate.
"""

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(content)
    print(content)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
