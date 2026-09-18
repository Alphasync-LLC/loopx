"""Example host composition: both coordinator and members use ordinary Turns."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def host_arguments(root: Path, actor: str, revision: str, *, host: str, attempt: int = 0) -> list[str]:
    settings = json.loads((root / "settings.json").read_text())
    coordinator = actor == "lead"
    workspace = root / "lead" if coordinator else root / actor / revision
    if host == "dsh":
        args = ["--host", "dsh", "--dsh-model", settings["dsh_model"], "--dsh-reasoning-effort", "high",
                "--dsh-home", str(root / "homes" / (actor + "-" + revision + "-" + str(attempt)))]
        if coordinator:
            patch = root / "lead-mcp.yml"
            forwarded = ["DEEPSEEK_API_KEY", "ARK_API_KEY"]
            forwarded += [name for name in ("DEEPSEEK_BASE_URL", "ARK_BASE_URL") if os.environ.get(name)]
            document = json.dumps([{"insert": [{
                "id": "research-team", "name": "@deepseek-ai/dsh-mcp-client",
                "config": {"transport": "stdio", "serverName": "research_team",
                           "command": sys.executable,
                           "args": [str(HERE / "server.py"), "--local-lead-root", str(root)],
                           "env": {name: "__environment_" + name + "__" for name in forwarded},
                           "toolCallTimeoutMs": 420_000,
                           "cwd": str(workspace), "failOnStartupError": True},
            }]}])
            # Cordis's public !!js environment references are resolved by the
            # local host. Persist names, never credential values. DSH deliberately
            # scrubs credentials from ambient MCP subprocess environments.
            for name in forwarded:
                document = document.replace(json.dumps("__environment_" + name + "__"), "!!js process.env." + name)
            patch.write_text(document)
            args.extend(["--dsh-cordis", str(patch)])
        return args
    if host != "ark":
        raise ValueError("unqualified_example_host")
    command = [sys.executable, "-m", "loopx_ark_turn.cli", "--model", settings["ark_model"],
               "--environment-id", settings["environment_id"], "--workspace", str(workspace),
               "--state-dir", str(root / "provider-receipts"), "--timeout-seconds", "1100" if coordinator else "220",
               "--tool-timeout-seconds", "420" if coordinator else "30", "--max-tool-calls", "16" if coordinator else "6",
               "--mcp-command-json", json.dumps([sys.executable, str(HERE / "server.py"),
                                                *([] if coordinator else ["--worker", actor, "--revision", revision])]),
               "--mcp-env", "LOOPX_RESEARCH_DEMO_ROOT"]
    if coordinator:
        command.extend(["--mcp-env", "DEEPSEEK_API_KEY"])
    for tool in (("read_assignment", "delegate", "write_report") if coordinator else ("read_input", "write_output")):
        command.extend(["--tool", tool])
    return ["--host", "generic-cli", "--iteration-context", "fresh", "--host-command-json", json.dumps(command)]
