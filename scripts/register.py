"""Upload a trained model with lineage and register one model version."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.factory import get_adapter
from src import config


DIGEST_IMAGE = re.compile(r".+@sha256:[0-9a-f]{64}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--training-image", required=True)
    parser.add_argument("--training-job-id", required=True)
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--version-out", type=Path, default=None)
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_metric(metrics: dict, key: str) -> float:
    if key not in metrics:
        raise ValueError(f"Training metrics are missing {key!r}")
    value = float(metrics[key])
    if not math.isfinite(value):
        raise ValueError(f"Training metric {key!r} must be finite")
    return value


def main() -> None:
    args = parse_args()

    if not args.model.is_file():
        raise SystemExit(f"Model file not found: {args.model}")
    if not args.metrics.is_file():
        raise SystemExit(f"Metrics file not found: {args.metrics}")
    if not DIGEST_IMAGE.fullmatch(args.training_image):
        raise SystemExit(
            "--training-image must be digest-pinned: repository@sha256:<64 hex>"
        )

    metrics = json.loads(args.metrics.read_text())
    data_version = str(metrics.get("data_fingerprint", "")).strip()
    mlflow_run_id = str(metrics.get("mlflow_run_id", "")).strip()
    if not data_version:
        raise SystemExit("Training metrics are missing data_fingerprint")
    if not mlflow_run_id:
        raise SystemExit("Training metrics are missing mlflow_run_id")

    model_digest = file_sha256(args.model)
    artifact_key = (
        f"lab5/models/{args.git_commit[:12]}-{model_digest[:12]}"
    )

    cfg = config.load()
    adapter = get_adapter(cfg)

    model_uri = adapter.upload(
        str(args.model),
        f"{artifact_key}/model.joblib",
    )

    lineage = {
        "git_commit": args.git_commit,
        "data_version": data_version,
        "mlflow_run_id": mlflow_run_id,
        "training_job_id": args.training_job_id,
        "image_digest": args.training_image.rsplit("@", 1)[1],
        "seed": int(metrics["seed"]),
        "metric_val": require_metric(metrics, "val_roc_auc"),
        "metric_test": require_metric(metrics, "test_roc_auc"),
        "model_uri": model_uri,
        "training_image_uri": args.training_image,
        "model_sha256": model_digest,
    }

    with TemporaryDirectory(prefix="itcs355-lab5-register-") as directory:
        sidecar = Path(directory) / "lineage.json"
        sidecar.write_text(json.dumps(lineage, indent=2, sort_keys=True))
        lineage_uri = adapter.upload(
            str(sidecar),
            f"{artifact_key}/lineage.json",
        )

    version = adapter.register_model(model_uri, cfg.model_registry_name)

    if args.version_out:
        args.version_out.parent.mkdir(parents=True, exist_ok=True)
        args.version_out.write_text(version + "\n")

    print(f"Registered {cfg.model_registry_name}@{version}")
    print(f"Model: {model_uri}")
    print(f"Lineage: {lineage_uri}")


if __name__ == "__main__":
    main()
