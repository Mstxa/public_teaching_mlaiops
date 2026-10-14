"""Lab 5 — the registration gate.

Compares a candidate against the currently registered production model. Exits non-zero
when the candidate should NOT be registered, which is what makes the pipeline condition
real rather than decorative.

    python scripts/evaluation_gate.py --metrics reports/metrics.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.factory import get_adapter
from src import config

# TODO(Lab 5): choose and defend these. A margin of zero means noise gets promoted;
# too large a margin means real improvements never ship.
MIN_ABSOLUTE = 0.75
MIN_IMPROVEMENT = 0.002

def read_production_metric(metric_key: str) -> float | None:
    """Read one metric from the registered production model.

    A missing production alias means this is the first registration.
    Other errors must propagate because permission and configuration failures
    must not silently turn into an automatic pass.
    """
    cfg = config.load()
    adapter = get_adapter(cfg)

    try:
        model = adapter.get_model_version(
            cfg.model_registry_name,
            "production",
        )
    except LookupError:
        print("no production model registered")
        return None

    description = model.get("versionDescription")
    if not description:
        raise RuntimeError("Production model has no versionDescription lineage")

    try:
        lineage = json.loads(description)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Production model versionDescription is not valid JSON"
        ) from exc

    if metric_key not in lineage:
        raise RuntimeError(
            f"Production model lineage has no {metric_key!r} metric"
        )

    value = float(lineage[metric_key])
    version = model.get("versionId", "unknown")
    print(f"production model version {version}  {metric_key} = {value:.4f}")
    return value

def finish(decision: str, decision_out: Path | None) -> int:
    """Publish the gate decision.

    Local mode exits non-zero on failure. Pipeline mode writes a decision
    parameter and exits zero so the DAG can reach its conditional branch.
    """
    if decision_out is not None:
        decision_out.parent.mkdir(parents=True, exist_ok=True)
        decision_out.write_text(decision + "\n")
        print(f"wrote gate decision to {decision_out}")

    print(f"GATE {decision.upper()}")

    if decision == "pass":
        return 0

    return 0 if decision_out is not None else 1

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", type=Path, required=True)
    ap.add_argument("--metric", default="test_roc_auc")
    ap.add_argument(
        "--registry-metric",
        default="metric_test",
        help="lineage field containing the production comparison metric",
    )
    ap.add_argument("--incumbent", type=float, default=None,
                    help="current production score; omit to read from the registry")
    ap.add_argument(
        "--decision-out",
        type=Path,
        default=None,
        help="write pass/fail for a pipeline conditional; failure exits zero in this mode",
    )
    args = ap.parse_args()

    payload = json.loads(args.metrics.read_text())
    candidate = float(payload[args.metric])
    print(f"candidate {args.metric} = {candidate:.4f}")

    if candidate < MIN_ABSOLUTE:
        print(f"below absolute floor {MIN_ABSOLUTE}")
        return finish("fail", args.decision_out)

    incumbent = args.incumbent
    if incumbent is None:
        incumbent = read_production_metric(args.registry_metric)

    if incumbent is None:
        print("treating this as the first registration")
        return finish("pass", args.decision_out)

    delta = candidate - incumbent
    print(f"incumbent {incumbent:.4f}  delta {delta:+.4f}  required {MIN_IMPROVEMENT:+.4f}")
    if delta < MIN_IMPROVEMENT:
        print("improvement within noise; not registering")
        return finish("fail", args.decision_out)

    return finish("pass", args.decision_out)


if __name__ == "__main__":
    raise SystemExit(main())
