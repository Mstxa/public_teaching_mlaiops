"""Lab 5 — compile pipeline/pipeline.yaml into your provider's pipeline service.

This module is Layer 3, so provider SDKs are allowed here and nowhere else. The DAG stays
in YAML; only the translation lives here. That separation is what you argue for or against
in Lab 5 Task 4.

Implement ONE compile function, for your provider.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

SPEC = Path(__file__).resolve().parents[1] / "pipeline" / "pipeline.yaml"


def load_spec(path: Path = SPEC) -> dict[str, Any]:
    """Read the neutral DAG and expand ${VAR} references from the environment."""
    raw = path.read_text()
    for key, value in os.environ.items():
        raw = raw.replace(f"${{{key}}}", value)
    spec = yaml.safe_load(raw)
    validate_spec(spec)
    return spec

def validate_spec(spec: dict[str, Any]) -> None:
    """Reject a malformed or disconnected neutral pipeline DAG."""
    if not isinstance(spec, dict):
        raise ValueError("Pipeline spec must be a mapping")

    steps = spec.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Pipeline spec must contain a non-empty steps list")

    expected = [
        "ingest",
        "validate",
        "train",
        "evaluate",
        "register",
        "deploy_staging",
    ]
    names = [step.get("name") for step in steps]
    if names != expected:
        raise ValueError(
            f"Pipeline steps must be ordered {expected}; received {names}"
        )
    if len(names) != len(set(names)):
        raise ValueError("Pipeline step names must be unique")

    by_name = {step["name"]: step for step in steps}
    seen: set[str] = set()
    allowed_output_types = {"dataset", "model", "metrics", "artifact", "parameter"}

    for step in steps:
        name = step["name"]

        if not step.get("image"):
            raise ValueError(f"Step {name!r} has no image")
        if not isinstance(step.get("command"), list) or not step["command"]:
            raise ValueError(f"Step {name!r} has no command")

        for dependency in step.get("depends_on", []):
            if dependency not in seen:
                raise ValueError(
                    f"Step {name!r} depends on unavailable step {dependency!r}"
                )

        for input_name, reference in step.get("inputs", {}).items():
            producer, separator, output_name = str(reference).partition(".")
            if not separator or producer not in seen:
                raise ValueError(
                    f"Input {name}.{input_name} has invalid source {reference!r}"
                )
            producer_outputs = by_name[producer].get("outputs", {})
            if output_name not in producer_outputs:
                raise ValueError(
                    f"Input {name}.{input_name} references missing output "
                    f"{reference!r}"
                )

        for output_name, output_type in step.get("outputs", {}).items():
            if output_type not in allowed_output_types:
                raise ValueError(
                    f"Output {name}.{output_name} has unsupported type "
                    f"{output_type!r}"
                )

        condition = step.get("condition")
        if condition:
            match = re.fullmatch(
                r"([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*) == '([^']+)'",
                condition,
            )
            if not match:
                raise ValueError(f"Invalid condition on step {name!r}: {condition!r}")
            producer, output_name, _ = match.groups()
            if producer not in seen:
                raise ValueError(
                    f"Condition on {name!r} references unavailable step {producer!r}"
                )
            if by_name[producer].get("outputs", {}).get(output_name) != "parameter":
                raise ValueError(
                    f"Condition source {producer}.{output_name} must be a parameter"
                )

        seen.add(name)

def compile_aws(spec: dict[str, Any]):
    """SageMaker Pipelines.

    Each step becomes a ProcessingStep or TrainingStep; `condition` becomes a
    ConditionStep. Note that SageMaker's condition steps branch rather than abort, so
    `on_failure: abort` needs a FailStep on the else branch — an asymmetry worth
    mentioning in your Lab 5 write-up.
    """
    raise NotImplementedError("TODO Lab 5: build a sagemaker.workflow.pipeline.Pipeline")


def compile_azure(spec: dict[str, Any]):
    """Azure ML Pipelines.

    Each step becomes a command component; the DAG is expressed as a @pipeline function.
    Conditions use azure.ai.ml.dsl.condition, which is closer to this YAML than the other
    two providers' equivalents.
    """
    raise NotImplementedError("TODO Lab 5: build an azure.ai.ml pipeline job")


def compile_gcp(spec: dict[str, Any]):
    """Vertex AI Pipelines.

    Kubeflow Pipelines underneath: steps become container components, conditions become
    dsl.If blocks. The compiled artifact is a JSON file you submit, so your build step
    produces a file rather than an object — different from the other two.
    """
    raise NotImplementedError("TODO Lab 5: compile a KFP pipeline and submit to Vertex")


COMPILERS = {"aws": compile_aws, "azure": compile_azure, "gcp": compile_gcp}


def compile_for(provider: str, spec: dict[str, Any] | None = None):
    spec = spec or load_spec()
    try:
        return COMPILERS[provider.lower()](spec)
    except KeyError:
        raise ValueError(f"No pipeline compiler for {provider!r}") from None
