# Lab 3 load-test report

## Target set before measurement

The service must achieve p95 latency below 500 ms at 10 concurrent
virtual users, with an error rate below 1%. This target represents an
interactive machine-maintenance prediction service where a response
within half a second is acceptable.

The target appeared in `loadtest/k6.js` at commit `ef8bfd6`, before
managed endpoint results were collected.

## Deployment under test

- Provider: Google Cloud Vertex AI, `asia-southeast1`
- Endpoint: `itcs355-6688121-lab3`
- Source model: `itcs355-6688121@1`
- Machine: `n1-standard-2`
- Replicas: min 1, max 1
- Duration: 60 seconds per concurrency level
- Image: `asia-southeast1-docker.pkg.dev/itcs355-6688121/itcs355/itcs355-serve@sha256:153bf1640584de74c060b5a02047f46d369b3b4bfe166fb8a29e988d2548ad1a`
- Predict route: `/predict/managed`
- Readiness route: `/ready`

## Baseline results

| VUs | Throughput (req/s) | p50 (ms) | p95 (ms) | p99 (ms) | Error rate |
|---:|---:|---:|---:|---:|---:|
| 1 | 7.859 | 98.59 | 288.60 | 307.68 | 0.00% |
| 10 | 55.735 | 161.27 | 328.55 | 448.51 | 0.00% |
| 50 | 58.398 | 806.97 | 1282.60 | 1637.36 | 0.00% |

The committed target passed at 10 VUs: p95 was 328.55 ms and the error
rate was 0.00%. Reporting p50, p95, and p99 exposes tail latency that
an average would hide.

## Breaking point

The tested breaking point lies between 10 and 50 VUs. Increasing load
from 10 to 50 VUs raised throughput only from 55.73 to 58.40 req/s,
while p95 increased from 328.55 to 1282.60 ms and p99 increased from
448.51 to 1637.36 ms. At 50 VUs the latency threshold failed even
though the HTTP error rate remained zero. This is latency saturation
rather than an availability failure.


## Batch, payload, and instance-size experiments

These experiments changed one variable at a time. The model version,
feature values, image, and replica count stayed fixed. Raw results are
stored in `reports/lab3-variable-local.txt` and the
`reports/lab3-instance-*.txt` files.

### Batch size

The local service compared 100 sequential calls to `/predict` against
one `/predict/batch` call containing the same 100 rows. Each experiment
was repeated 20 times.

| Method | HTTP requests | Rows | Median wall time (ms) | p95 (ms) | Predictions/s |
|---|---:|---:|---:|---:|---:|
| Single `/predict` | 100 | 100 | 8407.75 | 8834.39 | 11.843 |
| `/predict/batch` | 1 | 100 | 91.73 | 103.14 | 1111.164 |

Batching was 93.83 times faster in predictions per second and reduced
HTTP request count by 99%. At the same hourly machine price, cost per
1,000 predictions is inversely proportional to throughput, so this
measured speedup corresponds to a 98.93% normalized serving-cost
reduction. This local comparison isolates API and model-scoring
overhead; the absolute THB figures below use managed-endpoint results.

### Payload size

Feature values and prediction output remained unchanged. Valid JSON
whitespace was added before the closing brace so only request size
changed. This avoids adding fields that the strict Pydantic schema
correctly rejects.

| Request size | Median (ms) | p95 (ms) | Median delta |
|---:|---:|---:|---:|
| 124 B | 84.03 | 92.26 | baseline |
| 10.1 KiB | 85.33 | 92.48 | +1.55% |
| 100.1 KiB | 87.68 | 92.55 | +4.35% |
| 1.00 MiB | 89.54 | 100.67 | +6.56% |
| 5.00 MiB | 114.46 | 129.57 | +36.22% |
| 10.00 MiB | 127.42 | 147.02 | +51.64% |
| 20.00 MiB | 171.85 | 210.46 | +104.51% |

Serialization began to dominate at approximately 10 MiB, where median
latency was more than 50% above the 124-byte baseline. At 20 MiB the
median more than doubled. For a closed-loop client on the same hourly
machine, the corresponding capacity loss raises normalized cost per
prediction by approximately 51.64% at 10 MiB and 104.51% at 20 MiB.

### Instance size

The same managed endpoint, image, model version, one-row payload,
10 VUs, 60-second duration, and one replica were tested on two machine
sizes after warm-up.

| Instance | THB/hour | Throughput (req/s) | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | THB/1,000 at 100% measured utilisation |
|---|---:|---:|---:|---:|---:|---:|---:|
| `n1-standard-2` | 3.80 | 53.211 | 167.18 | 336.04 | 488.79 | 0.00% | 0.01984 |
| `n1-standard-4` | 7.60 | 78.565 | 122.29 | 187.86 | 246.19 | 0.00% | 0.02687 |

Moving one size up increased throughput by 47.65%, reduced p50 by
26.85%, p95 by 44.10%, and p99 by 49.63%. Hourly price increased by
100%, so cost per 1,000 predictions increased by 35.46% despite the
latency improvement. `n1-standard-4` is justified when lower tail
latency is worth the higher unit cost; `n1-standard-2` is the more
cost-efficient configuration for the stated p95 target.

The first request run after deploying `n1-standard-2` had p99
9998.58 ms and a maximum of 21730.67 ms, while the warmed run had p99
488.79 ms. This fresh-deployment warm-up effect is reported separately
and was excluded from the steady-state instance comparison.

## Canary detection and rollback

A deliberately degraded canary used the same immutable image and model
version with `PREDICT_DELAY_MS=700`. Vertex AI routed 90% of traffic
to the baseline and 10% to the canary.

| Variant | Requests | Share | p95 (ms) | p99 (ms) |
|---|---:|---:|---:|---:|
| Baseline | 2768 | 89.93% | 233.12 | 338.13 |
| Canary | 310 | 10.07% | 867.76 | 920.35 |

The combined p95 reached 786.89 ms and p99 reached 842.85 ms,
exceeding the 500 ms target. The canary received 310 real requests,
so degradation was detected from live routed traffic.

The rollback undeployed the canary and restored baseline traffic to
100%. The post-rollback 10-VU verification produced p95 278.45 ms,
p99 367.02 ms, throughput 65.93 req/s, and error rate 0.00%. This
confirms that latency recovered after the routing change.

Recorded timeline:

```text
canary_test_started=2026-09-22T17:58:07+07:00
traffic_split=baseline:90,canary:10
baseline_deployed_model_id=4679725996977422336
canary_deployed_model_id=522059115984322560
canary_test_finished=2026-09-22T17:59:08+07:00
rollback_triggered=2026-09-22T17:59:29+07:00
trigger_metric=predict_latency_ms_p95
observed_p95_ms=786.893732
target_p95_ms=500
action=undeploy_canary_and_restore_baseline_100_percent
rollback_completed=2026-09-22T17:59:32+07:00
post_rollback_test_started=2026-09-22T18:00:03+07:00
post_rollback_test_finished=2026-09-22T18:01:03+07:00
```


### Five-line detection analysis

1. The combined `predict_latency_ms` p95 revealed the degradation by crossing the committed 500 ms threshold at 786.89 ms.
2. Detection took 82 seconds from the first routed canary traffic at 17:58:07 to the rollback trigger at 17:59:29.
3. A shorter evaluation window, variant-aware latency metrics, or a larger canary sample would have detected it faster.
4. A 50/50 split would expose more users, move the combined distribution further toward the 867.76 ms canary p95, and trigger faster at greater customer impact.
5. Rollback completed three seconds after the trigger, and the post-rollback p95 recovered to 278.45 ms with zero errors.
## Health versus readiness

`/health` reports that the service process is alive. `/ready` reports
success only after the model has loaded and can serve predictions.

If readiness returned 200 while the model was still loading, Vertex AI
could route traffic too early and produce failed or invalid predictions
even though the process itself was alive.


## Cost per 1,000 predictions

The repository rate table records `n1-standard-2` at 3.80 THB/hour.
The main baseline achieved 55.735 req/s at 10 VUs. The stated
utilisation assumption for this headline estimate is 100% of the
measured capacity:

    cost per 1,000
      = hourly rate * 1,000
        / (requests per second * 3,600 * utilisation)
      = 3.80 * 1,000 / (55.735 * 3,600 * 1.00)
      = 0.018939 THB

At 25% utilisation, the same always-on endpoint costs 0.075756 THB per
1,000 predictions because provisioned idle time is shared across fewer
requests. The estimate excludes storage, registry, logging, network
transfer, and the temporary second replica used by the canary.

For the controlled instance-size runs at 100% measured utilisation,
`n1-standard-2` cost 0.01984 THB per 1,000 predictions and
`n1-standard-4` cost 0.02687 THB. The larger instance therefore raised
unit cost by 35.46% while reducing p95 by 44.10%.

Assuming one scheduled batch job per day uses `n1-standard-2` for
30 minutes, the planning batch cost is 1.90 THB per run. The repository
planning model gives a break-even rate of approximately 0.0010 req/s,
or about 89 predictions per day; below that volume, scheduled batch
inference is cheaper than keeping the 3.80 THB/hour endpoint warm.

## Cleanup

The required `make teardown` command was run with its Lab 3 default.
The first run removed endpoint `itcs355-6688121-lab3-sizing` and serving
model `itcs355-6688121-serve-v1`; the second run returned `[]`.

`python scripts/teardown_verify.py --lab 3` then reported
`PASS nothing found under these tags`. Direct label-filtered Vertex AI
endpoint and model listings returned no remaining Lab 3 resources.
The command outputs are committed in
`reports/lab3-make-teardown.txt`,
`reports/lab3-teardown-verify.txt`, and
`reports/lab3-teardown-cloud-confirmation.txt`.

## Required Make command evidence

The required operational commands were executed after their Make
targets had been committed.

- `make deploy` recreated the Vertex AI endpoint from registered model
  `itcs355-6688121@1` on `n1-standard-2`. The immutable image and
  deployment response are recorded in `reports/lab3-make-deploy.txt`.
- `make smoke` invoked three known payloads. All three returned one
  prediction containing `probability` and `model_version=1`. The
  committed result records `payload_count=3` and `all_passed=true` in
  `reports/lab3-make-smoke.txt`.
- `make cost-report` generated `reports/lab3-cost.md` from the measured
  throughput, hourly rates, and explicit 100% utilisation assumption.
- `make teardown` removed the recreated endpoint and serving model.
  Its second run returned `[]`, and
  `python scripts/teardown_verify.py --lab 3` returned `PASS`. The
  final evidence is in `reports/lab3-final-make-teardown.txt` and
  `reports/lab3-final-teardown-verify.txt`.
