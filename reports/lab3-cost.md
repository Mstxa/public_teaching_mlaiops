# Lab 3 cost report

Recorded `2026-09-22T16:04:19.827191+00:00`.

## Warm endpoint

- Provider: `gcp`
- Instance: `n1-standard-2`
- Hourly rate: 3.80 THB/hour
- Measured throughput: 55.735 requests/second
- Utilisation assumption: 100%

    THB per 1,000
      = hourly rate * 1,000
        / (throughput * 3,600 * utilisation)
      = 0.018939 THB

## One-size-up comparison

| Instance | THB/hour | Throughput (req/s) | THB/1,000 |
|---|---:|---:|---:|
| `n1-standard-2` | 3.80 | 53.211 | 0.01984 |
| `n1-standard-4` | 7.60 | 78.565 | 0.02687 |

The larger instance changes unit cost by
+35.46%.

## Batch inference break-even

Assumption: one scheduled batch run per day uses `n1-standard-2` for
0.50 hours and costs 1.90 THB.

The repository planning model gives a break-even request rate of
0.0010 req/s, approximately 89.3
predictions per day.

Below that volume, scheduled batch inference is cheaper than keeping
the endpoint warm. Above it, the latency requirement and available
batch window determine which mode is appropriate.
