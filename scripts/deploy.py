"""Deploy one registered model version to the staging endpoint."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.factory import get_adapter
from src import config


DIGEST_IMAGE = re.compile(r".+@sha256:[0-9a-f]{64}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version-file", type=Path, required=True)
    parser.add_argument("--serving-image", required=True)
    parser.add_argument("--target", choices=["staging"], default="staging")
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--instance", default="n1-standard-2")
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.version_file.is_file():
        raise SystemExit(
            f"Registered model version file not found: {args.version_file}"
        )
    if not DIGEST_IMAGE.fullmatch(args.serving_image):
        raise SystemExit(
            "--serving-image must be digest-pinned: repository@sha256:<64 hex>"
        )

    version = args.version_file.read_text().strip()
    if not version or any(character.isspace() for character in version):
        raise SystemExit("Registered model version is empty or invalid")

    cfg = config.load()
    adapter = get_adapter(cfg)
    endpoint = args.endpoint or f"{cfg.project_id}-lab5-{args.target}"
    model_ref = f"{cfg.model_registry_name}@{version}"

    os.environ["SERVING_IMAGE_URI"] = args.serving_image

    result = adapter.deploy(
        model_ref=model_ref,
        endpoint=endpoint,
        instance=args.instance,
    )

    record = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "target": args.target,
        "model_ref": model_ref,
        "endpoint": endpoint,
        "instance": args.instance,
        "serving_image": args.serving_image,
        "result": result,
    }

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n")

    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
