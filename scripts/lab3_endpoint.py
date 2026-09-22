"""Lab 3 managed endpoint deployment and three-payload smoke test."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cloudlayer.factory import get_adapter
from src.config import load


PAYLOADS = [
    {
        "temp_c": 78.4,
        "vibration_mm_s": 3.1,
        "pressure_kpa": 315.2,
        "hours_since_service": 4200,
        "load_pct": 68.0,
        "ambient_humidity": 55.0,
    },
    {
        "temp_c": 64.0,
        "vibration_mm_s": 1.8,
        "pressure_kpa": 298.0,
        "hours_since_service": 900,
        "load_pct": 41.0,
        "ambient_humidity": 47.0,
    },
    {
        "temp_c": 96.0,
        "vibration_mm_s": 7.2,
        "pressure_kpa": 342.0,
        "hours_since_service": 8100,
        "load_pct": 91.0,
        "ambient_humidity": 73.0,
    },
]


def save(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(value, indent=2)
    path.write_text(rendered + "\n")
    print(rendered)
    print(f"wrote {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    deploy_parser = subparsers.add_parser("deploy")
    deploy_parser.add_argument("--model-ref")
    deploy_parser.add_argument("--endpoint")
    deploy_parser.add_argument("--instance", default="n1-standard-2")
    deploy_parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports/lab3-make-deploy.txt"),
    )

    smoke_parser = subparsers.add_parser("smoke")
    smoke_parser.add_argument("--endpoint")
    smoke_parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports/lab3-make-smoke.txt"),
    )

    args = parser.parse_args()
    cfg = load()
    adapter = get_adapter(cfg)
    endpoint = args.endpoint or f"{cfg.project_id}-lab3"

    if args.command == "deploy":
        model_ref = args.model_ref or f"{cfg.model_registry_name}@1"
        result = adapter.deploy(
            model_ref=model_ref,
            endpoint=endpoint,
            instance=args.instance,
        )
        save(
            args.out,
            {
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "command": "make deploy",
                "model_ref": model_ref,
                "endpoint": endpoint,
                "instance": args.instance,
                "result": result,
            },
        )
        return 0

    responses = []
    for index, payload in enumerate(PAYLOADS, start=1):
        response = adapter.invoke(endpoint, payload)
        predictions = response.get("predictions", [])
        if len(predictions) != 1:
            raise RuntimeError(
                f"Smoke payload {index} returned {len(predictions)} predictions"
            )
        prediction = predictions[0]
        if (
            "probability" not in prediction
            or "model_version" not in prediction
        ):
            raise RuntimeError(
                f"Smoke payload {index} omitted probability or model_version"
            )
        responses.append(
            {
                "payload_number": index,
                "input": payload,
                "response": response,
            }
        )

    save(
        args.out,
        {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "command": "make smoke",
            "endpoint": endpoint,
            "payload_count": len(PAYLOADS),
            "all_passed": True,
            "results": responses,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
