"""Lab 5 — compile pipeline/pipeline.yaml into your provider's pipeline service.

This module is Layer 3, so provider SDKs are allowed here and nowhere else. The DAG stays
in YAML; only the translation lives here. That separation is what you argue for or against
in Lab 5 Task 4.

Implement ONE compile function, for your provider.
"""

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


def compile_gcp(spec: dict[str, Any]) -> str:
    """Compile the neutral DAG into a Vertex-compatible KFP v2 JSON file."""
    from kfp import compiler, dsl

    validate_spec(spec)

    parameters = spec.get("parameters", {})
    required_parameters = (
        "training_image",
        "serving_image",
        "git_commit",
        "staging_instance",
    )
    unresolved = [
        name
        for name in required_parameters
        if not parameters.get(name) or "${" in str(parameters[name])
    ]
    if unresolved:
        raise RuntimeError(
            "Set pipeline environment values before compiling: "
            + ", ".join(unresolved)
        )

    digest_pattern = r".+@sha256:[0-9a-f]{64}"
    for name in ("training_image", "serving_image"):
        if not re.fullmatch(digest_pattern, str(parameters[name])):
            raise ValueError(f"{name} must be a digest-pinned container image")

    capability_names = (
        "CLOUD_PROVIDER",
        "PROJECT_ID",
        "REGION",
        "BLOB_URI",
        "CONTAINER_REGISTRY",
        "MLFLOW_TRACKING_URI",
        "MODEL_REGISTRY_NAME",
        "IDENTITY_REF",
    )
    missing = [name for name in capability_names if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Missing pipeline capability environment: " + ", ".join(missing)
        )

    runtime_env = {
        name: os.environ[name]
        for name in capability_names
    }
    steps = {step["name"]: step for step in spec["steps"]}

    def render(
        command: list[Any],
        replacements: dict[str, Any],
    ) -> list[Any]:
        return [replacements.get(item, item) for item in command]

    @dsl.container_component
    def ingest_component(
        raw_data: dsl.Output[dsl.Dataset],
    ):
        return dsl.ContainerSpec(
            image=steps["ingest"]["image"],
            command=render(
                steps["ingest"]["command"],
                {
                    "{{outputs.raw_data}}": raw_data.path,
                },
            ),
        )

    @dsl.container_component
    def validate_component(
        raw_data: dsl.Input[dsl.Dataset],
    ):
        return dsl.ContainerSpec(
            image=steps["validate"]["image"],
            command=render(
                steps["validate"]["command"],
                {
                    "{{inputs.raw_data}}": raw_data.path,
                },
            ),
        )

    @dsl.container_component
    def train_component(
        raw_data: dsl.Input[dsl.Dataset],
        model: dsl.Output[dsl.Model],
        metrics: dsl.Output[dsl.Metrics],
    ):
        return dsl.ContainerSpec(
            image=steps["train"]["image"],
            command=render(
                steps["train"]["command"],
                {
                    "{{inputs.raw_data}}": raw_data.path,
                    "{{outputs.model}}": model.path,
                    "{{outputs.metrics}}": metrics.path,
                },
            ),
        )

    @dsl.container_component
    def evaluate_component(
        metrics: dsl.Input[dsl.Metrics],
        gate_decision: dsl.OutputPath(str),
    ):
        return dsl.ContainerSpec(
            image=steps["evaluate"]["image"],
            command=render(
                steps["evaluate"]["command"],
                {
                    "{{inputs.metrics}}": metrics.path,
                    "{{outputs.gate_decision}}": gate_decision,
                },
            ),
        )

    @dsl.container_component
    def register_component(
        model: dsl.Input[dsl.Model],
        metrics: dsl.Input[dsl.Metrics],
        version: dsl.Output[dsl.Artifact],
    ):
        return dsl.ContainerSpec(
            image=steps["register"]["image"],
            command=render(
                steps["register"]["command"],
                {
                    "{{inputs.model}}": model.path,
                    "{{inputs.metrics}}": metrics.path,
                    "{{parameters.training_image}}": parameters[
                        "training_image"
                    ],
                    "{{runtime.pipeline_job_name}}": (
                        dsl.PIPELINE_JOB_NAME_PLACEHOLDER
                    ),
                    "{{parameters.git_commit}}": parameters["git_commit"],
                    "{{outputs.version}}": version.path,
                },
            ),
        )

    @dsl.container_component
    def deploy_component(
        version: dsl.Input[dsl.Artifact],
        deployment: dsl.Output[dsl.Artifact],
    ):
        return dsl.ContainerSpec(
            image=steps["deploy_staging"]["image"],
            command=render(
                steps["deploy_staging"]["command"],
                {
                    "{{inputs.version}}": version.path,
                    "{{parameters.serving_image}}": parameters[
                        "serving_image"
                    ],
                    "{{parameters.staging_instance}}": parameters[
                        "staging_instance"
                    ],
                    "{{outputs.deployment}}": deployment.path,
                },
            ),
        )

    def configure(task):
        task.set_caching_options(False)
        for name, value in runtime_env.items():
            task.set_env_variable(name, value)
        return task

    @dsl.pipeline(name=spec["name"])
    def pipeline():
        ingest_task = configure(
            ingest_component()
        ).set_display_name("ingest")

        validate_task = configure(
            validate_component(
                raw_data=ingest_task.outputs["raw_data"],
            )
        ).set_display_name("validate")

        train_task = configure(
            train_component(
                raw_data=ingest_task.outputs["raw_data"],
            )
        ).after(validate_task).set_display_name("train")

        evaluate_task = configure(
            evaluate_component(
                metrics=train_task.outputs["metrics"],
            )
        ).set_display_name("evaluate")

        with dsl.If(
            evaluate_task.outputs["gate_decision"] == "pass",
            name="evaluation-gate-pass",
        ):
            register_task = configure(
                register_component(
                    model=train_task.outputs["model"],
                    metrics=train_task.outputs["metrics"],
                )
            ).set_display_name("register")

            configure(
                deploy_component(
                    version=register_task.outputs["version"],
                )
            ).set_display_name("deploy-staging")

    output = Path("tmp/vertex-pipeline.json")
    output.parent.mkdir(parents=True, exist_ok=True)

    compiler.Compiler().compile(
        pipeline_func=pipeline,
        package_path=str(output),
    )

    print(f"Compiled Vertex pipeline: {output}")
    return str(output)

COMPILERS = {"aws": compile_aws, "azure": compile_azure, "gcp": compile_gcp}


def compile_for(provider: str, spec: dict[str, Any] | None = None):
    spec = spec or load_spec()
    try:
        return COMPILERS[provider.lower()](spec)
    except KeyError:
        raise ValueError(f"No pipeline compiler for {provider!r}") from None
