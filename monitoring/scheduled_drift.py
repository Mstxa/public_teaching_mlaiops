"""Run the Lab 4 drift detector from a managed scheduled job.

The reference and recent production windows live in Cloud Storage.  A Cloud
Run Job downloads both, emits one PSI metric per feature, and logs the alert
decision.  A threshold breach is not an infrastructure failure, so the job
still exits successfully after publishing the metrics.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from cloudlayer.factory import get_adapter
from monitoring.drift import PSI_ALERT_THRESHOLD, compare
from src import config, data


def main() -> int:
    reference_uri = os.environ["REFERENCE_URI"]
    current_uri = os.environ["CURRENT_URI"]
    threshold = float(os.environ.get("PSI_THRESHOLD", PSI_ALERT_THRESHOLD))
    adapter = get_adapter(config.load(strict=False))

    with TemporaryDirectory(prefix="itcs355-drift-") as directory:
        workdir = Path(directory)
        reference_path = workdir / "reference.csv"
        current_path = workdir / "current.csv"
        adapter.download(reference_uri, str(reference_path))
        adapter.download(current_uri, str(current_path))

        results = compare(
            pd.read_csv(reference_path),
            pd.read_csv(current_path),
            data.FEATURES,
        )

    for result in results:
        adapter.emit_metric(f"drift.psi.{result.feature}", result.psi)

    print(json.dumps([asdict(result) for result in results], sort_keys=True))
    breached = [result for result in results if result.psi >= threshold]
    if breached:
        names = ", ".join(result.feature for result in breached)
        print(f"ALERT: {len(breached)} feature(s) above {threshold}: {names}")
    else:
        print(f"OK: no feature above {threshold}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
