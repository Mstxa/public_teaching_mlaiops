"""Azure adapter. Implement upload/download/push_image for Lab 1.

SDK:  pip install azure-storage-blob azure-identity azure-containerregistry
Docs: BlobServiceClient for storage; ACR push goes through `docker push` after
      `az acr login --name <registry>`.

Hints for Lab 1:
  * BLOB_URI is either abfss://container@account.dfs.core.windows.net/prefix or
    https://account.blob.core.windows.net/container/prefix. Pick one form and parse
    it here, never in src/.
  * Use DefaultAzureCredential rather than a connection string. It picks up your CLI
    login locally and your managed identity in CI, which is what Lab 4 needs.
  * push_image must return the digest reference: registry.azurecr.io/repo@sha256:...
  * Azure tags live on the resource, not the blob. Tag the storage account, the
    registry, and later the workspace with cfg.tags(1).
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from cloudlayer.base import CloudAdapter


def _split_blob_root(uri: str) -> tuple[str, str, str]:
    """Return account URL, container name, and optional blob prefix."""
    parsed = urlparse(uri)
    if parsed.scheme != "https" or not parsed.netloc.endswith(".blob.core.windows.net"):
        raise ValueError(
            "Azure BLOB_URI must use "
            "https://<account>.blob.core.windows.net/<container>[/prefix]"
        )

    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        raise ValueError("Azure BLOB_URI must include a container name")

    account_url = f"{parsed.scheme}://{parsed.netloc}"
    container = parts[0]
    prefix = "/".join(parts[1:])
    return account_url, container, prefix


class AzureAdapter(CloudAdapter):
    def upload(self, local_path: str, key: str) -> str:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        source = Path(local_path)
        if not source.is_file():
            raise FileNotFoundError(source)

        account_url, container, prefix = _split_blob_root(self.cfg.blob_uri)
        blob_name = "/".join(part.strip("/") for part in (prefix, key) if part)
        client = BlobServiceClient(
            account_url=account_url,
            credential=DefaultAzureCredential(),
        ).get_blob_client(container=container, blob=blob_name)
        with source.open("rb") as handle:
            client.upload_blob(handle, overwrite=True)
        return client.url

    def download(self, uri: str, local_path: str) -> None:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobClient

        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        client = BlobClient.from_blob_url(uri, credential=DefaultAzureCredential())
        with destination.open("wb") as handle:
            handle.write(client.download_blob().readall())

    def push_image(self, local_tag: str) -> str:
        raise NotImplementedError("TODO Lab 1: az acr login, push, return registry/repo@sha256:...")

    def invoke(self, endpoint: str, payload: dict) -> dict:
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Azure invoke endpoint must be a full HTTPS URL")

        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=60) as response:  # noqa: S310 - HTTPS required above
            body = response.read().decode("utf-8")
        result = json.loads(body)
        return result if isinstance(result, dict) else {"response": result}

    # submit_training / register_model  -> Lab 2 (Azure ML command job + model registry)
    # deploy / invoke                   -> Lab 3. On Azure for Students, deploy to
    #                                      Container Apps, NOT an Azure ML managed
    #                                      online endpoint: those need
    #                                      ceil(1.2 x instances) x cores of quota, so
    #                                      one Standard_DS3_v2 asks for 8 vCPU against
    #                                      a student cap of about 3, and the cap cannot
    #                                      be raised. Container Apps has no Azure ML
    #                                      core quota and scales to zero.
    # emit_metric                       -> Lab 4 (Azure Monitor custom metric)
    # generate                          -> Lab 5 (managed LLM endpoint; read the usage block for tokens)
    # teardown                          -> Lab 5 (resource graph query by tag)
