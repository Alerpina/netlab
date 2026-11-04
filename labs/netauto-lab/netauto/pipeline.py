"""Orquestra o fluxo de mudança como um único trace.

deploy: render -> pre-checks -> backup -> apply -> post-checks
        (se algo falhar depois do backup: rollback) -> drift

Cada etapa é um subprocesso com o próprio span, filho do span "netauto.deploy".
O Ansible entra no mesmo trace pelo callback community.general.opentelemetry.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from opentelemetry.trace import Status, StatusCode

from . import telemetry
from .logging_setup import get_logger, run_context
from .settings import LAB_ROOT

log = get_logger("pipeline")
PY = sys.executable
ANSIBLE_DIR = LAB_ROOT / "ansible"
ANSIBLE_PLAYBOOK = str(Path(sys.executable).with_name("ansible-playbook"))
ROBOT = str(Path(sys.executable).with_name("robot"))

Runner = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True)
class Step:
    name: str
    cmd: Sequence[str]
    cwd: Path = LAB_ROOT
    ansible: bool = False


@dataclass
class Result:
    ok: bool = True
    executed: list[str] = field(default_factory=list)
    failed_step: str | None = None
    rolled_back: bool = False


def _robot(suite: str) -> Step:
    return Step(
        f"{suite}-checks",
        [ROBOT, "--pythonpath", ".", "--outputdir", f"build/robot/{suite}", f"robot/{suite}_checks.robot"],
    )


def _playbook(name: str, *extra: str) -> Step:
    return Step(name, [ANSIBLE_PLAYBOOK, f"playbooks/{name}.yml", *extra], cwd=ANSIBLE_DIR, ansible=True)


def deploy_steps(check: bool = False) -> list[Step]:
    steps = [
        Step("render", [PY, "-m", "netauto.render", "--source", "netbox"]),
        _robot("pre"),
        _playbook("backup"),
        _playbook("apply", "--diff", *(["--check"] if check else [])),
    ]
    if not check:
        steps.append(_robot("post"))
    return steps


ROLLBACK = _playbook("rollback")
DRIFT = Step("drift", [PY, "-m", "netauto.drift"])


def _env_for(step: Step) -> dict[str, str]:
    env = telemetry.child_env()
    env.setdefault("RUN_ID", run_context()["run_id"])
    env["PYTHONPATH"] = str(LAB_ROOT)
    if step.ansible and telemetry.enabled():
        # Cada task do Ansible vira um span dentro deste trace
        env["ANSIBLE_CALLBACKS_ENABLED"] = "community.general.opentelemetry"
        env.setdefault("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", "http/protobuf")
        env["OTEL_SERVICE_NAME"] = "netauto-ansible"
    return env


def run_step(step: Step, runner: Runner = subprocess.run) -> bool:
    with telemetry.tracer().start_as_current_span(f"step {step.name}") as span:
        span.set_attribute("netauto.step", step.name)
        started = time.monotonic()
        proc = runner(list(step.cmd), cwd=step.cwd, env=_env_for(step), check=False)
        span.set_attribute("process.exit_code", proc.returncode)
        ok = proc.returncode == 0
        if not ok:
            span.set_status(Status(StatusCode.ERROR, f"saída {proc.returncode}"))
        log.info(
            "etapa concluída" if ok else "etapa falhou",
            extra={
                "step": step.name,
                "exit_code": proc.returncode,
                "seconds": round(time.monotonic() - started, 1),
            },
        )
        return ok


def run_pipeline(
    name: str,
    steps: Sequence[Step],
    runner: Runner = subprocess.run,
    rollback: Step | None = ROLLBACK,
    after: Sequence[Step] = (DRIFT,),
) -> Result:
    """Executa em ordem; para no primeiro erro. Rollback só se o backup já tiver rodado."""
    result = Result()
    ctx = run_context()
    m = telemetry.meter()
    runs = m.create_counter("netauto.pipeline.runs", unit="{run}", description="Execuções do pipeline")
    duration = m.create_gauge(
        "netauto.pipeline.last_duration", unit="s", description="Duração da última execução"
    )
    success = m.create_gauge(
        "netauto.pipeline.last_success", unit="{bool}", description="1 se a última execução passou"
    )

    started = time.monotonic()
    with telemetry.tracer().start_as_current_span(
        f"netauto.{name}", context=telemetry.parent_from_env()
    ) as root:
        root.set_attribute("netauto.run_id", ctx["run_id"])
        root.set_attribute("vcs.ref.head.revision", ctx["commit"])
        for step in steps:
            result.executed.append(step.name)
            if not run_step(step, runner):
                result.ok = False
                result.failed_step = step.name
                break

        if not result.ok and rollback is not None and "backup" in result.executed[:-1]:
            log.warning("rollback automático", extra={"failed_step": result.failed_step})
            result.executed.append(rollback.name)
            result.rolled_back = run_step(rollback, runner)

        if "backup" in result.executed:
            for step in after:
                result.executed.append(step.name)
                run_step(step, runner)  # informativo: não muda o resultado do deploy

        root.set_attribute("netauto.result", "success" if result.ok else "failed")
        if result.failed_step:
            root.set_attribute("netauto.failed_step", result.failed_step)
            root.set_status(Status(StatusCode.ERROR, f"falhou em {result.failed_step}"))

    labels = {"pipeline": name}
    runs.add(1, {**labels, "result": "success" if result.ok else "failed"})
    duration.set(round(time.monotonic() - started, 2), labels)
    success.set(1 if result.ok else 0, labels)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fluxo de mudança instrumentado com OpenTelemetry")
    parser.add_argument("pipeline", choices=["deploy"])
    parser.add_argument("--check", action="store_true", help="só simula (ansible --check, sem post-checks)")
    args = parser.parse_args(argv)

    os.environ.setdefault("RUN_ID", run_context()["run_id"])
    if telemetry.setup():
        log.info("OpenTelemetry ligado", extra={"endpoint": os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"]})

    result = run_pipeline(args.pipeline, deploy_steps(check=args.check))
    log.info(
        "pipeline concluído" if result.ok else "pipeline falhou",
        extra={
            "steps": result.executed,
            "failed_step": result.failed_step,
            "rolled_back": result.rolled_back,
        },
    )
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
