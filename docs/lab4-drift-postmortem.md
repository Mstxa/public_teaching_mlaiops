# Post-mortem — injected `temp_c` distribution shift

**What fired:** The Cloud Monitoring policy `Lab 4 - temp_c PSI above 0.06` fired by email at approximately 15:11 ICT on 5 October 2026 after `temp_c` PSI reached `0.38333`, above the justified `0.06` threshold. The shift was injected at 15:08:28 ICT, so end-to-end notification latency was approximately 2 minutes 32 seconds.

**True cause:** This was controlled data drift produced by `scripts/inject_drift.py`, which shifted the `temp_c` mean from `79.58°C` to `85.58°C`. It was not concept drift, because no change in the feature-to-label relationship was measured, and it was not a schema break because the columns and types remained valid.

**Retrain, roll back, or no action — and why:** Do not retrain. Stop the injected input source and restore the known-good input distribution; retraining on this deliberately shifted batch would teach the model from unverified data. Retraining would be reconsidered only if operational evidence showed that the shift was legitimate, persistent, and accompanied by reliable recent labels.

**What this would have cost if unnoticed for a week:** Assuming 10,000 predictions per day, as many as 70,000 maintenance predictions could have been made on off-distribution temperatures during one week. The direct cloud cost might remain similar, but unreliable maintenance decisions could create unnecessary inspections or missed failures; this estimate should be replaced with the production request rate and business cost when available.

**How to prevent or detect it faster:** Run the detector every minute with Cloud Scheduler, retain the `0.06` alert threshold, and add an upstream rolling-mean/range check for `temp_c` so a producer-side shift is identified before it reaches model inference.
