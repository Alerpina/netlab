import subprocess

from netauto.pipeline import ROLLBACK, Step, deploy_steps, run_pipeline


class FakeRunner:
    """Simula os subprocessos: falha nas etapas pedidas e guarda o que rodou."""

    def __init__(self, fail: set[str] = frozenset()):
        self.fail = fail
        self.calls: list[dict] = []

    def __call__(self, cmd, cwd, env, check):
        self.calls.append({"cmd": cmd, "env": env})
        return subprocess.CompletedProcess(cmd, 1 if cmd[0] in self.fail else 0)


def steps(*names):
    return [Step(n, [n]) for n in names]


def test_deploy_tem_a_ordem_certa():
    assert [s.name for s in deploy_steps()] == ["render", "pre-checks", "backup", "apply", "post-checks"]


def test_check_mode_nao_roda_post_checks_e_passa_check_ao_ansible():
    plan = deploy_steps(check=True)
    assert [s.name for s in plan] == ["render", "pre-checks", "backup", "apply"]
    assert "--check" in plan[-1].cmd


def test_tudo_ok_roda_drift_no_fim_e_nao_faz_rollback():
    result = run_pipeline(
        "deploy", steps("render", "pre", "backup", "apply", "post"), FakeRunner(), after=steps("drift")
    )
    assert result.ok
    assert result.executed == ["render", "pre", "backup", "apply", "post", "drift"]
    assert not result.rolled_back


def test_falha_no_post_check_faz_rollback():
    runner = FakeRunner(fail={"post"})
    result = run_pipeline(
        "deploy", steps("render", "pre", "backup", "apply", "post"), runner, after=steps("drift")
    )
    assert not result.ok
    assert result.failed_step == "post"
    assert result.executed == ["render", "pre", "backup", "apply", "post", ROLLBACK.name, "drift"]
    assert result.rolled_back


def test_falha_antes_do_backup_nao_faz_rollback_nem_drift():
    result = run_pipeline(
        "deploy", steps("render", "pre", "backup", "apply"), FakeRunner(fail={"pre"}), after=steps("drift")
    )
    assert result.executed == ["render", "pre"]
    assert not result.rolled_back


def test_falha_no_proprio_backup_nao_faz_rollback():
    result = run_pipeline(
        "deploy", steps("render", "backup", "apply"), FakeRunner(fail={"backup"}), after=steps("drift")
    )
    assert result.executed == ["render", "backup", "drift"]
    assert not result.rolled_back


def test_todas_as_etapas_recebem_o_mesmo_run_id(monkeypatch):
    monkeypatch.setenv("RUN_ID", "run-123")
    runner = FakeRunner()
    run_pipeline("deploy", steps("a", "b"), runner, after=())
    assert {c["env"]["RUN_ID"] for c in runner.calls} == {"run-123"}
