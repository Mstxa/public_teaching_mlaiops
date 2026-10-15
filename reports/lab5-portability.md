# Lab 5 — Portability Test

## Evidence

- Primary provider: GCP
- Second provider: Azure
- Azure Blob container: private `portability` container in `malaysiawest`
- Azure invocation target: Container Apps Express in `malaysiawest`
- Container App scaling: minimum 0, maximum 1 replica
- `upload`: `PASS`
- `download`: `PASS`, including an exact content comparison
- `invoke`: `PASS`, using an HTTPS JSON `POST`
- `make swap-check SECOND=azure` exit status: `0`

## Findings

`invoke` was the hardest of the three methods to port. The Python request itself was
small, but obtaining an equivalent managed endpoint exposed several platform
constraints. Azure Container Registry could be created in Malaysia West, while its
remote build operation was unavailable there. Recreating the registry in East Asia
allowed the source upload, but the Azure for Students subscription then rejected ACR
Tasks entirely. The proof therefore used the versioned public
`ealen/echo-server:0.9.2` image on Azure Container Apps Express. Blob upload and
download were more direct, although they still required Azure RBAC, a private
container, `DefaultAzureCredential`, and Azure-specific URI parsing inside the
adapter.

The abstraction genuinely leaked through resource configuration and deployment
semantics. A neutral `upload(local_path, key)` interface can hide the Blob SDK, but it
cannot invent the Azure account/container URL, endpoint FQDN, allowed region, RBAC
assignment, or subscription quota. The swap check therefore needed separate
`SECOND_BLOB_URI` and `SECOND_ENDPOINT` values. Keeping these details out of `src/`
preserved Layer 1 portability, but did not eliminate provider-specific operations.

A complete production migration is estimated at **10–14 engineering days** for one
engineer: 1–2 days for identity and RBAC, 1–2 for data transfer and integrity checks,
2–3 for image build and serving, 3–4 for managed training, registry, and pipeline
equivalents, and 2–3 for monitoring, rollback, cost validation, and runbooks. This
excludes organizational security review and large-data transfer time.

The abstraction was worth building as a deliberately narrow seam, not as a promise
of effortless multi-cloud operation. All three required operations changed provider
without modifying the neutral application layer, and the audit can enforce that
boundary. Extending the interface to hide every training, registry, scaling, and
quota difference would add more complexity than value; those differences should
remain explicit in adapters and deployment configuration.
