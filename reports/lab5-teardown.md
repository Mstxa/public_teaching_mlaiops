# Lab 5 teardown evidence

Date: 2026-10-15

Primary provider: GCP

Portability provider: Azure

## Scope checked before deletion

- One succeeded Vertex AI Pipeline Job labelled for Lab 5:
  `projects/475085312620/locations/asia-southeast1/pipelineJobs/itcs355-training-pipeline-20261015133913`
- Pipeline artifacts under:
  `gs://itcs355-6688121-mlops/itcs355/lab5/`
- No Vertex endpoint or model carrying the Lab 5 labels.
- Azure resource group `itcs355-lab5-portability` contained one Storage
  account, one Container Apps managed environment, and one Container App.

The shared GCS bucket, training service account, and container images were
intentionally retained because earlier labs also use them.

## Deletion performed

`make teardown LAB=5` deleted the labelled Vertex Pipeline Job and the Lab 5
GCS prefix. The Azure resource group was submitted for deletion as one scoped
operation, which removed its three contained resources.

Command output is retained in:

- `reports/lab5-teardown-gcp.txt`
- `reports/lab5-teardown-verify.txt`
- `reports/lab5-teardown-azure.txt`

## Automated verification

- `scripts/teardown_verify.py --lab 5`: **PASS** — nothing remained under the
  exact Lab 5 labels.
- GCS recursive listing: **PASS** — no objects matched the Lab 5 prefix.
- Azure resource-group existence check: **PASS** — returned `false`.

Automated verification cannot detect an unlabelled resource. Final console
screenshots provide an independent manual check:

- `reports/evidence/lab5-gcp-teardown-console.png` shows an empty Pipeline Runs
  table for project `itcs355-6688121` in `asia-southeast1`.
- `reports/evidence/lab5-azure-teardown-console.png` shows no resource group
  matching `itcs355-lab5-portability` in the Azure for Students subscription.

The delayed billing check remains separate follow-up evidence because provider
billing reports are not real-time.
