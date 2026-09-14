"""Fetch an explicit Vertex registry version, download its model, and score test rows."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib

from cloudlayer.factory import get_adapter
from src import config, data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", help="registered model name (defaults to cloud.env)")
    ap.add_argument("--version", required=True)
    ap.add_argument("--rows", type=int, default=5)
    args = ap.parse_args()

    cfg = config.load()
    name = args.name or cfg.model_registry_name
    adapter = get_adapter(cfg)
    registered = adapter.get_model_version(name, args.version)
    lineage = json.loads(registered.get("versionDescription", "{}"))
    required = (
        "git_commit", "data_version", "mlflow_run_id", "training_job_id",
        "image_digest", "seed", "metric_val", "metric_test", "model_uri",
    )
    if any(lineage.get(key) in (None, "") for key in required):
        raise RuntimeError("Registered version is missing required lineage")
    artifact_uri = registered.get("artifactUri", "").rstrip("/")
    if not artifact_uri.startswith("gs://"):
        raise RuntimeError("Registered version has no downloadable GCS artifact URI")
    print(f"loading {name}@{registered['versionId']} from Vertex Model Registry")
    with TemporaryDirectory(prefix="itcs355-reload-") as directory:
        model_path = Path(directory) / "model.joblib"
        adapter.download(f"{artifact_uri}/model.joblib", str(model_path))
        model = joblib.load(model_path)

    df = data.load_raw(cfg.raw_path)
    _, _, test_df = data.split(df, seed=int(lineage["seed"]))
    sample = test_df.head(args.rows)
    preds = model.predict_proba(sample[data.FEATURES])[:, 1]

    for rid, p in zip(sample[data.ID], preds):
        print(f"  reading {rid}: p(failure)={p:.4f}")
    print("\nPASS  model reloaded by Vertex registry version and scored rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
