# Lab 5 — Cost Report

Provider `gcp` · planning instance `n1-standard-2` · 3.80 THB/hour

> Billing was finalised from the CSV export captured on 2026-10-16. The export
> contains one managed pipeline job and its Training/Pipelines SKUs. Evidence:
> [billing CSV](evidence/lab5-billing-export-2026-10-16.csv),
> [billing summary](evidence/lab5-billing-delay-2026-10-16-summary.png), and
> [service table](evidence/lab5-billing-delay-2026-10-16-services.png).

## 1. Estimate made before running

The committed pre-run estimate was **70.00 THB**, including contingency. The largest
planned line was 30.40 THB for keeping a serving instance online for eight hours.

## 2. Actual from billing

The Lab 5 managed pipeline incurred **1.09 THB before credits**, received
**-1.09 THB** of promotional/free-trial savings, and therefore had a **0.00 THB net
subtotal**. The attribution is supported by one `AI Pipeline job: Managed Pipeline
job count` and the associated Training/Pipelines compute and disk SKUs:

| Lab 5 SKU | Usage | List cost (THB) | Savings (THB) | Net (THB) |
|---|---:|---:|---:|---:|
| Managed Pipeline job | 1 job | 1.01 | -1.01 | 0.00 |
| E2 instance core | 0.04 hour | 0.05 | -0.05 | 0.00 |
| E2 instance RAM | 0.17 GiB-hour | 0.02 | -0.02 | 0.00 |
| SSD-backed persistent disk | rounded to 0 GiB-month | 0.01 | -0.01 | 0.00 |
| **Lab 5 actual** | | **1.09** | **-1.09** | **0.00** |

The current-month Vertex AI total moved from 0.82 THB in the pre-run observation to
1.91 THB in the export. The 1.09 THB increase exactly matches the four Lab 5 rows
above. Other current-month services are excluded because they include earlier labs.

## 3. Gap

Using before-credit resource cost, the gap is:

`1.09 - 70.00 = -68.91 THB`

Actual cost was **68.91 THB below estimate**, or about **98.4% lower**. The estimate
was deliberately conservative: the pipeline was short, the evaluation gate rejected
the candidate before a paid GCP serving endpoint was created, artifacts were small,
and the eight-hour serving allowance was unused. Credits reduced the billed net to
zero but are not used to hide the consumed-resource comparison.

## 4. Breakdown by component

| Component | Actual THB before credits | Evidence and attribution |
|---|---:|---|
| Training compute and disk | 0.08 | Three Training/Pipelines E2 and disk SKU rows |
| Pipeline orchestration | 1.01 | One managed Pipeline job count |
| Storage | 0.00 rounded | Current-month Cloud Storage remained 0.01 THB; Lab 5 increment rounded to zero |
| Serving | 0.00 | The failed gate prevented GCP endpoint creation |
| Monitoring and logging | 0.00 | Exported rows rounded to zero and were not incremental to Lab 5 |
| LLM evaluation | 0.00 | Evaluation used committed recorded responses rather than paid online calls |
| **Total** | **1.09** | Reconciles to the increase in current-month Vertex AI cost |

The project-month CSV is retained unchanged. Its unrelated Cloud Run, prediction,
storage, monitoring, logging, scheduler, registry, and Dataplex rows are not assigned
to Lab 5.

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

## Billing conclusion

The billing export closes the provisional observation: Lab 5 consumed 1.09 THB of
resources before credits and billed 0.00 THB net. The cost report uses the before-credit
amount for estimate accuracy and records the credits separately.
