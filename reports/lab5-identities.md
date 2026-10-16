# Lab 5 — Scoped Identities and Permission Boundary

**Evidence date:** 2026-10-16
**Project:** `itcs355-6688121`

## Identity separation

| Identity | Permission | Why it is needed |
|---|---|---|
| Training: `itcs355-lab2-train` | `roles/aiplatform.user` | Run the managed Vertex AI training pipeline and create its outputs. |
| Training: `itcs355-lab2-train` | `roles/storage.objectAdmin` on the ML bucket | Read training data and write model artifacts, evaluation results, and pipeline outputs. |
| Training: `itcs355-lab2-train` | `roles/storage.bucketViewer` | Read bucket metadata needed by storage operations. |
| Training: `itcs355-lab2-train` | `roles/artifactregistry.reader` on repository `itcs355` | Pull the digest-pinned training container. |
| Training: `itcs355-lab2-train` | `roles/monitoring.metricWriter` | Publish training and evaluation metrics. |
| Serving: `itcs355-lab5-serve` | `roles/storage.objectViewer` on the ML bucket | Read the registered model artifact without permission to overwrite or delete it. |
| Serving: `itcs355-lab5-serve` | `roles/logging.logWriter` | Write serving logs without broader project administration rights. |
| Serving: `itcs355-lab5-serve` | `roles/monitoring.metricWriter` | Publish request, latency, and prediction metrics. |
| CI: `itcs355-lab4-deploy` | `roles/artifactregistry.writer` on repository `itcs355` | Push commit-SHA-tagged serving images. |
| CI: `itcs355-lab4-deploy` | `roles/aiplatform.user` | Trigger the managed pipeline and perform Vertex AI deployment operations. |
| CI: `itcs355-lab4-deploy` | `roles/storage.objectViewer` on the ML bucket | Read deployment artifacts and lineage without modifying training output. |
| CI: `itcs355-lab4-deploy` | `roles/iam.serviceAccountUser` on the training identity | Submit pipeline work that runs as the scoped training identity. |
| GitHub repository principal | `roles/iam.workloadIdentityUser` on the CI identity | Authenticate the named GitHub repository through short-lived OIDC credentials; no service-account key is stored. |

The identities are not interchangeable. Training may write artifacts but cannot
push images. Serving may read artifacts but cannot alter them. CI may push and
deploy but has only read access to the ML bucket; pipeline execution is
delegated to the training identity.

## Permission-removal experiment

I tested the hypothesis that the serving identity might not need direct object
read access because a managed serving platform could materialise the model
artifact on its behalf. A probe object was uploaded under the Lab 5 storage
prefix and read while impersonating only `itcs355-lab5-serve`.

With `roles/storage.objectViewer` present, the serving identity read the object
successfully (`BEFORE_EXIT=0`). I then removed that bucket-level role and
repeated the identical read. It failed with HTTP 403 and explicitly reported
that `storage.objects.get` was denied (`REMOVED_EXIT=1`). After restoring the
same role, the identical read succeeded again (`RESTORED_EXIT=0`).

Therefore direct object read access is a real serving dependency, not a
permission that can be removed. The role remains narrowly scoped to viewer:
the serving identity still cannot create, overwrite, or delete artifacts. The
temporary probe object was deleted after the test.

## Evidence

- `reports/lab5-identities-final.txt` records the final roles of all three identities.
- `reports/lab5-identity-permission-test.txt` records the success, 403 failure, and restored success.
- `reports/lab5-bucket-iam-before.json` records the earlier bucket policy.
- `reports/lab5-artifact-registry-iam.json` records training-reader and CI-writer separation.
- `.github/workflows/cd.yml` records GitHub OIDC authentication as the CI identity.
