#!/usr/bin/env python3
"""Prove the steward channel selects its executor explicitly and stays put."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.chat_agent import (  # noqa: E402
    MANAGED_HOST_CHAT_TRANSPORT_UNSUPPORTED,
    CodexChatAgentError,
)
from loopx.chat_manager import (  # noqa: E402
    MANAGER_ENDPOINT_ENV_VAR,
    MANAGER_ENDPOINT_SOURCE_EXPLICIT_CONFIG,
    manager_channel_binding,
    manager_executor_endpoint_default,
    manager_model_config,
    open_manager_session,
)
from loopx.chat_runtime import ChatRuntimeController  # noqa: E402
from loopx.chat_store import ChatSessionStore  # noqa: E402


CREDENTIAL_ENV = "DEEPSEEK_API_KEY"
CREDENTIAL_VALUE = "fixture-operator-credential"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"steward channel binding smoke failed: {message}")


def _assert_credential_does_not_select() -> dict[str, object]:
    """A configured provider key must not re-point the steward channel."""

    without_credential = manager_channel_binding({})
    with_credential = manager_channel_binding({CREDENTIAL_ENV: CREDENTIAL_VALUE})
    _assert(
        without_credential["executor_endpoint"] == "codex"
        and with_credential["executor_endpoint"] == "codex",
        "the steward channel must keep the shipped CLI endpoint either way",
    )
    _assert(
        without_credential["executor_endpoint_source"]
        == with_credential["executor_endpoint_source"]
        == "product_default",
        "a credential must never become the endpoint source",
    )
    _assert(
        without_credential["model"] == with_credential["model"] == "gpt-6-astra"
        and with_credential["model_source"] == "vendor_default",
        "a credential for a provider this channel does not run on must not move the model",
    )
    _assert(
        with_credential["operator_credential_configured"] is True
        and without_credential["operator_credential_configured"] is False,
        "the credential must still be reported as a fact",
    )
    _assert(
        CREDENTIAL_VALUE not in json.dumps(with_credential)
        and with_credential["credential_env_var"] == "",
        "the binding must never echo a credential value, nor claim one for a CLI endpoint",
    )
    _assert(
        manager_model_config(
            {CREDENTIAL_ENV: CREDENTIAL_VALUE, "LOOPX_MANAGER_MODEL": "fixture-model"}
        )
        == {"model": "fixture-model", "reasoning_effort": "high"},
        "an explicit model override must win over the shipped default",
    )
    return {
        "without_credential": without_credential,
        "with_credential": with_credential,
    }


def _assert_explicit_selection_and_managed_host_gate() -> dict[str, object]:
    """Explicit selection wins; the managed host fails closed as a typed gate."""

    selected = manager_channel_binding({MANAGER_ENDPOINT_ENV_VAR: "dsh"})
    _assert(
        selected["executor_endpoint"] == "dsh"
        and selected["executor_endpoint_source"]
        == MANAGER_ENDPOINT_SOURCE_EXPLICIT_CONFIG,
        "an explicit endpoint selection must win over the shipped default",
    )
    _assert(
        selected["executor_kind"] == "managed"
        and selected["available"] is False
        and selected["unavailable_reason"] == MANAGED_HOST_CHAT_TRANSPORT_UNSUPPORTED,
        "the managed host must report its missing Chat transport as a typed reason",
    )
    _assert(
        manager_executor_endpoint_default(
            {MANAGER_ENDPOINT_ENV_VAR: "dsh", CREDENTIAL_ENV: CREDENTIAL_VALUE}
        )
        == "dsh",
        "the selected endpoint must not depend on the credential",
    )

    with tempfile.TemporaryDirectory() as gate_root:
        root = Path(gate_root)
        runtime = ChatRuntimeController(
            store=ChatSessionStore(root / "store"), codex_bin="fixture-codex"
        )
        try:
            try:
                runtime.open_session(
                    goal_id="loopx-steward-binding-fixture",
                    agent_id="dsh",
                    work_dir=root,
                    objective="fixture",
                    mode="new",
                )
            except CodexChatAgentError as exc:
                _assert(
                    exc.error_code == MANAGED_HOST_CHAT_TRANSPORT_UNSUPPORTED
                    and exc.gate.get("kind") == "host_tool_gate"
                    and "loopx turn" in exc.gate.get("next_action", ""),
                    "the managed host must fail closed as a typed host-tool gate",
                )
            else:
                raise SystemExit(
                    "steward channel binding smoke failed: dsh opened an interactive session"
                )
        finally:
            runtime.close()
    return selected


def _assert_session_opens_the_selected_endpoint() -> str:
    """The channel opens the endpoint the operator selected, not a credential."""

    opened: list[dict[str, object]] = []

    class _Controller:
        def open_session(self, **kwargs):
            opened.append(kwargs)
            return {"session_id": "fixture-session"}, False

    controller = _Controller()
    with tempfile.TemporaryDirectory() as work_dir:
        ambient = os.environ.pop(CREDENTIAL_ENV, None)
        ambient_endpoint = os.environ.pop(MANAGER_ENDPOINT_ENV_VAR, None)
        try:
            open_manager_session(
                controller=controller,
                goal_id="loopx-steward-binding-fixture",
                work_dir=Path(work_dir),
            )
            _assert(
                opened[-1]["agent_id"] == "codex",
                "without a selection the manager session must open the shipped endpoint",
            )

            os.environ[CREDENTIAL_ENV] = CREDENTIAL_VALUE
            open_manager_session(
                controller=controller,
                goal_id="loopx-steward-binding-fixture",
                work_dir=Path(work_dir),
            )
            _assert(
                opened[-1]["agent_id"] == "codex",
                "a configured credential must not re-point the manager session",
            )
        finally:
            os.environ.pop(CREDENTIAL_ENV, None)
            if ambient is not None:
                os.environ[CREDENTIAL_ENV] = ambient
            if ambient_endpoint is not None:
                os.environ[MANAGER_ENDPOINT_ENV_VAR] = ambient_endpoint
    return str(opened[-1]["agent_id"])


def main() -> int:
    payload = {
        "ok": True,
        "credential_selection_probe": _assert_credential_does_not_select(),
        "explicit_selection": _assert_explicit_selection_and_managed_host_gate(),
        "opened_endpoint": _assert_session_opens_the_selected_endpoint(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
