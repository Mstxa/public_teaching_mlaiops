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

# TODO(Lab 5): choose and defend these. A margin of zero means noise gets promoted;
# too large a margin means real improvements never ship.
MIN_ABSOLUTE = 0.75
MIN_IMPROVEMENT = 0.002

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
        # TODO(Lab 5): read the production version's metric from the registry instead of
        # assuming there is no incumbent. A first run legitimately has none.
        print("no incumbent supplied — treating as first registration")
        return finish("pass", args.decision_out)

    delta = candidate - incumbent
    print(f"incumbent {incumbent:.4f}  delta {delta:+.4f}  required {MIN_IMPROVEMENT:+.4f}")
    if delta < MIN_IMPROVEMENT:
        print("improvement within noise; not registering")
        return finish("fail", args.decision_out)

    return finish("pass", args.decision_out)


if __name__ == "__main__":
    raise SystemExit(main())
