"""The Turn host is selected explicitly; a credential only authenticates it."""

from __future__ import annotations

import pytest

from loopx.cli import build_parser
from loopx.control_plane.operator_credential import configured_operator_credential
from loopx.control_plane.turn_driver.host_binding import (
    MANAGED_DEFAULT_TURN_HOST,
    MANAGED_TURN_HOST,
    TURN_HOST_ENV_VAR,
    TURN_HOST_SOURCE_EXPLICIT_CONFIG,
    TURN_HOST_SOURCE_PRODUCT_DEFAULT,
    resolve_default_turn_host,
    selected_turn_host,
)


def test_default_host_is_the_managed_product_default():
    assert MANAGED_DEFAULT_TURN_HOST == MANAGED_TURN_HOST == "dsh"
    assert resolve_default_turn_host({}) == MANAGED_DEFAULT_TURN_HOST
    assert selected_turn_host({}) == (
        MANAGED_DEFAULT_TURN_HOST,
        TURN_HOST_SOURCE_PRODUCT_DEFAULT,
    )


@pytest.mark.parametrize(
    "environ",
    [
        {"DEEPSEEK_API_KEY": "sk-operator"},
        {"DEEPSEEK_API_KEY": ""},
        {"DEEPSEEK_API_KEY": "   "},
        {"DEEPSEEK_BASE_URL": "https://example.invalid"},
        {"DEEPSEEK_API_KEY": "sk-operator", "DEEPSEEK_BASE_URL": "https://x.invalid"},
    ],
)
def test_a_credential_never_changes_the_selected_host(environ):
    """Discovering a credential must not re-point a Turn by itself."""

    assert resolve_default_turn_host(environ) == MANAGED_DEFAULT_TURN_HOST
    assert selected_turn_host(environ)[1] == TURN_HOST_SOURCE_PRODUCT_DEFAULT


def test_explicit_config_repoints_the_default_host():
    environ = {TURN_HOST_ENV_VAR: "codex-cli", "DEEPSEEK_API_KEY": "sk-operator"}

    assert selected_turn_host(environ) == (
        "codex-cli",
        TURN_HOST_SOURCE_EXPLICIT_CONFIG,
    )
    assert resolve_default_turn_host(environ) == "codex-cli"


def test_configured_credential_names_the_env_var():
    assert (
        configured_operator_credential({"DEEPSEEK_API_KEY": "sk-operator"})
        == "DEEPSEEK_API_KEY"
    )
    assert configured_operator_credential({}) is None


def _turn_argv(command: str) -> list[str]:
    argv = ["turn", command, "--goal-id", "goal-x", "--agent-id", "agent-x"]
    if command == "run-once":
        argv.extend(["--project", "."])
    return argv


@pytest.mark.parametrize("command", ["plan", "run-once"])
@pytest.mark.parametrize(
    "environ",
    [{}, {"DEEPSEEK_API_KEY": "sk-operator"}, {"DEEPSEEK_API_KEY": "   "}],
)
def test_cli_defaults_to_the_selected_host_regardless_of_credentials(
    command, environ, monkeypatch
):
    for name in ("DEEPSEEK_API_KEY", TURN_HOST_ENV_VAR):
        monkeypatch.delenv(name, raising=False)
    for name, value in environ.items():
        monkeypatch.setenv(name, value)

    assert (
        build_parser().parse_args(_turn_argv(command)).host == MANAGED_DEFAULT_TURN_HOST
    )


@pytest.mark.parametrize("command", ["plan", "run-once"])
def test_explicit_config_environment_repoints_the_cli_default(command, monkeypatch):
    monkeypatch.setenv(TURN_HOST_ENV_VAR, "codex-cli")

    assert build_parser().parse_args(_turn_argv(command)).host == "codex-cli"


def test_explicit_host_flag_wins_over_the_default(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-operator")
    monkeypatch.setenv(TURN_HOST_ENV_VAR, "dsh")

    args = build_parser().parse_args([*_turn_argv("run-once"), "--host", "generic-cli"])

    assert args.host == "generic-cli"


@pytest.mark.parametrize("command", ["plan", "run-once"])
def test_default_execution_mode_follows_the_selected_host(command, monkeypatch):
    for name in ("DEEPSEEK_API_KEY", TURN_HOST_ENV_VAR):
        monkeypatch.delenv(name, raising=False)
    managed = build_parser().parse_args(_turn_argv(command))

    monkeypatch.setenv(TURN_HOST_ENV_VAR, "codex-cli")
    individual = build_parser().parse_args(_turn_argv(command))

    # The selected managed host runs bounded headless Turns; pairing it with a
    # visible interactive mode would make the shipped default unschedulable.
    # run-once ships only the isolated-headless mode, so it keeps that either way.
    assert managed.host == MANAGED_DEFAULT_TURN_HOST
    assert managed.execution_mode == "isolated-headless"
    assert individual.host == "codex-cli"
    assert individual.execution_mode == (
        "interactive-visible" if command == "plan" else "isolated-headless"
    )
