# ITCS355 Lab 1 — Reproducible Training

> **Course materials live in [`course/`](course/README.md)** — syllabus, slides, the faculty
> specification, all five lab handouts, and the project brief. Every document is Markdown and
> renders on GitHub, diagrams included. New to the repo? Start with the
> [portability reference](course/reference/cloud-portability-reference.md).
> Keep this block when you edit the rest of this file; it is not part of the Lab 1 deliverable.

Predicting machine failure within 7 days from sensor readings. The model is not the point;
whether a stranger can reproduce it is.

> **This README is graded.** A grader with Docker and nothing else from your setup runs one
> command and compares the result against the claim below.

---

## Reproduce

```bash
make reproduce
```

expected test_roc_auc: 0.8482 ± 0.0010

Runtime: about 40 seconds on 4 cores. No cloud account or credentials needed for this command —
that is deliberate, and it is why a grader can run it.

---

## The problem

240 machines, 25 readings each, 6 sensor features, binary target `failed_within_7d` with a
positive rate near 12%.

Machines have persistent characteristics — a hot-running machine reads hot in every row. So the
train/validation/test split is **grouped by `machine_id`**: every reading from one machine lands
in exactly one partition. Splitting row-wise instead lets the model memorise the machine and
reports a validation score that will never survive production. `tests/test_data.py` asserts this
property holds, and Lab 4 turns it into a CI gate.

Bringing your own dataset is allowed. Replace `scripts/make_dataset.py`, update the schema in
`src/data.py`, and keep every test passing.

---

## Layout

```
src/          Layer 1 — provider-neutral. No SDKs, no bucket names, no absolute paths.
cloudlayer/   Layer 3 — the only place a provider SDK may be imported.
scripts/      Dataset generation, cloud check, portability audit, metric verification.
tests/        Data contract tests and split property tests.
```

`src/config.py` is the single point of environment knowledge. Everything else reads from it.
`make portability-audit` enforces the rule; it fails the build if a provider string appears in
`src/` or `tests/`.

---

## Setup

```bash
cp cloud.env.example cloud.env      # fill in, never commit
make setup
make cloud-check                    # eight slots, all PASS
make data                           # generate the dataset
make test                           # 10 tests, all passing
```

Post your `make cloud-check` output in the course channel before Session 1.

---

## What you must finish

Four `TODO` markers are left in the repo deliberately. Each is a graded decision, not busywork.

| Where | What |
|---|---|
| `requirements.txt` | Regenerate with `pip-compile --generate-hashes` |
| `Dockerfile` | Pin the base image by digest; add `--require-hashes` |
| `cloudlayer/gcp.py` | Implement `upload`, `download`, `push_image` |
| This README | The reproducibility trade-off question below |

Then:

```bash
make image-push        # image reaches your registry, digest-pinned
dvc init && dvc remote add -d storage ${BLOB_URI}/dvc
dvc add data/raw && dvc push
```

Run five or more tracked runs varying something meaningful — not five identical runs with
different seeds.

---

## Reproducibility trade-off

Under time pressure, I would drop strict seed control first. The hashed lock file and digest-pinned base image preserve buildability and prevent the software environment from changing silently. Without fixed seeds, the data split and Random Forest may change between runs, so metrics are no longer directly comparable and the exact reported ROC AUC may not reproduce. I would document the variance and restore seed control before using the result for evaluation or promotion.

---

## Notes for the grader

The final configuration uses 150 estimators, maximum depth 6, and minimum samples per leaf 5. It was selected by the highest validation ROC AUC across five tracked runs; the test set was not used for model selection. Raw data is versioned with DVC in GCS, and the linux/amd64 image is stored in Google Artifact Registry. The reproduction command requires no cloud credentials.

### Lab 2 registry promotion

The selected trial and <=200-word comparison are in `reports/lab2-comparison.md`. Run `make register`, then `make reload-check VERSION=<returned version>` to fetch the model by its Vertex registry version and score five held-out rows. Only after that check succeeds, run `make promote-staging VERSION=<same version>`. The registry version description contains the eight exact lineage fields; the model artifact and a JSON sidecar are stored in GCS. The registered container is the digest-pinned training image, which preserves the software environment for Lab 2 verification; a serving container is needed before online deployment in Lab 3.

The laptop sleep and study recovery are documented in `reports/lab2-resume.md`, with terminal screenshots. This is evidence of recovery from a local connection loss, not a confirmed Spot preemption.

The managed job, model registration, registry reload check, staging retry, and teardown outputs are documented in `reports/lab2-operations.md`.

In a real organisation, an ML platform release owner should control the staging alias. They should require the 12-trial comparison, validation and held-out test metrics, seed variance, actual cloud cost, complete code/data/job/image lineage, a successful registry reload check, and a review of data drift and failure risks before promotion. The computed trial costs are estimates until reconciled with Cloud Billing.

Run `make cost-report` to generate `reports/lab2-cost.md` from the trial checkpoint and the saved Billing observation. The observed project usage cost through September 14 was 4.48 THB before Free Trial credits, and the net billed amount was 0.00 THB. This project total includes services outside the 12 trial estimate; see the report and Billing screenshots for the scope. If Billing adds later charges, update `reports/lab2-billing-observation.json`, rerun `make cost-report`, and commit the updated report.

---

## Checklist before you submit

- [ ] `make reproduce` works from a fresh clone, on a machine that is not yours
- [ ] `make verify` passes against your claim line
- [ ] `make test` — all tests pass
- [ ] `make portability-audit` — clean
- [ ] Image builds for `linux/amd64` and is pushed, digest-pinned
- [ ] `dvc push` completed; a grader can `dvc pull`
- [ ] Five or more tracked runs with params, metrics, data fingerprint, and commit SHA
- [ ] Every **REPLACE** block above is gone (the course-materials block at the top stays)
- [ ] `make scan-secrets` is clean

That last check is not optional. A credential in Git history is an automatic deduction in this
course, and rotating it is your responsibility, not the grader's. The scan reads *history*, not
your working tree, because deleting the file is the thing that makes people believe they are
safe. If it finds something, rotate the credential first and rewrite history second — in that
order, because the first one is the only step that actually helps.
