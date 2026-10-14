# Lab 5 — Pre-run Cost Estimate

Estimate recorded before running the Lab 5 managed pipeline.

- Provider: GCP
- Project: itcs355-6688121
- Region: asia-southeast1
- Currency: THB
- Budget limit: 800 THB
- Estimate date: 2026-10-14

## Assumptions

| Component | Assumption | Estimated THB |
|---|---|---:|
| Training | n1-standard-2 Spot, approximately 2 hours including failed runs | 2.28 |
| Storage | Existing GCS bucket, less than 5 GB additional data and artifacts | 1.00 |
| Serving | n1-standard-2 endpoint, kept online no longer than 8 hours | 30.40 |
| Pipeline | Vertex AI pipeline orchestration and temporary resources | 10.00 |
| Monitoring | Logs and metrics generated during testing | 2.00 |
| LLM evaluation | Small managed model, approximately 100 test requests | 2.00 |
| Contingency | Failed runs, delayed deletion, and billing variation | 22.32 |
| **Total estimated cost** | | **70.00** |

## Calculation

The repository's current cost model estimates `n1-standard-2` at 3.80 THB/hour.

Spot training estimate:

`3.80 × 0.30 × 2 hours = 2.28 THB`

Serving estimate:

`3.80 × 8 hours = 30.40 THB`

The largest uncertainty is serving duration. The endpoint will be deleted immediately
after evidence and load measurements are captured.

This estimate was written and committed before the first Lab 5 pipeline execution.
Actual billing will be filtered using the labels `course=itcs355`,
`student=itcs355-6688121`, and `lab=5`.
