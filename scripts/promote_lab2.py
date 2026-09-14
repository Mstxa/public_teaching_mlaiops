"""Promote a verified Vertex model version to the staging alias."""
from __future__ import annotations

import argparse

from cloudlayer.factory import get_adapter
from src import config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    cfg = config.load()
    model = get_adapter(cfg).promote_model_to_staging(cfg.model_registry_name, args.version)
    print(f"Staging: {cfg.model_registry_name}@{model['versionId']}")


if __name__ == "__main__":
    main()
