"""Run one training trial with cloud input and durable cloud outputs.

The Vertex job supplies configuration through environment variables and arguments.
This entry point also runs locally with application-default credentials, which makes
it possible to test data access and artifact upload before paying for managed compute.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from cloudlayer.factory import get_adapter
from src import config, seeds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one cloud-backed training trial")
    parser.add_argument("--data-uri", required=True)
    parser.add_argument("--output-prefix", required=True, help="Key under BLOB_URI")
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--data-version", required=True)
    parser.add_argument("--n-estimators", type=int, default=150)
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--min-samples-leaf", type=int, default=5)
    parser.add_argument("--seed", type=int, default=seeds.DEFAULT_SEED)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.data_version not in args.data_uri:
        raise ValueError("data URI must include the declared DVC data version")

    with TemporaryDirectory(prefix="itcs355-lab2-") as temporary:
        work = Path(temporary)
        os.environ["DATA_DIR"] = str(work / "data")
        os.environ["MLFLOW_TRACKING_URI"] = f"sqlite:///{work / 'mlflow.db'}"
        os.environ["GIT_COMMIT"] = args.git_commit
        os.environ["DVC_DATA_HASH"] = args.data_version

        cfg = config.load()
        adapter = get_adapter(cfg)
        adapter.download(args.data_uri, str(cfg.raw_path))

        model_path = work / "model.joblib"
        metrics_path = work / "metrics.json"
        command = [
            sys.executable, "-m", "src.train",
            "--n-estimators", str(args.n_estimators),
            "--max-depth", str(args.max_depth),
            "--min-samples-leaf", str(args.min_samples_leaf),
            "--seed", str(args.seed),
            "--experiment", "itcs355-lab2-remote-smoke",
            "--model-out", str(model_path),
            "--metrics-out", str(metrics_path),
        ]
        subprocess.run(command, check=True, env=os.environ.copy())

        prefix = args.output_prefix.strip("/")
        model_uri = adapter.upload(str(model_path), f"{prefix}/model.joblib")
        metrics_uri = adapter.upload(str(metrics_path), f"{prefix}/metrics.json")
        print(json.dumps({"model_uri": model_uri, "metrics_uri": metrics_uri}, indent=2))


if __name__ == "__main__":
    main()
