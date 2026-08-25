"""Threat-matrix RED tests: documentation-like paths must not start the stack."""

from __future__ import annotations

import subprocess

import pytest

from cost_mgmt_etl.stack import run_stack


class _ForbiddenRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple, dict]] = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError(f"compose/kubectl must not be invoked: {args} {kwargs}")


@pytest.mark.parametrize(
    "path",
    [
        "requirements.txt",
        "CMakeLists.txt",
        "README.md",
        "docs/run.mdx",
        "README.sh",
    ],
)
def test_documentation_like_paths_are_rejected_without_subprocess(path: str) -> None:
    runner = _ForbiddenRunner()
    code = run_stack(path, runner=runner)
    assert code != 0
    assert runner.calls == []


def test_allowed_compose_yaml_uses_list_argv_never_shell() -> None:
    recorded: list[tuple[list[str], dict]] = []

    def runner(cmd, **kwargs):
        recorded.append((list(cmd), kwargs))
        return subprocess.CompletedProcess(cmd, 0)

    code = run_stack("compose.yaml", runner=runner)
    assert code == 0
    assert recorded, "allowed compose.yaml must invoke the compose engine"
    cmd, kwargs = recorded[0]
    assert kwargs.get("shell") is not True
    assert "shell" not in kwargs or kwargs["shell"] is False
    assert cmd[0] in {"podman", "docker", "podman-compose", "docker-compose"}
    assert "compose.yaml" in cmd
    joined = " ".join(cmd)
    assert "kubectl" not in joined


def test_allowed_deploy_yaml_uses_kubectl_without_shell() -> None:
    recorded: list[tuple[list[str], dict]] = []

    def runner(cmd, **kwargs):
        recorded.append((list(cmd), kwargs))
        return subprocess.CompletedProcess(cmd, 0)

    code = run_stack("deploy/cronjob.yaml", runner=runner)
    assert code == 0
    cmd, kwargs = recorded[0]
    assert kwargs.get("shell") is not True
    assert cmd[0] == "kubectl"
    assert "deploy/cronjob.yaml" in cmd


def test_nested_or_absolute_paths_are_rejected() -> None:
    runner = _ForbiddenRunner()
    assert run_stack("/tmp/compose.yaml", runner=runner) != 0
    assert run_stack("deploy/../compose.yaml", runner=runner) != 0
    assert run_stack("compose.yaml; rm -rf /", runner=runner) != 0
    assert runner.calls == []
