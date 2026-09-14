"""Register the selected Vertex Spot trial with reproducible lineage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cloudlayer.factory import get_adapter
from src import config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial", type=int, default=1)
    args = parser.parse_args()

    cfg = config.load()
    checkpoint = json.loads(Path("reports/lab2_remote_checkpoint.json").read_text())
    matches = [item for item in checkpoint["completed"] if item["trial"] == args.trial]
    if len(matches) != 1:
        raise SystemExit(f"Expected one completed trial {args.trial:02d} in the checkpoint")
    trial = matches[0]
    image_uri = checkpoint["image_uri"]
    lineage = {
        "git_commit": checkpoint["git_commit"],
        "data_version": checkpoint["data_version"],
        "mlflow_run_id": trial["mlflow_run_id"],
        "training_job_id": trial["job_id"],
        "image_digest": image_uri.rsplit("@", 1)[1],
        "seed": trial["seed"],
        "metric_val": trial["metrics"]["val_roc_auc"],
        "metric_test": trial["metrics"]["test_roc_auc"],
        "model_uri": trial["model_uri"],
        "training_image_uri": image_uri,
    }
    if not trial["model_uri"].startswith(cfg.blob_uri.rstrip("/") + "/"):
        raise SystemExit("Chosen model is outside the configured storage prefix")
    sidecar_uri = trial["model_uri"].rsplit("/", 1)[0] + "/lineage.json"
    sidecar_key = sidecar_uri.removeprefix(cfg.blob_uri.rstrip("/") + "/")
    adapter = get_adapter(cfg)
    with TemporaryDirectory(prefix="itcs355-register-") as directory:
        path = Path(directory) / "lineage.json"
        path.write_text(json.dumps(lineage, indent=2, sort_keys=True))
        adapter.upload(str(path), sidecar_key)
    version = adapter.register_model(trial["model_uri"], cfg.model_registry_name)
    print(f"Registered {cfg.model_registry_name}@{version}")
    print(f"Lineage: {sidecar_uri}")


if __name__ == "__main__":
    main()
