"""Submit the compiled Lab 5 pipeline to Vertex AI."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.cloud import aiplatform

from src import config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--template",
        type=Path,
        default=Path("tmp/vertex-pipeline.json"),
    )
    parser.add_argument(
        "--display-name",
        default="itcs355-lab5-training-pipeline",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports/lab5-pipeline-submission.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.template.is_file():
        raise SystemExit(f"Pipeline template not found: {args.template}")

    cfg = config.load()
    pipeline_root = f"{cfg.blob_uri.rstrip('/')}/lab5/pipeline-root"

    aiplatform.init(
        project=cfg.project_id,
        location=cfg.region,
    )

    job = aiplatform.PipelineJob(
        display_name=args.display_name,
        template_path=str(args.template),
        pipeline_root=pipeline_root,
        enable_caching=False,
        labels=cfg.tags(5),
        project=cfg.project_id,
        location=cfg.region,
        failure_policy="fast",
    )

    job.submit(
        service_account=cfg.identity_ref,
        enable_preflight_validations=True,
    )

    record = {
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "resource_name": job.resource_name,
        "display_name": args.display_name,
        "project_id": cfg.project_id,
        "region": cfg.region,
        "pipeline_root": pipeline_root,
        "service_account": cfg.identity_ref,
        "template": str(args.template),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2) + "\n")

    print(json.dumps(record, indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
