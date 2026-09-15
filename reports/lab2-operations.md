# Lab 2 managed job and registry evidence

The first managed training job shown in my terminal record reached `JOB_STATE_SUCCEEDED` with `error: null`. I did not observe a permission error on this submission, so I cannot name a missing permission.

I registered the selected model as `itcs355-6688121@1`. Its version stores the code commit, data version, MLflow run ID, training job ID, image digest, seed, validation metric, and test metric. The registry reload check loaded version 1 and scored five held-out rows. The staging command then set the staging alias on version 1. The staging screenshot also shows an earlier failed verification, followed by the successful retry.

After the study, I ran `make teardown`. It returned `[]`, meaning there were no active Lab 2 jobs to cancel. The registered model and its stored artifacts were kept for Lab 3.

## Terminal evidence

1. [Managed training job succeeded](evidence/lab2-first-managed-job.png)
2. [Model registration and five-row registry reload check](evidence/lab2-registry-reload.png)
3. [Successful staging retry and teardown output](evidence/lab2-staging-teardown.png)
