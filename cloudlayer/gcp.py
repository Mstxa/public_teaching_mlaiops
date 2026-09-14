"""GCP adapter. Implement upload/download/push_image for Lab 1.

SDK:  pip install google-cloud-storage google-cloud-aiplatform
Docs: storage.Client for GCS; Artifact Registry push goes through `docker push` after
      `gcloud auth configure-docker <region>-docker.pkg.dev`.

Hints for Lab 1:
  * BLOB_URI looks like gs://bucket/prefix — parse it here, never in src/.
  * Artifact Registry paths are region-scoped:
        <region>-docker.pkg.dev/<project>/<repo>/<image>
    A common first failure is pushing to gcr.io out of habit; it is a different service.
  * push_image must return the digest reference, not the tag.
  * GCP calls them labels, not tags, and they must be lowercase with no spaces.
    cfg.tags(1) already satisfies that constraint — do not "improve" the values.
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import storage

from cloudlayer.base import CloudAdapter


def _parse_gs_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc:
        raise ValueError(f"Invalid GCS URI: {uri}")
    return parsed.netloc, parsed.path.strip("/")


class GcpAdapter(CloudAdapter):
    def _vertex_session(self) -> AuthorizedSession:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return AuthorizedSession(credentials)

    def _vertex_url(self, resource: str) -> str:
        return f"https://{self.cfg.region}-aiplatform.googleapis.com/v1/{resource}"

    def upload(self, local_path: str, key: str) -> str:
        bucket_name, prefix = _parse_gs_uri(self.cfg.blob_uri)
        object_name = "/".join(
            part for part in (prefix, key.lstrip("/")) if part
        )

        client = storage.Client(project=self.cfg.project_id)
        blob = client.bucket(bucket_name).blob(object_name)
        blob.upload_from_filename(local_path)

        return f"gs://{bucket_name}/{object_name}"

    def download(self, uri: str, local_path: str) -> None:
        bucket_name, object_name = _parse_gs_uri(uri)
        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        client = storage.Client(project=self.cfg.project_id)
        blob = client.bucket(bucket_name).blob(object_name)
        blob.download_to_filename(destination)

    def push_image(self, local_tag: str) -> str:
        registry = self.cfg.container_registry.rstrip("/")
        registry_host = registry.split("/", 1)[0]
        image_name = local_tag.rsplit("/", 1)[-1]
        remote_tag = f"{registry}/{image_name}"

        subprocess.run(
            [
                "gcloud",
                "auth",
                "configure-docker",
                registry_host,
                "--quiet",
            ],
            check=True,
        )
        subprocess.run(
            ["docker", "tag", local_tag, remote_tag],
            check=True,
        )
        result = subprocess.run(
            ["docker", "push", remote_tag],
            check=True,
            capture_output=True,
            text=True,
        )

        output = result.stdout + result.stderr
        print(output, end="")

        match = re.search(r"digest:\s*(sha256:[0-9a-f]{64})", output)
        if not match:
            raise RuntimeError("Docker push succeeded but no digest was found")

        repository = remote_tag.rsplit(":", 1)[0]
        return f"{repository}@{match.group(1)}"

    def submit_training(self, image_uri: str, args: dict[str, Any]) -> str:
        """Start one Vertex custom job and return its full resource name."""
        if not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image_uri):
            raise ValueError("Training image must be pinned by sha256 digest")
        required = ("data_uri", "output_prefix", "git_commit", "data_version")
        missing = [key for key in required if not args.get(key)]
        if missing:
            raise ValueError(f"Missing training arguments: {', '.join(missing)}")

        command_args = [
            "--data-uri", str(args["data_uri"]),
            "--output-prefix", str(args["output_prefix"]),
            "--git-commit", str(args["git_commit"]),
            "--data-version", str(args["data_version"]),
        ]
        for key in ("n_estimators", "max_depth", "min_samples_leaf", "seed"):
            if key in args:
                command_args.extend(("--" + key.replace("_", "-"), str(args[key])))

        env = {
            "CLOUD_PROVIDER": self.cfg.provider,
            "PROJECT_ID": self.cfg.project_id,
            "REGION": self.cfg.region,
            "BLOB_URI": self.cfg.blob_uri,
            "CONTAINER_REGISTRY": self.cfg.container_registry,
            "MLFLOW_TRACKING_URI": self.cfg.mlflow_tracking_uri,
            "MODEL_REGISTRY_NAME": self.cfg.model_registry_name,
            "IDENTITY_REF": self.cfg.identity_ref,
        }
        job_spec: dict[str, Any] = {
            "workerPoolSpecs": [{
                "machineSpec": {"machineType": args.get("machine_type", "e2-standard-4")},
                "replicaCount": 1,
                "containerSpec": {
                    "imageUri": image_uri,
                    "command": ["python", "-m", "scripts.remote_train"],
                    "args": command_args,
                    "env": [{"name": key, "value": value} for key, value in env.items()],
                },
            }],
            "serviceAccount": self.cfg.identity_ref,
            "scheduling": {"timeout": "1800s"},
        }
        if args.get("spot"):
            job_spec["scheduling"]["strategy"] = "SPOT"

        job = {
            "displayName": str(args.get("display_name", "itcs355-lab2-smoke")),
            "labels": self.cfg.tags(2),
            "jobSpec": job_spec,
        }
        parent = f"projects/{self.cfg.project_id}/locations/{self.cfg.region}"
        response = self._vertex_session().post(
            self._vertex_url(f"{parent}/customJobs"), json=job, timeout=60
        )
        response.raise_for_status()
        return response.json()["name"]

    def wait_training(self, job_id: str) -> dict[str, Any]:
        """Poll a custom job until it finishes or the local wait limit expires."""
        parent = f"projects/{self.cfg.project_id}/locations/{self.cfg.region}/customJobs/"
        if not job_id.startswith(parent):
            raise ValueError("Job ID does not belong to the configured project and region")
        terminal = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
        deadline = time.monotonic() + 1900
        session = self._vertex_session()
        while time.monotonic() < deadline:
            response = session.get(self._vertex_url(job_id), timeout=60)
            response.raise_for_status()
            job = response.json()
            state = job.get("state", "JOB_STATE_UNSPECIFIED")
            print(f"{job_id}: {state}", flush=True)
            if state in terminal:
                return job
            time.sleep(20)
        raise TimeoutError(f"Timed out waiting for {job_id}; the cloud job may still be running")

    # register_model                  -> Lab 2 (Vertex Model Registry)
    # deploy / invoke                   -> Lab 3 (Vertex Endpoint)
    # emit_metric                       -> Lab 4 (Cloud Monitoring time series)
    # generate                          -> Lab 5 (managed LLM endpoint; read usageMetadata for tokens)
    # teardown                          -> Lab 5 (filter resources by label)
