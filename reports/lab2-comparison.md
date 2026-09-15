# Lab 2 — Run comparison

Experiment `itcs355-lab2` · 12 trials · estimated compute cost 2.4233 THB

Cost uses a conservative planning rate, not the final Cloud Billing amount.

`thb_per_point` is cost per percentage point of val_roc_auc above the worst trial. Cheap improvements rank low; expensive improvements rank high, however good the headline number is. The worst trial has no improvement, so its value is undefined.

| run_id   |   val_roc_auc |   est_cost_thb |   n_estimators |   max_depth |   min_samples_leaf |   thb_per_point |
|:---------|--------------:|---------------:|---------------:|------------:|-------------------:|----------------:|
| 5b0573cd |        0.8426 |         0.2    |            100 |           4 |                  5 |          0.1242 |
| f5816abb |        0.8424 |         0.2033 |            100 |           4 |                  1 |          0.1279 |
| 2a29c0f9 |        0.8411 |         0.2    |            300 |           4 |                  5 |          0.137  |
| d4c5e1c8 |        0.8404 |         0.2033 |            300 |           4 |                  1 |          0.1463 |
| 2de1a52a |        0.8397 |         0.2    |            100 |           8 |                  5 |          0.1515 |
| e2ab0fa0 |        0.8377 |         0.2    |            300 |           8 |                  5 |          0.1786 |
| 551a39b2 |        0.8354 |         0.1    |            300 |          12 |                  5 |          0.1124 |
| 3184022c |        0.8338 |         0.3033 |            300 |           8 |                  1 |          0.4155 |
| 01956c2d |        0.8322 |         0.2033 |            100 |          12 |                  5 |          0.3567 |
| 4b79f623 |        0.8312 |         0.2033 |            100 |           8 |                  1 |          0.4326 |
| 2e52496e |        0.8268 |         0.2033 |            100 |          12 |                  1 |          6.7767 |
| 3e8c46b6 |        0.8265 |         0.2033 |            300 |          12 |                  1 |        nan      |

## Selection and justification

I selected trial 01 (run ID `5b0573cd9f424028a0bfbae992673809`; 100 trees, maximum depth 4, minimum leaf size 5). Its validation ROC AUC was 0.8426, and its held-out test ROC AUC was 0.8533. It had the highest validation score, but its lead over trial 00 was only 0.00016. This gap is much smaller than the change across seeds, so I do not treat it as proof that trial 01 is better. I chose it because it has fewer, shallow trees and a larger leaf size, which may reduce noise fitting at almost the same cost.

For this setup, validation AUC was 0.8426 with seed 20260101 on Vertex Spot, and 0.8479 and 0.8492 with seeds 20260102 and 20260103 in WSL. The mean was 0.8466 and the sample standard deviation was 0.0035. Training is estimated at 0.20 THB per run, or about 0.20 THB for one retraining each month, before storage and logs. Project usage cost before credits was 4.48 THB, including other services. This choice could be wrong if sensor data or failure rates change. I would track PR AUC and changes in the input data.
