import http from 'k6/http';
import { check } from 'k6';
import { Counter, Trend, Rate } from 'k6/metrics';

const latency = new Trend('predict_latency_ms');
const baselineLatency = new Trend('baseline_latency_ms');
const canaryLatency = new Trend('canary_latency_ms');
const baselineRequests = new Counter('baseline_requests');
const canaryRequests = new Counter('canary_requests');
const failures = new Rate('predict_failures');

const managed = (__ENV.MODE || 'local') === 'managed';
const target = __ENV.TARGET || 'http://127.0.0.1:8080/predict';
const canaryId = __ENV.CANARY_DEPLOYED_MODEL_ID || '';

export const options = {
  vus: Number(__ENV.VUS || 10),
  duration: __ENV.DURATION || '60s',
  summaryTrendStats: [
    'avg',
    'min',
    'med',
    'p(90)',
    'p(95)',
    'p(99)',
    'max',
  ],
  thresholds: {
    // Target set before measurement: p95 < 500 ms at 10 VUs; error rate < 1%.
    'predict_latency_ms': ['p(95)<500'],
    'predict_failures': ['rate<0.01'],
  },
};

const instance = {
  temp_c: 78.4,
  vibration_mm_s: 3.1,
  pressure_kpa: 315.2,
  hours_since_service: 4200,
  load_pct: 68.0,
  ambient_humidity: 55.0,
};

const payload = JSON.stringify(
  managed ? { instances: [instance] } : instance,
);

export default function () {
  const headers = {
    'Content-Type': 'application/json',
  };

  if (__ENV.AUTH_TOKEN) {
    headers.Authorization = `Bearer ${__ENV.AUTH_TOKEN}`;
  }

  const res = http.post(target, payload, { headers });
  const body = res.status === 200 ? res.json() : {};

  latency.add(res.timings.duration);
  failures.add(res.status !== 200);

  if (managed && canaryId && body.deployedModelId === canaryId) {
    canaryLatency.add(res.timings.duration);
    canaryRequests.add(1);
  } else {
    baselineLatency.add(res.timings.duration);
    baselineRequests.add(1);
  }

  check(res, {
    'status is 200': (r) => r.status === 200,
    'probability present': () =>
      managed
        ? Array.isArray(body.predictions) &&
          body.predictions.length === 1 &&
          body.predictions[0].probability !== undefined
        : body.probability !== undefined,
    'version reported': (r) =>
      managed
        ? Array.isArray(body.predictions) &&
          body.predictions[0].model_version !== undefined
        : r.headers['X-Model-Version'] !== undefined,
  });
}
