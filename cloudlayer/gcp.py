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
import json
import os
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlparse

import google.auth
from google.api_core.exceptions import NotFound
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
        try:
            blob.download_to_filename(destination)
        except NotFound as exc:
            raise FileNotFoundError(uri) from exc

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
            "scheduling": {"timeout": f"{int(args.get('timeout_s', 1800))}s"},
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
        # Vertex may return the project number even when creation used its string ID.
        pattern = rf"projects/[^/]+/locations/{re.escape(self.cfg.region)}/customJobs/[0-9]+"
        if not re.fullmatch(pattern, job_id):
            raise ValueError("Job ID is not a Vertex custom job in the configured region")
        terminal = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
        deadline = time.monotonic() + 1900
        session = self._vertex_session()
        previous_state = None
        while time.monotonic() < deadline:
            response = session.get(self._vertex_url(job_id), timeout=60)
            response.raise_for_status()
            job = response.json()
            state = job.get("state", "JOB_STATE_UNSPECIFIED")
            if state != previous_state:
                print(f"{job_id}: {state}", flush=True)
                previous_state = state
            if state in terminal:
                return job
            time.sleep(20)
        raise TimeoutError(f"Timed out waiting for {job_id}; the cloud job may still be running")

    def get_model_version(self, name: str, version: str) -> dict[str, Any]:
        """Read one explicit Vertex Model Registry version."""
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,62}", name):
            raise ValueError("Invalid Vertex model ID")
        if not re.fullmatch(r"[0-9]+|[a-z][a-z0-9-]+", version):
            raise ValueError("Invalid Vertex model version or alias")
        resource = f"projects/{self.cfg.project_id}/locations/{self.cfg.region}/models/{name}@{version}"
        response = self._vertex_session().get(self._vertex_url(resource), timeout=60)
        response.raise_for_status()
        return response.json()

    def register_model(self, model_uri: str, name: str) -> str:
        """Upload a GCS model to Vertex, carrying exact lineage on its version."""
        if not model_uri.endswith("/model.joblib"):
            raise ValueError("Expected a GCS model.joblib URI")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,62}", name):
            raise ValueError("Invalid Vertex model ID")
        artifact_uri = model_uri.rsplit("/", 1)[0]
        with TemporaryDirectory(prefix="itcs355-lineage-") as directory:
            sidecar = Path(directory) / "lineage.json"
            self.download(f"{artifact_uri}/lineage.json", str(sidecar))
            lineage = json.loads(sidecar.read_text())
        required = (
            "git_commit", "data_version", "mlflow_run_id", "training_job_id",
            "image_digest", "seed", "metric_val", "metric_test",
        )
        if any(lineage.get(key) in (None, "") for key in required):
            raise ValueError("Model lineage must contain all eight required fields")
        if lineage.get("model_uri") != model_uri:
            raise ValueError("Lineage model_uri does not match the model being registered")
        image_uri = lineage.get("training_image_uri", "")
        if not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image_uri):
            raise ValueError("A digest-pinned container image is required")
        if lineage["image_digest"] != image_uri.rsplit("@", 1)[1]:
            raise ValueError("Image digest in lineage does not match the container")

        parent = f"projects/{self.cfg.project_id}/locations/{self.cfg.region}"
        model_resource = f"{parent}/models/{name}"
        session = self._vertex_session()
        existing = session.get(self._vertex_url(model_resource), timeout=60)
        if existing.status_code == 200:
            model = existing.json()
            if json.loads(model.get("versionDescription", "{}")) != lineage:
                raise ValueError("Model ID already exists with different lineage; choose a new ID")
            return str(model["versionId"])
        if existing.status_code != 404:
            existing.raise_for_status()

        body = {
            "modelId": name,
            "model": {
                "displayName": name,
                "artifactUri": artifact_uri,
                "containerSpec": {"imageUri": image_uri},
                "versionDescription": json.dumps(lineage, sort_keys=True),
                "labels": self.cfg.tags(2),
            },
        }
        response = session.post(self._vertex_url(f"{parent}/models:upload"), json=body, timeout=60)
        response.raise_for_status()
        operation_name = response.json()["name"]
        deadline = time.monotonic() + 1200
        while time.monotonic() < deadline:
            operation = session.get(self._vertex_url(operation_name), timeout=60)
            operation.raise_for_status()
            result = operation.json()
            if result.get("done"):
                if result.get("error"):
                    raise RuntimeError(f"Vertex model upload failed: {result['error']}")
                version = str(result["response"]["modelVersionId"])
                registered = self.get_model_version(name, version)
                if json.loads(registered.get("versionDescription", "{}")) != lineage:
                    raise RuntimeError("Registered model lost its lineage")
                return version
            time.sleep(10)
        raise TimeoutError(f"Model upload is still running: {operation_name}")

    def promote_model_to_staging(self, name: str, version: str) -> dict[str, Any]:
        """Assign the mutable staging alias after a successful reload check."""
        model = self.get_model_version(name, version)
        if "staging" in model.get("versionAliases", []):
            return model
        resource = f"projects/{self.cfg.project_id}/locations/{self.cfg.region}/models/{name}@{version}"
        response = self._vertex_session().post(
            self._vertex_url(f"{resource}:mergeVersionAliases"),
            json={"versionAliases": ["staging"]}, timeout=60,
        )
        response.raise_for_status()
        promoted = response.json()
        if "staging" not in promoted.get("versionAliases", []):
            raise RuntimeError("Vertex did not retain the staging alias")
        return promoted

    def teardown(self, tags: dict[str, str]) -> list[str]:
        """Cancel only active Lab 2 jobs; terminal jobs already release compute."""
        if tags == self.cfg.tags(3):
            return self._teardown_lab3(tags)
        if tags != self.cfg.tags(2):
            raise ValueError("This teardown implementation is scoped to Lab 2 or Lab 3")
        parent = f"projects/{self.cfg.project_id}/locations/{self.cfg.region}"
        session = self._vertex_session()
        label_filter = " AND ".join(f"labels.{key}={value}" for key, value in tags.items())
        terminal = {
            "JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED",
            "JOB_STATE_EXPIRED",
        }
        cancelled: list[str] = []
        page_token = ""
        while True:
            params = {"filter": label_filter, "pageSize": 100}
            if page_token:
                params["pageToken"] = page_token
            response = session.get(self._vertex_url(f"{parent}/customJobs"), params=params, timeout=60)
            response.raise_for_status()
            page = response.json()
            for job in page.get("customJobs", []):
                if job.get("state") in terminal:
                    continue
                job_name = job["name"]
                cancellation = session.post(self._vertex_url(f"{job_name}:cancel"), json={}, timeout=60)
                cancellation.raise_for_status()
                cancelled.append(job_name)
            page_token = page.get("nextPageToken", "")
            if not page_token:
                break
        return cancelled

    def _gcloud_json(
        self,
        args: list[str],
        *,
        input_text: str | None = None,
        check: bool = True,
    ) -> Any:
        command = [
            "gcloud",
            *args,
            f"--project={self.cfg.project_id}",
            "--quiet",
            "--format=json",
        ]
        result = subprocess.run(
            command,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            if not check:
                return None
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(
                f"gcloud command failed ({result.returncode}): {detail}"
            )

        output = result.stdout.strip()
        return json.loads(output) if output else {}

    def deploy(
        self,
        model_ref: str,
        endpoint: str,
        instance: str,
    ) -> dict[str, Any]:
        if "@" not in model_ref:
            raise ValueError("model_ref must use NAME@VERSION")

        model_name, model_version = model_ref.rsplit("@", 1)
        source_model = self.get_model_version(model_name, model_version)
        artifact_uri = source_model.get("artifactUri")
        if not artifact_uri:
            raise RuntimeError(
                f"Registered model {model_ref} has no artifactUri"
            )

        report_path = self.cfg.reports_dir / "lab3-serving-image-uri.txt"
        image_uri = os.environ.get("SERVING_IMAGE_URI", "").strip()
        if not image_uri and report_path.exists():
            image_uri = report_path.read_text().strip()

        if not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image_uri):
            raise RuntimeError(
                "SERVING_IMAGE_URI must be an immutable @sha256 URI"
            )

        safe_name = re.sub(r"[^a-z0-9_-]", "-", model_name.lower())
        safe_version = re.sub(r"[^a-z0-9_-]", "-", model_version.lower())
        serving_model_id = f"{safe_name}-serve-v{safe_version}"
        endpoint_id = re.sub(r"[^a-z0-9_-]", "-", endpoint.lower())
        deployed_name = f"{serving_model_id}-deployment"

        labels = ",".join(
            f"{key}={value}" for key, value in self.cfg.tags(3).items()
        )
        env_vars = {
            "CLOUD_PROVIDER": self.cfg.provider,
            "PROJECT_ID": self.cfg.project_id,
            "REGION": self.cfg.region,
            "BLOB_URI": self.cfg.blob_uri,
            "CONTAINER_REGISTRY": self.cfg.container_registry,
            "MLFLOW_TRACKING_URI": self.cfg.mlflow_tracking_uri,
            "MODEL_REGISTRY_NAME": model_name,
            "MODEL_VERSION": model_version,
            "IDENTITY_REF": self.cfg.identity_ref,
        }
        container_env = ",".join(
            f"{key}={value}" for key, value in env_vars.items()
        )

        serving_model = self._gcloud_json(
            [
                "ai",
                "models",
                "describe",
                serving_model_id,
                f"--region={self.cfg.region}",
            ],
            check=False,
        )
        if serving_model is None:
            self._gcloud_json(
                [
                    "ai",
                    "models",
                    "upload",
                    f"--model-id={serving_model_id}",
                    f"--display-name={serving_model_id}",
                    f"--artifact-uri={artifact_uri}",
                    f"--container-image-uri={image_uri}",
                    "--container-ports=8080",
                    "--container-health-route=/ready",
                    "--container-predict-route=/predict/managed",
                    f"--container-env-vars={container_env}",
                    f"--labels={labels}",
                    (
                        "--version-description="
                        f"Lab 3 serving model for {model_ref}; image={image_uri}"
                    ),
                    f"--region={self.cfg.region}",
                ]
            )
            serving_model = self._gcloud_json(
                [
                    "ai",
                    "models",
                    "describe",
                    serving_model_id,
                    f"--region={self.cfg.region}",
                ]
            )

        endpoint_state = self._gcloud_json(
            [
                "ai",
                "endpoints",
                "describe",
                endpoint_id,
                f"--region={self.cfg.region}",
            ],
            check=False,
        )
        if endpoint_state is None:
            self._gcloud_json(
                [
                    "ai",
                    "endpoints",
                    "create",
                    f"--endpoint-id={endpoint_id}",
                    f"--display-name={endpoint_id}",
                    f"--labels={labels}",
                    f"--region={self.cfg.region}",
                ]
            )
            endpoint_state = self._gcloud_json(
                [
                    "ai",
                    "endpoints",
                    "describe",
                    endpoint_id,
                    f"--region={self.cfg.region}",
                ]
            )

        deployed_models = endpoint_state.get("deployedModels", [])
        already_deployed = any(
            item.get("displayName") == deployed_name
            for item in deployed_models
        )
        if not already_deployed:
            service_account = self.cfg.identity_ref.removeprefix(
                "serviceAccount:"
            )
            self._gcloud_json(
                [
                    "ai",
                    "endpoints",
                    "deploy-model",
                    endpoint_id,
                    f"--model={serving_model_id}",
                    f"--display-name={deployed_name}",
                    f"--machine-type={instance}",
                    "--min-replica-count=1",
                    "--max-replica-count=1",
                    f"--service-account={service_account}",
                    f"--region={self.cfg.region}",
                ]
            )
            endpoint_state = self._gcloud_json(
                [
                    "ai",
                    "endpoints",
                    "describe",
                    endpoint_id,
                    f"--region={self.cfg.region}",
                ]
            )

        return {
            "endpoint": endpoint_state["name"],
            "model": serving_model["name"],
            "source_model": model_ref,
            "serving_image": image_uri,
        }

    def invoke(
        self,
        endpoint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        endpoint_id = endpoint.rstrip("/").rsplit("/", 1)[-1]
        response = self._gcloud_json(
            [
                "ai",
                "endpoints",
                "predict",
                endpoint_id,
                "--json-request=-",
                f"--region={self.cfg.region}",
            ],
            input_text=json.dumps({"instances": [payload]}),
        )
        if not response.get("predictions"):
            raise RuntimeError(
                f"Vertex endpoint returned no predictions: {response}"
            )
        return response

    def _teardown_lab3(self, tags: dict[str, str]) -> list[str]:
        label_filter = " AND ".join(
            f"labels.{key}={value}" for key, value in tags.items()
        )
        removed: list[str] = []

        endpoints = self._gcloud_json(
            [
                "ai",
                "endpoints",
                "list",
                f"--region={self.cfg.region}",
                f"--filter={label_filter}",
            ]
        )
        for endpoint in endpoints:
            endpoint_name = endpoint["name"]
            endpoint_id = endpoint_name.rsplit("/", 1)[-1]
            details = self._gcloud_json(
                [
                    "ai",
                    "endpoints",
                    "describe",
                    endpoint_id,
                    f"--region={self.cfg.region}",
                ]
            )
            for deployed in details.get("deployedModels", []):
                self._gcloud_json(
                    [
                        "ai",
                        "endpoints",
                        "undeploy-model",
                        endpoint_id,
                        f"--deployed-model-id={deployed['id']}",
                        f"--region={self.cfg.region}",
                    ]
                )
            self._gcloud_json(
                [
                    "ai",
                    "endpoints",
                    "delete",
                    endpoint_id,
                    f"--region={self.cfg.region}",
                ]
            )
            removed.append(endpoint_name)

        models = self._gcloud_json(
            [
                "ai",
                "models",
                "list",
                f"--region={self.cfg.region}",
                f"--filter={label_filter}",
            ]
        )
        seen: set[str] = set()
        for model in models:
            model_name = model["name"].split("@", 1)[0]
            model_id = model_name.rsplit("/", 1)[-1]
            if model_id in seen:
                continue
            seen.add(model_id)
            self._gcloud_json(
                [
                    "ai",
                    "models",
                    "delete",
                    model_id,
                    f"--region={self.cfg.region}",
                ]
            )
            removed.append(model_name)

        return removed

    # deploy / invoke                   -> Lab 3 (Vertex Endpoint)
    # emit_metric                       -> Lab 4 (Cloud Monitoring time series)
    # generate                          -> Lab 5 (managed LLM endpoint; read usageMetadata for tokens)
