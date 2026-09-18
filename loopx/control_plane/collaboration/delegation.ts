/** Explicit local execution bindings. Registration/messages alone grant no launch.
 * These are host observations; canonical task/Turn/acceptance remain authoritative. */
import type {JsonObject} from "../effect_program.ts";
import {requireJsonObject} from "../runtime_decode.ts";
import {EffectRuntimeRequestError} from "../effect_runtime_errors.ts";

function requireThat(ok: unknown, message: string): asserts ok {
  if (!ok) throw new EffectRuntimeRequestError(message);
}
function text(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= 4096;
}
export function selectDelegationBinding(params: JsonObject): JsonObject {
  const config = requireJsonObject(params.config, "delegation configuration");
  requireThat(config.schema_version === "loopx_local_delegation_v0", "unsupported delegation configuration");
  requireThat(Array.isArray(config.bindings) && config.bindings.length <= 100, "bounded bindings required");
  const rows = config.bindings.map(value => requireJsonObject(value, "delegation binding"));
  requireThat(new Set(rows.map(row => row.id)).size === rows.length, "duplicate binding identity");
  const binding = rows.find(row => row.id === params.binding_id);
  requireThat(binding, "delegation binding unavailable");
  requireThat(new TextEncoder().encode(JSON.stringify(binding)).length <= 16000, "delegation binding exceeds limit");
  requireThat([binding.id, binding.agent_id, binding.todo_id, binding.workspace].every(text), "binding identity/workspace required");
  requireThat(Array.isArray(binding.requesters) && binding.requesters.includes(params.agent_id)
    && binding.agent_id !== params.agent_id, "caller has no delegation grant");
  requireThat(Array.isArray(binding.host_args) && binding.host_args.length > 0
    && binding.host_args.every(text), "operator host arguments required");
  requireThat(Number.isInteger(binding.timeout_seconds) && Number(binding.timeout_seconds) >= 1
    && Number(binding.timeout_seconds) <= 3600, "bounded execution timeout required");
  requireThat(Array.isArray(binding.output_refs) && binding.output_refs.length > 0
    && binding.output_refs.length <= 20 && binding.output_refs.every(ref => text(ref)
      && !ref.startsWith("/") && !ref.includes("\\") && !ref.split("/").includes("..")), "bounded relative output refs required");
  return binding;
}

type Observation = "prepared" | "running" | "turn_returned" | "accepted" | "rejected";
const transitions: Record<Observation, readonly Observation[]> = {
  prepared: ["running", "rejected"], running: ["turn_returned", "rejected"],
  turn_returned: ["accepted", "rejected"], accepted: [], rejected: [],
};
export function transitionDelegationObservation(params: JsonObject): JsonObject {
  const from = params.from as Observation, to = params.to as Observation;
  requireThat(Object.hasOwn(transitions, from) && Object.hasOwn(transitions, to), "invalid delegation observation");
  requireThat(from === to || transitions[from].includes(to), "invalid delegation observation transition");
  if (to === "accepted") requireThat(params.canonical_done === true
    && params.acceptance_ready === true && params.artifacts_current === true,
  "accepted return requires current canonical completion and artifacts");
  return {status: to};
}
