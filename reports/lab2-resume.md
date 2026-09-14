# Lab 2 recovery evidence

During the 12-trial study, my laptop went to sleep. The local terminal lost its connection while it was waiting for Vertex job trial 06. The command ended with `requests.exceptions.ConnectionError`.

The saved checkpoint still had six completed trials. It also kept trial 06 as the active trial and saved its Vertex job ID. After I ran the study again, the log said `trial 06: reattaching` to that same job. The study then finished all 12 trials. The final checkpoint has 12 completed trials and no failed trial attempts.

This shows recovery from a local connection loss. I did not observe a Vertex Spot preemption, so these screenshots do not prove recovery from Spot preemption.

## Terminal evidence

1. [Connection error after the laptop slept](evidence/lab2-connection-error.png)
2. [Checkpoint with six completed trials, followed by reattachment to trial 06](evidence/lab2-checkpoint-and-reattach.png)
3. [Study finished with 12 of 12 trials](evidence/lab2-study-complete.png)

The per-trial jobs and estimated costs are listed in [the cost report](lab2-cost.md).
