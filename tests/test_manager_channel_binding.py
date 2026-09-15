"""The steward channel selects its executor explicitly; a credential only authenticates."""

from __future__ import annotations

import json

import pytest

from loopx.chat_agent import (
    MANAGED_HOST_CHAT_TRANSPORT_UNSUPPORTED,
    CodexChatAgentError,
)
from loopx.capabilities.manager_runtime import manager_runtime_capability_projection
from loopx.chat_manager import (
    MANAGER_ENDPOINT_SOURCE_EXPLICIT_CONFIG,
    MANAGER_ENDPOINT_SOURCE_PRODUCT_DEFAULT,
    MANAGER_MODEL_SOURCE_ENV_OVERRIDE,
    MANAGER_MODEL_SOURCE_VENDOR_DEFAULT,
    manager_channel_binding,
    manager_executor_endpoint_default,
    manager_model_config,
    open_manager_session,
    selected_manager_executor_endpoint,
)
from loopx.chat_runtime import ChatRuntimeController
from loopx.chat_store import ChatSessionStore


def test_the_shipped_steward_channel_defaults_to_the_cli_endpoint():
    binding = manager_channel_binding({})

    assert (
        binding["executor_endpoint"] == manager_executor_endpoint_default({}) == "codex"
    )
    assert (
        binding["executor_endpoint_source"] == MANAGER_ENDPOINT_SOURCE_PRODUCT_DEFAULT
    )
    assert binding["executor_kind"] == "individual"
    assert binding["credential_env_var"] == ""
    assert binding["operator_credential_configured"] is False
    assert binding["available"] is None
    assert binding["unavailable_reason"] is None
    assert binding["model"] == "gpt-6-astra"
    assert binding["model_source"] == MANAGER_MODEL_SOURCE_VENDOR_DEFAULT


def test_a_configured_credential_never_re_points_the_steward_channel():
    """Discovering a provider key must not change the executor or the model."""

    without = manager_channel_binding({})
    with_credential = manager_channel_binding({"DEEPSEEK_API_KEY": "fixture"})

    assert with_credential["executor_endpoint"] == without["executor_endpoint"]
    assert (
        with_credential["executor_endpoint_source"]
        == without["executor_endpoint_source"]
        == MANAGER_ENDPOINT_SOURCE_PRODUCT_DEFAULT
    )
    assert with_credential["model"] == without["model"] == "gpt-6-astra"
    assert with_credential["model_source"] == MANAGER_MODEL_SOURCE_VENDOR_DEFAULT
    # The credential stays a reported fact, not a selection signal.
    assert with_credential["operator_credential_configured"] is True
    assert with_credential["credential_env_var"] == ""
    assert "fixture" not in json.dumps(with_credential)


def test_an_explicit_endpoint_selection_wins_over_the_shipped_default():
    endpoint, source = selected_manager_executor_endpoint(
        {"LOOPX_MANAGER_ENDPOINT": "fixture-endpoint"}
    )

    assert (endpoint, source) == (
        "fixture-endpoint",
        MANAGER_ENDPOINT_SOURCE_EXPLICIT_CONFIG,
    )
    assert manager_executor_endpoint_default({"LOOPX_MANAGER_ENDPOINT": " "}) == "codex"


def test_selecting_the_managed_host_reports_the_missing_chat_transport():
    """The managed host is a bounded Turn host, so the channel fails closed."""

    binding = manager_channel_binding({"LOOPX_MANAGER_ENDPOINT": "dsh"})

    assert binding["executor_endpoint"] == "dsh"
    assert binding["executor_kind"] == "managed"
    assert binding["available"] is False
    assert binding["unavailable_reason"] == MANAGED_HOST_CHAT_TRANSPORT_UNSUPPORTED
    # An operator-billed endpoint names the credential it authenticates with.
    assert binding["credential_env_var"] == ""
    assert (
        manager_channel_binding(
            {"LOOPX_MANAGER_ENDPOINT": "dsh", "DEEPSEEK_API_KEY": "fixture"}
        )["credential_env_var"]
        == "DEEPSEEK_API_KEY"
    )


def test_an_unknown_explicit_endpoint_makes_no_availability_claim():
    binding = manager_channel_binding({"LOOPX_MANAGER_ENDPOINT": "fixture-endpoint"})

    assert binding["executor_kind"] == ""
    assert binding["available"] is None
    assert binding["model"] == "gpt-6-astra"


def test_explicit_model_override_wins_with_and_without_credential():
    overridden = manager_channel_binding(
        {"DEEPSEEK_API_KEY": "fixture", "LOOPX_MANAGER_MODEL": "fixture-model"}
    )
    assert overridden["model"] == "fixture-model"
    assert overridden["model_source"] == MANAGER_MODEL_SOURCE_ENV_OVERRIDE

    assert manager_model_config(
        {"DEEPSEEK_API_KEY": "fixture", "LOOPX_MANAGER_MODEL": "fixture-model"}
    ) == {"model": "fixture-model", "reasoning_effort": "high"}
    assert manager_model_config({"LOOPX_MANAGER_REASONING_EFFORT": "low"}) == {
        "model": "gpt-6-astra",
        "reasoning_effort": "low",
    }


def test_manager_model_config_reads_the_process_environment(monkeypatch):
    monkeypatch.delenv("LOOPX_MANAGER_MODEL", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture")

    assert manager_model_config()["model"] == "gpt-6-astra"


def test_open_manager_session_resolves_the_endpoint_only_when_unset(tmp_path):
    calls: list[dict[str, object]] = []

    class Controller:
        def open_session(self, **kwargs):
            calls.append(kwargs)
            return {"session_id": "fixture"}, False

    controller = Controller()
    open_manager_session(controller=controller, goal_id="g", work_dir=tmp_path)
    assert calls[-1]["agent_id"] == manager_executor_endpoint_default()

    open_manager_session(
        controller=controller,
        goal_id="g",
        work_dir=tmp_path,
        executor_endpoint_id="claude-code",
    )
    assert calls[-1]["agent_id"] == "claude-code"


def test_managed_host_without_a_chat_transport_raises_a_typed_gate(tmp_path):
    runtime = ChatRuntimeController(
        store=ChatSessionStore(tmp_path / "store"), codex_bin="fixture-codex"
    )
    try:
        with pytest.raises(CodexChatAgentError) as raised:
            runtime.open_session(
                goal_id="fixture-goal",
                agent_id="dsh",
                work_dir=tmp_path,
                objective="fixture",
                mode="new",
            )
    finally:
        runtime.close()

    assert raised.value.error_code == MANAGED_HOST_CHAT_TRANSPORT_UNSUPPORTED
    assert raised.value.gate["kind"] == "host_tool_gate"
    assert "loopx turn" in raised.value.gate["next_action"]


def test_unknown_endpoint_keeps_the_untyped_lookup_error(tmp_path):
    runtime = ChatRuntimeController(
        store=ChatSessionStore(tmp_path / "store"), codex_bin="fixture-codex"
    )
    try:
        with pytest.raises(ValueError, match="unknown Agent endpoint"):
            runtime.open_session(
                goal_id="fixture-goal",
                agent_id="not-a-registered-endpoint",
                work_dir=tmp_path,
                objective="fixture",
                mode="new",
            )
    finally:
        runtime.close()


def test_manager_capability_projection_carries_the_channel_binding():
    binding = manager_channel_binding({"DEEPSEEK_API_KEY": "fixture"})
    projection = manager_runtime_capability_projection(
        object(),
        {"model": "gpt-6-astra", "reasoning_effort": "high"},
        channel_binding=binding,
    )

    assert projection["scope"] == "owner_global"
    assert projection["channel_binding"] == binding
    assert "fixture" not in json.dumps(projection)


def test_manager_capability_projection_stays_unchanged_without_a_binding():
    projection = manager_runtime_capability_projection(
        object(), {"model": "gpt-6-astra", "reasoning_effort": "high"}
    )

    assert "channel_binding" not in projection
    assert projection["model"] == "gpt-6-astra"
