# Lab 5 — LLM Evaluation Gate

## Baseline

- Golden-set cases: 8
- Passed: 8
- Pass rate: 100%
- P95 latency: 878 ms
- Estimated cost per 1,000 requests: 4.794 THB
- Provider/model: `gcp/small`

## Deliberately regressed responses

- Passed: 4/8
- Pass rate: 50%
- P95 latency: 902 ms
- Estimated cost per 1,000 requests: 4.692 THB
- Gate result: `FAILED`
- `make llm-gate` exit status: `2`

## Detected regressions

- `triage-003`: returned `schedule_routine` instead of `review_by_engineer`.
- `triage-004`: exposed identifier `PN-4471` and omitted the required word `not`.
- `triage-005`: incorrectly included `vibration`.
- `triage-007`: returned `schedule_urgent` instead of `no_action`.

The gate correctly rejected the degraded response set. The regressed set was
slightly cheaper per 1,000 requests, but its pass rate fell from 100% to 50%.
This demonstrates why cost or latency alone must not control promotion: quality
and safety checks must pass independently.
