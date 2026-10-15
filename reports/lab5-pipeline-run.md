# Lab 5 — First Managed Pipeline Run

## Run identity

- Display name: `itcs355-lab5-first-gated-run`
- Pipeline job: `itcs355-training-pipeline-20261015133913`
- Region: `asia-southeast1`
- Final state: `PIPELINE_STATE_SUCCEEDED`
- Training service account: `itcs355-lab2-train@itcs355-6688121.iam.gserviceaccount.com`
- Training image: `asia-southeast1-docker.pkg.dev/itcs355-6688121/itcs355/itcs355-lab1@sha256:f9f1060974848e8f201ecd143d70696c4c2d8bf7b39341e8f554fee13e698046`

## Task results

- `ingest-component`: `SUCCEEDED`
- `validate-component`: `SUCCEEDED`
- `train-component`: `SUCCEEDED`
- `evaluate-component`: `SUCCEEDED`
- Conditional registration/deployment branch: `NOT_TRIGGERED`

## Evaluation gate

- Decision: `fail`
- Candidate test ROC AUC: `0.8482378548603715`
- Production test ROC AUC: `0.8532857870606215`
- Required improvement: `0.002`
- Required candidate ROC AUC: `0.8552857870606215`
- Candidate minus production: `-0.005047932200250016`
- Candidate minus required threshold: `-0.007047932200250018`

The candidate exceeded the absolute quality floor but did not improve on the
production model by the required margin. The gate therefore prevented model
registration and staging deployment. This is the expected safe outcome: a
successful pipeline run does not imply that every candidate should be promoted.

## Traceability

- MLflow run ID: `85b272362a5840f3939d43ae47b21fae`
- Data fingerprint: `422cccb9136e8140`
- Evaluation custom job: `projects/475085312620/locations/asia-southeast1/customJobs/422193498490404864`
- Pipeline root: `gs://itcs355-6688121-mlops/itcs355/lab5/pipeline-root`
- Metrics and detailed submission records remain local under `reports/*.json`
  because generated JSON reports are intentionally excluded by `.gitignore`.
