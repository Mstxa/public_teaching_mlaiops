# Lab 5 — LLM Token Cost and Budget Defence

**Calculation date:** 2026-10-16
**Provider/model:** `gcp/small`
**Pricing basis:** `src/llmcost.py` uses 8.5 THB per 1,000,000 input
tokens and 34 THB per 1,000,000 output tokens. Token counts come from the
recorded provider usage fields rather than word-count estimates.

## 1. Measured cost per 1,000 requests

The passing 10-case baseline measured 416 average input tokens and 37 average
output tokens per request.

    input cost/request  = 416 × 8.5 / 1,000,000
                        = 0.003536 THB

    output cost/request = 37 × 34 / 1,000,000
                        = 0.001258 THB

    total/request       = 0.004794 THB
    cost/1,000 requests = 4.794 THB

The baseline gate passed 10/10 cases with this measured usage.

## 2. `max_output_tokens` cap

The live-generation cap was reduced from 200 to 64 tokens in
`scripts/llm_eval.py`.

    200-token cap = ((416 × 8.5) + (200 × 34)) / 1,000
                  = 10.336 THB per 1,000 requests

    64-token cap  = ((416 × 8.5) + (64 × 34)) / 1,000
                  = 5.712 THB per 1,000 requests

    saving        = 10.336 - 5.712
                  = 4.624 THB per 1,000 requests
                  = 44.74%

The largest observed passing response used 41 output tokens, below the new
64-token cap. After applying the cap, the baseline still passed 10/10 cases.
The evidence is stored in `reports/lab5-output-cap-gate.txt`.

## 3. Prompt-cache break-even

For a stable 300-token prefix, cache writes cost 1.25 times normal input and
cache reads cost 0.10 times normal input.

    extra cost on miss = 1.25 - 1.00 = 0.25
    saving on hit      = 1.00 - 0.10 = 0.90
    break-even rate    = 0.25 / (0.25 + 0.90)
                       = 21.74%

The recorded usage contains zero cached input tokens, giving a measured cache
hit rate of 0.00%. This is below the 21.74% break-even rate, so prompt caching
is not enabled until real traffic demonstrates a sufficiently stable prefix.

## Budget defence

At 4.794 THB per 1,000 requests, a forecast of 100,000 requests per month
costs approximately 479.40 THB. This leaves 320.60 THB of the 800 THB budget
as headroom. At the measured average, the budget supports approximately
166,875 requests per month.

The 64-token cap also limits worst-case verbose responses while the 10/10
baseline confirms that the cap preserves the recorded quality. An alert should
fire before 80% of budget, and nonessential workloads should be stopped rather
than silently exceeding 800 THB.

## Evidence

- `reports/llm_eval-baseline.json`
- `reports/lab5-token-calculation.txt`
- `reports/lab5-output-cap-gate.txt`
- `reports/lab5-llm-gate-run.txt`
