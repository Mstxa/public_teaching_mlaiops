"""Submit and watch the first Vertex AI training smoke job."""
from __future__ import annotations

import argparse
import json
import subprocess

from cloudlayer.factory import get_adapter
from src import config
from src.train import dvc_data_hash


def _git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=config.REPO_ROOT, text=True
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-uri", help="Digest reference from make image-push")
    parser.add_argument("--job-id", help="Watch an existing job without submitting another one")
    parser.add_argument("--output-prefix", default="lab2/smoke-vertex")
    parser.add_argument("--machine-type", default="e2-standard-4")
    parser.add_argument("--no-wait", action="store_true")
    options = parser.parse_args()

    cfg = config.load()
    adapter = get_adapter(cfg)
    if options.job_id:
        job_id = options.job_id
    else:
        if not options.image_uri:
            parser.error("--image-uri is required when submitting a new job")
        if _git("status", "--porcelain"):
            raise SystemExit("Commit the current source changes before building and submitting the image")
        data_version = dvc_data_hash()
        if data_version == "unknown":
            raise SystemExit("Could not read the DVC data version")
        args = {
            "data_uri": f"{cfg.blob_uri.rstrip('/')}/lab2/data/{data_version}/sensors.csv",
            "output_prefix": options.output_prefix,
            "git_commit": _git("rev-parse", "HEAD"),
            "data_version": data_version,
            "machine_type": options.machine_type,
        }
        job_id = adapter.submit_training(options.image_uri, args)
        print(json.dumps({"training_job_id": job_id, "output_prefix": options.output_prefix}, indent=2))
    if not options.no_wait:
        result = adapter.wait_training(job_id)
        print(json.dumps({"state": result.get("state"), "error": result.get("error")}, indent=2))
        if result.get("state") != "JOB_STATE_SUCCEEDED":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
