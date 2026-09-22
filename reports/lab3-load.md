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

## Payload and instance-size experiment

The controlled request contained one prediction instance with six
numeric features. All baseline runs used the same payload, image,
model version, replica count, and `n1-standard-2` machine, making
concurrency the independent variable.

Batch size and machine size were held constant to avoid confounding
the concurrency comparison. A follow-up capacity study should sweep
batch size and compare a larger machine using the same traffic trace.

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

## Health versus readiness

`/health` reports that the service process is alive. `/ready` reports
success only after the model has loaded and can serve predictions.

If readiness returned 200 while the model was still loading, Vertex AI
could route traffic too early and produce failed or invalid predictions
even though the process itself was alive.

## Cost per 1,000 predictions

The repository rate table records `n1-standard-2` at 3.80 THB/hour.
This is one half of the repository's `n1-standard-4` rate because the
selected N1 machine has half its vCPU and memory allocation.

At the measured 10-VU throughput of 55.735 req/s:

    cost per 1,000
      = hourly rate * 1,000 / (requests per second * 3,600)
      = 3.80 * 1,000 / (55.735 * 3,600)
      = 0.018939 THB

This steady-state estimate covers one serving replica at measured
throughput. It excludes storage, registry, logging, network transfer,
idle-utilisation differences, and the temporary second replica used
during the canary experiment.

## Cleanup

After measurement, `teardown(tags(3))` undeployed the serving model
and deleted the endpoint, baseline Vertex Model, and canary Vertex
Model. Label-filtered endpoint and model listings returned no remaining
Lab 3 resources.
