"""Controlled Lab 3 batch and payload experiments against the local service."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

INSTANCE = {
    "temp_c": 78.4,
    "vibration_mm_s": 3.1,
    "pressure_kpa": 315.2,
    "hours_since_service": 4200,
    "load_pct": 68.0,
    "ambient_humidity": 55.0,
}


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def summary(values: list[float]) -> dict[str, float]:
    return {
        "median_ms": statistics.median(values),
        "p95_ms": percentile(values, 0.95),
        "min_ms": min(values),
        "max_ms": max(values),
    }


def send(base_url: str, path: str, body: bytes) -> tuple[float, dict]:
    request = Request(
        base_url.rstrip("/") + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            status = response.status
    except HTTPError as exc:
        raise RuntimeError(
            f"{path} returned {exc.code}: {exc.read().decode(errors='replace')}"
        ) from exc

    elapsed_ms = (time.perf_counter() - started) * 1000
    if status != 200:
        raise RuntimeError(f"{path} returned HTTP {status}")
    return elapsed_ms, json.loads(raw)


def wait_ready(base_url: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with urlopen(base_url.rstrip("/") + "/ready", timeout=3) as response:
                if response.status == 200:
                    return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Service did not become ready within 60 seconds")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports/lab3-variable-local.txt"),
    )
    args = parser.parse_args()

    wait_ready(args.base_url)

    single_body = json.dumps(INSTANCE, separators=(",", ":")).encode()
    batch_body = json.dumps(
        {"rows": [INSTANCE] * 100},
        separators=(",", ":"),
    ).encode()

    for _ in range(5):
        _, result = send(args.base_url, "/predict", single_body)
        if "probability" not in result or "model_version" not in result:
            raise RuntimeError("Single response contract failed")

    single_cycles: list[float] = []
    batch_cycles: list[float] = []

    for _ in range(args.repeats):
        started = time.perf_counter()
        for _ in range(100):
            _, result = send(args.base_url, "/predict", single_body)
            if "probability" not in result or "model_version" not in result:
                raise RuntimeError("Single response contract failed")
        single_cycles.append((time.perf_counter() - started) * 1000)

        elapsed, result = send(args.base_url, "/predict/batch", batch_body)
        if (
            len(result.get("probabilities", [])) != 100
            or "model_version" not in result
        ):
            raise RuntimeError("Batch response contract failed")
        batch_cycles.append(elapsed)

    single_total_s = sum(single_cycles) / 1000
    batch_total_s = sum(batch_cycles) / 1000
    single_prediction_rate = args.repeats * 100 / single_total_s
    batch_prediction_rate = args.repeats * 100 / batch_total_s

    compact = json.dumps(INSTANCE, separators=(",", ":"))
    payload_rows = []
    payload_medians: dict[int, float] = {}

    for padding_bytes in (0, 10_240, 102_400, 1_048_576, 5_242_880, 10_485_760, 20_971_520):
        padded = (
            compact[:-1] + (" " * padding_bytes) + "}"
        ).encode()
        timings = []
        for _ in range(args.repeats):
            elapsed, result = send(args.base_url, "/predict", padded)
            if "probability" not in result or "model_version" not in result:
                raise RuntimeError("Payload response contract failed")
            timings.append(elapsed)

        metrics = summary(timings)
        payload_medians[padding_bytes] = metrics["median_ms"]
        payload_rows.append(
            {
                "padding_bytes": padding_bytes,
                "request_bytes": len(padded),
                **metrics,
            }
        )

    baseline_median = payload_medians[0]
    for row in payload_rows:
        row["median_delta_pct"] = (
            (row["median_ms"] / baseline_median) - 1
        ) * 100

    dominance = next(
        (
            row["request_bytes"]
            for row in payload_rows
            if row["padding_bytes"] > 0
            and row["median_ms"] >= baseline_median * 1.5
        ),
        None,
    )

    output = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "repeats": args.repeats,
        "batch_experiment": {
            "single_100_calls": {
                **summary(single_cycles),
                "predictions_per_second": single_prediction_rate,
                "request_bytes_each": len(single_body),
            },
            "batch_100_rows": {
                **summary(batch_cycles),
                "predictions_per_second": batch_prediction_rate,
                "request_bytes": len(batch_body),
            },
            "batch_speedup": (
                batch_prediction_rate / single_prediction_rate
            ),
            "request_reduction_pct": 99.0,
        },
        "payload_experiment": {
            "same_prediction_input": True,
            "method": (
                "Valid JSON whitespace was added before the closing brace; "
                "feature values and prediction output were unchanged."
            ),
            "first_size_with_50pct_median_increase_bytes": dominance,
            "results": payload_rows,
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(output, indent=2)
    args.out.write_text(rendered + "\n")
    print(rendered)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
