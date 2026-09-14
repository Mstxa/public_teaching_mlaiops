"""Run the Lab 2 grid as resumable, one-trial-per-job Vertex Spot training."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import mlflow

from cloudlayer.factory import get_adapter
from src import config
from src.train import dvc_data_hash
from src.tune import SEARCH_SPACE, grid

CHECKPOINT_KEY = "lab2/study/checkpoint.json"
LOCAL_CHECKPOINT = Path("reports/lab2_remote_checkpoint.json")


def _git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=config.REPO_ROOT, text=True
    ).strip()


def _read_checkpoint(adapter) -> dict:
    with TemporaryDirectory() as directory:
        remote = Path(directory) / "checkpoint.json"
        try:
            adapter.download(f"{adapter.cfg.blob_uri.rstrip('/')}/{CHECKPOINT_KEY}", str(remote))
            state = json.loads(remote.read_text())
        except FileNotFoundError:
            state = {}
    if LOCAL_CHECKPOINT.exists():
        local = json.loads(LOCAL_CHECKPOINT.read_text())
        if len(local.get("completed", [])) > len(state.get("completed", [])):
            state = local
        elif len(local.get("completed", [])) == len(state.get("completed", [])) and local.get("active_job_id"):
            state = local
    return state


def _save_checkpoint(adapter, state: dict) -> None:
    LOCAL_CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_CHECKPOINT.write_text(json.dumps(state, indent=2))
    adapter.upload(str(LOCAL_CHECKPOINT), CHECKPOINT_KEY)


def _seconds(start: str | None, end: str | None) -> float:
    if not start or not end:
        return 0.0
    return max(0.0, (
        datetime.fromisoformat(end.replace("Z", "+00:00"))
        - datetime.fromisoformat(start.replace("Z", "+00:00"))
    ).total_seconds())


def _record_run(cfg, adapter, job: dict, trial: int, params: dict, seed: int,
                image_uri: str, data_version: str, prefix: str, rate: float) -> dict:
    duration_s = _seconds(job.get("startTime"), job.get("endTime"))
    wall_s = _seconds(job.get("createTime"), job.get("endTime"))
    cost_thb = duration_s / 3600.0 * rate
    with TemporaryDirectory(prefix="itcs355-lab2-result-") as directory:
        model_path = Path(directory) / "model.joblib"
        metrics_path = Path(directory) / "metrics.json"
        model_uri = f"{cfg.blob_uri.rstrip('/')}/{prefix}/model.joblib"
        metrics_uri = f"{cfg.blob_uri.rstrip('/')}/{prefix}/metrics.json"
        adapter.download(model_uri, str(model_path))
        adapter.download(metrics_uri, str(metrics_path))
        metrics = json.loads(metrics_path.read_text())

        mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
        mlflow.set_experiment("itcs355-lab2")
        with mlflow.start_run(run_name=f"vertex-spot-{trial:02d}") as run:
            mlflow.log_params({**params, "seed": seed, "instance": "e2-standard-4"})
            mlflow.log_metrics({
                **{k: float(v) for k, v in metrics.items() if k.endswith(("roc_auc", "pr_auc"))},
                "duration_s": duration_s,
                "wall_duration_s": wall_s,
                "cost_thb": cost_thb,
            })
            mlflow.set_tags({
                "git_commit": _git("rev-parse", "HEAD"),
                "data_version": data_version,
                "training_job_id": job["name"],
                "image_digest": image_uri.rsplit("@", 1)[1],
                "model_uri": model_uri,
                "metrics_uri": metrics_uri,
                "pricing_note": "conservative planning estimate; verify actual billing",
                "lab": "2",
            })
            mlflow.log_artifact(str(model_path), artifact_path="model")
            return {
                "trial": trial,
                "params": params,
                "seed": seed,
                "job_id": job["name"],
                "mlflow_run_id": run.info.run_id,
                "model_uri": model_uri,
                "metrics_uri": metrics_uri,
                "metrics": metrics,
                "duration_s": duration_s,
                "wall_duration_s": wall_s,
                "cost_thb_estimate": cost_thb,
            }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-uri", required=True)
    parser.add_argument("--trials", type=int, default=12)
    parser.add_argument("--budget-thb", type=float, default=150)
    parser.add_argument("--rate-thb-hour", type=float, default=12,
                        help="Conservative estimated Spot compute rate; check current billing")
    parser.add_argument("--prior-spend-thb", type=float, default=10,
                        help="Reserve for the earlier smoke job")
    parser.add_argument("--other-reserve-thb", type=float, default=20,
                        help="Reserve for storage, logs and price uncertainty")
    parser.add_argument("--max-job-minutes", type=int, default=15)
    parser.add_argument("--dry-run", action="store_true")
    options = parser.parse_args()
    if not 1 <= options.trials <= len(grid(SEARCH_SPACE)):
        parser.error(f"--trials must be 1..{len(grid(SEARCH_SPACE))}")
    if options.budget_thb <= 0 or options.rate_thb_hour <= 0 or options.max_job_minutes <= 0:
        parser.error("Budget, rate and max job duration must be positive")

    candidates = grid(SEARCH_SPACE)[:options.trials]
    reservation = options.rate_thb_hour * options.max_job_minutes / 60
    print(f"{len(candidates)} Spot trials; conservative reservation {reservation:.2f} THB per job")
    for trial, params in enumerate(candidates):
        print(f"  trial {trial:02d}: {params}")
    if options.dry_run:
        print(f"Maximum planned study spend: {reservation * len(candidates):.2f} THB, "
              f"plus {options.prior_spend_thb + options.other_reserve_thb:.2f} THB reserved")
        return

    if _git("status", "--porcelain"):
        raise SystemExit("Commit source changes and rebuild/push the image before running the study")
    cfg = config.load()
    adapter = get_adapter(cfg)
    data_version = dvc_data_hash()
    if data_version == "unknown":
        raise SystemExit("Could not read the DVC data version")
    study_id = {"git_commit": _git("rev-parse", "HEAD"),
                "data_version": data_version, "image_uri": options.image_uri}
    state = _read_checkpoint(adapter)
    if state and any(state.get(key) != value for key, value in study_id.items()):
        raise SystemExit("Existing checkpoint belongs to a different code, data or image version")
    if not state:
        state = {**study_id, "completed": [], "failed_attempts": [], "active_job_id": None}
        _save_checkpoint(adapter, state)

    for trial, params in enumerate(candidates):
        if any(item["trial"] == trial for item in state["completed"]):
            print(f"trial {trial:02d}: resumed from checkpoint")
            continue
        spent = sum(item["cost_thb_estimate"] for item in state["completed"])
        spent += sum(item["cost_thb_estimate"] for item in state["failed_attempts"])
        if spent + options.prior_spend_thb + options.other_reserve_thb + reservation > options.budget_thb:
            raise SystemExit(f"Budget guard stopped before trial {trial:02d}; estimated spend {spent:.2f} THB")

        prefix = f"lab2/study/trial-{trial:02d}"
        if state.get("active_job_id"):
            job_id = state["active_job_id"]
            if state.get("active_trial") != trial:
                raise SystemExit("Checkpoint has an active job for a different trial")
            print(f"trial {trial:02d}: reattaching to {job_id}")
        else:
            job_id = adapter.submit_training(options.image_uri, {
                "data_uri": f"{cfg.blob_uri.rstrip('/')}/lab2/data/{data_version}/sensors.csv",
                "output_prefix": prefix,
                "git_commit": study_id["git_commit"],
                "data_version": data_version,
                "machine_type": "e2-standard-4",
                "n_estimators": params["n_estimators"],
                "max_depth": params["max_depth"],
                "min_samples_leaf": params["min_samples_leaf"],
                "spot": True,
                "timeout_s": options.max_job_minutes * 60,
                "display_name": f"itcs355-lab2-spot-{trial:02d}",
            })
            print(f"trial {trial:02d}: submitted {job_id}")
            state["active_job_id"] = job_id
            state["active_trial"] = trial
            _save_checkpoint(adapter, state)

        job = adapter.wait_training(job_id)
        state["active_job_id"] = None
        state["active_trial"] = None
        if job.get("state") != "JOB_STATE_SUCCEEDED":
            duration_s = _seconds(job.get("startTime"), job.get("endTime"))
            state["failed_attempts"].append({
                "trial": trial, "job_id": job_id, "state": job.get("state"),
                "error": job.get("error"),
                "cost_thb_estimate": duration_s / 3600 * options.rate_thb_hour,
            })
            _save_checkpoint(adapter, state)
            raise SystemExit(f"Trial {trial:02d} ended {job.get('state')}; rerun to resume")

        result = _record_run(cfg, adapter, job, trial, params, 20260101,
                             options.image_uri, data_version, prefix, options.rate_thb_hour)
        state["completed"].append(result)
        _save_checkpoint(adapter, state)
        print(f"trial {trial:02d}: val ROC AUC {result['metrics']['val_roc_auc']:.4f}; "
              f"estimated cost {result['cost_thb_estimate']:.3f} THB")

    print(f"Study complete: {len(state['completed'])}/{len(candidates)} trials")


if __name__ == "__main__":
    main()
