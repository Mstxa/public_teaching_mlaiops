# Lab 5 — Cost Report (Provisional)

Provider `gcp` · planning instance `n1-standard-2` · 3.80 THB/hour

> Billing observation captured on 2026-10-15. The console graph contained posted
> usage only through 2026-10-14, before the first Lab 5 pipeline run on 2026-10-15.
> Therefore the Lab 5 actual and gap remain pending rather than being reported as a
> misleading zero. Evidence: [billing summary](evidence/lab5-billing-summary-provisional.png)
> and [service table](evidence/lab5-billing-services-provisional.png).

## 1. Estimate made before running

The committed pre-run estimate was **70.00 THB**, including contingency. The largest
planned line was 30.40 THB for keeping a serving instance online for eight hours.

## 2. Actual from billing

**Pending the normal Cloud Billing reporting delay.** The project-level report showed
1.46 THB of current-month usage before savings, -1.46 THB of savings, and 0.00 THB
net. Those values include earlier labs and are not a tag-filtered Lab 5 actual:

| Current-month service | Usage cost (THB) | Net subtotal (THB) |
|---|---:|---:|
| Artifact Registry | 0.00 | 0.00 |
| Cloud Run | 0.63 | 0.00 |
| Cloud Monitoring | 0.00 | 0.00 |
| Cloud Storage | 0.01 | 0.00 |
| Vertex AI | 0.82 | 0.00 |
| Dataplex | 0.00 | 0.00 |
| Cloud Logging | 0.00 | 0.00 |
| **Total shown** | **1.46** | **0.00** |

The report must be updated after charges through 2026-10-15 appear, filtered to the
Lab 5 labels, and stated both before and after credits.

## 3. Gap

**Pending.** Computing `0.00 - 70.00` now would describe billing latency and credits,
not the difference between estimated and consumed resources. The expected downward
drivers are the short pipeline duration, no paid online model deployment because the
evaluation gate rejected the candidate, small artifacts, and free-tier or promotional
credits. Failed deployment experiments and delayed resource deletion are upward
drivers and must be included once posted.

## 4. Breakdown by component

| Component | Actual THB | Status and attribution rule |
|---|---:|---|
| Training | Pending | Vertex AI custom-job SKUs carrying the Lab 5 labels |
| Storage | Pending | Cloud Storage bytes and operations for Lab 5 artifacts |
| Serving | Pending | Expected near zero: the gated Vertex deployment was not triggered |
| Pipeline | Pending | Vertex AI Pipelines orchestration and component execution |
| Monitoring | Pending | Cloud Logging and Cloud Monitoring usage |

The unfiltered current-month table above is retained as evidence, but is deliberately
not copied into this component breakdown because it includes previous labs.

## 5. Cost per 1,000 predictions

Measured Lab 3 throughput was **55.735 requests/second**. At 3.80 THB/hour:

| Utilisation | THB per 1,000 predictions |
|---:|---:|
| 5% | 0.3788 |
| 25% | 0.0758 |
| 80% | 0.0237 |

The 25% case is the most credible planning figure for a variable interactive workload;
80% is optimistic outside sustained load, while 5% represents a lightly used endpoint.
With a daily batch job costing an assumed 1.90 THB, the repository model gives a
break-even rate of about **0.0010 requests/second**, or **89 predictions/day**. Below
that volume, scheduled batch inference is cheaper than a continuously warm endpoint.

## 6. Optimisation actually applied

Lab 3 right-sizing replaced `n1-standard-4` with `n1-standard-2` after measuring both:

| Metric | Before: `n1-standard-4` | After: `n1-standard-2` |
|---|---:|---:|
| Hourly price | 7.60 THB | 3.80 THB |
| Measured throughput | 78.565 req/s | 53.211 req/s |
| THB per 1,000 at measured utilisation | 0.02687 | 0.01984 |
| P95 latency | 187.85 ms | 336.04 ms |

This halved hourly cost and reduced unit cost by about 26%, while P95 latency increased
by about 79% but remained below the committed 500 ms target. For Lab 5, the evaluation
gate supplied an additional optimisation: it did not create a paid serving endpoint for
a candidate that failed to improve on production.

## Finalisation

After billing has posted for 2026-10-15, replace the pending values with the
tag-filtered service/SKU amounts, calculate the numeric gap from 70.00 THB, and retain
the before-credit and net totals so promotional savings do not hide resource usage.
