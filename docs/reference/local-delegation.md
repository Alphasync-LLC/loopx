# Local delegation through governed Turns

An existing local Agent can launch explicitly bound peer work and reconnect to
its result after the requesting conversation disappears. The same interface is
available to a coordinating member. DSH and an optional cloud provider use the
existing Turn entrypoint; there is no steward-specific scheduler or task store.

## Activate

First register the participating Agents and bind the intended canonical Todos
to [owner-configured acceptance](goal-acceptance-observations.md). Prepare an
operator-owned JSON file **outside member workspaces**:

```json
{
  "schema_version": "loopx_local_delegation_v0",
  "bindings": [{
    "id": "independent-review",
    "agent_id": "reviewer",
    "todo_id": "todo_review",
    "requesters": ["lead", "analyst"],
    "workspace": "/absolute/reviewer-worktree",
    "host_args": ["--host", "dsh", "--dsh-model", "your-configured-model"],
    "timeout_seconds": 300,
    "output_refs": ["output.json"]
  }]
}
```

`requesters` is an execution grant for this exact binding. Registration, a peer
message or a coordinator role does not grant it. Host arguments are trusted
operator configuration and use the existing `turn run-once` options. For Ark,
select `generic-cli`, `fresh`, and the optional adapter's `--config` invocation.
Profiles, executables, workspace isolation and credential custody remain the
operator's responsibility. No model tool accepts those values.

Start the existing stdio server with the explicit opt-in:

```bash
python -m loopx.collaboration_mcp \
  --registry "$REGISTRY" --runtime-root "$RUNTIME_ROOT" \
  --goal-id "$GOAL_ID" --agent-id "$AGENT_ID" --workspace "$WORKSPACE" \
  --execution-config "$DELEGATION_CONFIG"
```

Without `--execution-config`, the original five collaboration tools are
unchanged and cannot launch workers. With it, the Agent can:

1. Call `list_execution_bindings` to find its authorized work.
2. Call `start_delegation(binding_id, operation_id, brief, parent_request_id?)`.
   Supply the existing `collaboration_brief_v0`, including purpose, context,
   constraints, inputs, acceptance and return requirement. Reuse the operation
   id after a lost response; changed content under the same id is rejected.
3. Continue other work, or call `wait_delegation` for a bounded wait. A `running`
   response is normal. `read_delegation` reads the durable original operation.
4. If `recovery_required` is true, call `resume_delegation` with that same id.
   This cannot retarget the work or silently create a replacement Turn.

Configure the member's host to expose its own identity-bound collaboration
tools. It reads `DELEGATION.json`, independently calls `assess_request`, and
produces the bound artifact. A nested coordinator uses its own grants and
forwards `parent_request_id`; the original semantic context is retained.

## Acceptance and return

The Turn validator reads only this task's current pinned criteria from the TS
acceptance owner. After a validated Turn, ordinary `todo complete` executes the
criteria again and commits through the existing canonical authority. The host
then reads current completion, binding guards and artifacts before returning
`accepted`. The overall Goal remains independent of this task result.

A member's peer conclusion is preserved. It is an opinion/evidence message,
not canonical completion; the host does not overwrite it with another reply.
When the member has not written a conclusion, the host returns compact
completion references through the existing peer return route. Reading a saved
accepted operation revalidates current artifacts and bindings. Edited output,
stale work, missing adoption and forged result files cannot certify completion.

The operation receipt lives under the runtime's existing private collaboration
storage (`.local/manager-context/executions`). It records execution observations,
request lineage, the original Turn key and bounded results. It does not replace
canonical Todo, claim, lease, quota, or acceptance ownership. Business ordering,
questions, repair decisions and synthesis remain Agent decisions.

## Disconnect and recovery

| Interruption | Behavior and recovery |
| --- | --- |
| Requesting MCP conversation closes | The detached bounded worker continues; another connection reads the original operation. |
| Duplicate start/resume while work runs | Operation identity, task lock and Turn journal prevent another concurrent execution. |
| Worker process or machine stops | Reconnect with the same operator configuration and credentials, then resume the original Turn. |
| Ark is computing without local tools | The already-started cloud turn can continue. It is not dependent on the local conversation. |
| Ark requests a local tool while the host is absent | It waits for the local tool result. Recovery observes the original input/session and executes only previously unstarted tool calls. |
| Tool execution or send acknowledgement is uncertain | Do not repeat the effect. Preserve the receipt/session for explicit reconciliation. |
| Task completed but return was interrupted | Read/validate the original task and return; do not rerun the model. |

Ark recovery retains the original execution deadline; reconnecting does not
reset the budget. Lost creation/input-send responses remain reconciliation
cases. This is a local trusted-host facility, not authenticated remote control,
automatic boot supervision, general live steering or a guarantee that an entire
team continues through a host outage. It introduces no frontend/Lark settings
or default executor change; those existing configuration surfaces are untouched.

To disable new admission, remove the caller's grants or remove
`--execution-config` from the host. A stopped Goal refuses new starts/resumes;
existing completed results remain readable. Disabling does not kill work already
running. Retain receipts, stop or reconcile owned workers, and confirm cloud
resource cleanup before deleting a disposable runtime. The optional adapter's
cleanup command never grants task completion.

For the mixed and nested research journey, see the
[synthetic research team](../../examples/managed-research-team/README.md).
