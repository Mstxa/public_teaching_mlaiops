# Lab 2 cost reconciliation

Completed Spot trials: 12; failed attempts: 0.
Estimated Vertex training compute: 2.4233 THB.
Cloud Billing observed project usage cost before credits: 4.4800 THB.
Net billed after Free Trial credits: 0.0000 THB.
The observed project usage cost to date is below the 150 THB Lab 2 budget.
Billing report checked on: 2026-09-15.
Billing scope: project itcs355-6688121, charge period September 1-14, 2026; all services; Savings (None).
Service usage costs: Compute Engine 4.06 THB; Vertex AI 0.42 THB; Cloud Storage 0.00 THB; Artifact Registry 0.00 THB.
Billing evidence: [project summary](evidence/lab2-billing-project-summary.png), [service table](evidence/lab2-billing-usage-cost.png).
Comparison: the estimate covers only the 12 training trials, while the Billing observation covers the full project and may include the earlier smoke job and other services.

The estimate uses a planning rate of 12 THB/hour and excludes the earlier smoke job, storage, registry, logs, network, and taxes. The Cloud Billing amount may include those charges. Do not treat the difference between these scopes as an exact trial cost error.

| Trial | Job | Duration (s) | Estimated THB |
|---:|---|---:|---:|
| 00 | `projects/475085312620/locations/asia-southeast1/customJobs/4663414467101458432` | 61 | 0.2033 |
| 01 | `projects/475085312620/locations/asia-southeast1/customJobs/7786660808682897408` | 60 | 0.2000 |
| 02 | `projects/475085312620/locations/asia-southeast1/customJobs/8304574765830504448` | 61 | 0.2033 |
| 03 | `projects/475085312620/locations/asia-southeast1/customJobs/1204649953280917504` | 60 | 0.2000 |
| 04 | `projects/475085312620/locations/asia-southeast1/customJobs/8752682928753868800` | 61 | 0.2033 |
| 05 | `projects/475085312620/locations/asia-southeast1/customJobs/328805378873622528` | 61 | 0.2033 |
| 06 | `projects/475085312620/locations/asia-southeast1/customJobs/5625038540661325824` | 61 | 0.2033 |
| 07 | `projects/475085312620/locations/asia-southeast1/customJobs/8061485939068764160` | 60 | 0.2000 |
| 08 | `projects/475085312620/locations/asia-southeast1/customJobs/3422672769760886784` | 91 | 0.3033 |
| 09 | `projects/475085312620/locations/asia-southeast1/customJobs/4769354611460931584` | 60 | 0.2000 |
| 10 | `projects/475085312620/locations/asia-southeast1/customJobs/2244981467203502080` | 61 | 0.2033 |
| 11 | `projects/475085312620/locations/asia-southeast1/customJobs/7075197620674625536` | 30 | 0.1000 |
