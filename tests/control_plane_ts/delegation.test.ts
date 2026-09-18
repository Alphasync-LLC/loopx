import test from "node:test";
import assert from "node:assert/strict";
import {selectDelegationBinding, transitionDelegationObservation} from "../../loopx/control_plane/collaboration/delegation.ts";

const binding = {id: "review", agent_id: "reviewer", todo_id: "todo_review", workspace: "/fixture",
  requesters: ["coordinator", "analyst"], host_args: ["--host", "dsh"], timeout_seconds: 60, output_refs: ["output.json"]};
const params = {agent_id: "coordinator", binding_id: "review",
  config: {schema_version: "loopx_local_delegation_v0", bindings: [binding]}};

test("same explicit grant contract applies to a coordinator and an ordinary member", () => {
  assert.deepEqual(selectDelegationBinding(params), binding);
  assert.deepEqual(selectDelegationBinding({...params, agent_id: "analyst"}), binding);
  assert.throws(() => selectDelegationBinding({...params, agent_id: "unbound"}), /no delegation grant/);
  assert.throws(() => selectDelegationBinding({...params, agent_id: "reviewer"}), /no delegation grant/);
  assert.throws(() => selectDelegationBinding({...params, binding_id: "other"}), /unavailable/);
});

test("malformed operator binding fails before launch", () => {
  for (const patch of [{timeout_seconds: 0}, {timeout_seconds: 5000}, {output_refs: ["../secret"]},
    {output_refs: ["/secret"]}, {host_args: []}, {todo_id: null}]) {
    assert.throws(() => selectDelegationBinding({...params,
      config: {...params.config, bindings: [{...binding, ...patch}]}}));
  }
});

test("message receipt and model return do not imply accepted work", () => {
  assert.throws(() => transitionDelegationObservation({from: "prepared", to: "accepted"}), /transition/);
  assert.throws(() => transitionDelegationObservation({from: "turn_returned", to: "accepted"}), /canonical/);
  assert.throws(() => transitionDelegationObservation({from: "rejected", to: "running"}), /transition/);
  assert.deepEqual(transitionDelegationObservation({from: "turn_returned", to: "accepted",
    canonical_done: true, acceptance_ready: true, artifacts_current: true}), {status: "accepted"});
});
