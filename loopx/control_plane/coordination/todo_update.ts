import type { JsonObject } from "../effect_program.ts";
import { TODO_OWNERSHIP_INTENT_FIELDS } from "../todos/authoring_scope.ts";
import type { AuthorityStore, AuthorityStoreCommit } from "./authority_store.ts";
import {
  AuthorityStoreProtocolError,
  canonicalAuthorityBytes,
  canonicalAuthorityObject,
  canonicalAuthoritySha256,
  requireAuthorityStoreId,
} from "./authority_store_codec.ts";
import {canonicalTodoRecord} from "./todo_presentation.ts";
import {
  indexCoordinationProjection,
  prepareCoordinationProjectionCommit,
  validateCoordinationTodoReadModel,
} from "./coordination_projection.ts";
import { normalizeRegisteredTodoAgents, normalizeTodoAgent } from "./todo_agents.ts";

import {todoUpdateAdmissionRejection} from "./todo_update_admission.ts";
import { normalizeNativePlanningIntent, planNativeTodoUpdate } from "../todos/native_update_plan.ts";
import { CoordinationCommandReceipt } from "./command_receipt.ts";

export const COORDINATION_TODO_UPDATE_REQUEST_SCHEMA =
  "loopx_local_coordination_todo_update_request_v0";
// Older runtimes must reject planning requests rather than commit only their copy patch.
export const COORDINATION_TODO_PLANNING_UPDATE_REQUEST_SCHEMA =
  "loopx_local_coordination_todo_update_request_v1";
// Admission witnesses and reviewed CAS must never be silently ignored by v0/v1.
export const COORDINATION_TODO_REVIEWED_UPDATE_REQUEST_SCHEMA =
  "loopx_local_coordination_todo_update_request_v2";
export const COORDINATION_TODO_UPDATE_RESULT_SCHEMA =
  "loopx_coordination_todo_update_result_v0";
export const COORDINATION_TODO_UPDATE_RECEIPT_SCHEMA =
  "loopx_coordination_todo_update_receipt_v0";

const UPDATE_FIELDS = new Set(["text", "note"]);

export interface CoordinationTodoUpdateInput {
  readonly goal_id: string;
  readonly todo_id: string;
  readonly expected_role: string | null;
  readonly actor_agent_id: string | null;
  readonly registered_agents: readonly string[];
  readonly operation_id: string;
  readonly expected_provider_revision?: string;
  readonly expected_registry_sha256?: string;
  readonly lifecycle_grants?: readonly JsonObject[];
  readonly authority_reason?: string | null;
  readonly patch: JsonObject;
  readonly clear_fields: readonly string[];
  readonly dry_run: boolean;
  readonly now: Date;
  readonly lease_idempotency_key?: string | null;
  readonly lease_expected_version?: number | null;
  readonly planning_intent?: JsonObject;
}

export type CoordinationTodoUpdateResult = JsonObject & {
  readonly schema_version: typeof COORDINATION_TODO_UPDATE_RESULT_SCHEMA;
};

function failure(code: string, reason: string): CoordinationTodoUpdateResult {
  return {schema_version: COORDINATION_TODO_UPDATE_RESULT_SCHEMA, status: "failed",
    changed: false, reason_code: code, reason};
}

function isFailure(value: JsonObject): value is CoordinationTodoUpdateResult {
  return value.schema_version === COORDINATION_TODO_UPDATE_RESULT_SCHEMA &&
    value.status === "failed";
}

function normalizeInput(raw: CoordinationTodoUpdateInput): CoordinationTodoUpdateInput {
  if (raw.expected_provider_revision !== undefined) {
    requireAuthorityStoreId(raw.expected_provider_revision, "expected_provider_revision");
  }
  if (raw.expected_registry_sha256 !== undefined && !/^[a-f0-9]{64}$/u.test(raw.expected_registry_sha256)) {
    throw new AuthorityStoreProtocolError("expected_registry_sha256 must be a SHA-256 digest");
  }
  if (raw.authority_reason != null && typeof raw.authority_reason !== "string") {
    throw new AuthorityStoreProtocolError("authority_reason must be a string");
  }
  const planningIntent = normalizeNativePlanningIntent(raw.planning_intent);
  const key = raw.lease_idempotency_key ?? null;
  const version = raw.lease_expected_version ?? null;
  if (key !== null && (typeof key !== "string" || !key.trim() || key !== key.trim())) {
    throw new AuthorityStoreProtocolError("lease_idempotency_key must be a non-empty unpadded string");
  }
  if (version !== null && (!Number.isSafeInteger(version) || version < 0)) {
    throw new AuthorityStoreProtocolError("lease_expected_version must be a non-negative safe integer");
  }
  const patch = canonicalAuthorityObject(raw.patch, "Todo update patch");
  const clearFields = raw.clear_fields.map((field, index) =>
    requireAuthorityStoreId(field, `clear_fields[${index}]`));
  if (Object.keys(patch).length + clearFields.length + Object.keys(planningIntent).length === 0) {
    throw new AuthorityStoreProtocolError("Todo update requires a non-empty patch");
  }
  if (new Set(clearFields).size !== clearFields.length) {
    throw new AuthorityStoreProtocolError("clear_fields must be unique");
  }
  const unsupported = [...Object.keys(patch), ...clearFields]
    .find((field) => !UPDATE_FIELDS.has(field));
  if (unsupported !== undefined) {
    throw new AuthorityStoreProtocolError(`Todo update does not own field ${unsupported}`);
  }
  if (Object.keys(patch).some((field) => clearFields.includes(field))) {
    throw new AuthorityStoreProtocolError("Todo update cannot patch and clear the same field");
  }
  if (raw.expected_role !== null && !["agent", "user"].includes(raw.expected_role)) {
    throw new AuthorityStoreProtocolError("expected_role must be agent or user");
  }
  if (typeof raw.dry_run !== "boolean") {
    throw new AuthorityStoreProtocolError("dry_run must be a boolean");
  }
  if (!(raw.now instanceof Date) || Number.isNaN(raw.now.valueOf())) {
    throw new AuthorityStoreProtocolError("now must be a valid Date");
  }
  return {...raw, planning_intent: planningIntent, lease_idempotency_key: key, lease_expected_version: version,
    goal_id: requireAuthorityStoreId(raw.goal_id, "goal id"),
    todo_id: requireAuthorityStoreId(raw.todo_id, "todo id"),
    operation_id: requireAuthorityStoreId(raw.operation_id, "operation id"),
    actor_agent_id: raw.actor_agent_id === null ? null :
      normalizeTodoAgent(raw.actor_agent_id, "actor_agent_id"),
    registered_agents: normalizeRegisteredTodoAgents(raw.registered_agents),
    patch, clear_fields: clearFields};
}

function updateReceipt(input: CoordinationTodoUpdateInput, requestSha: string) {
  return new CoordinationCommandReceipt({result_schema: COORDINATION_TODO_UPDATE_RESULT_SCHEMA,
    identity: {schema_version: COORDINATION_TODO_UPDATE_RECEIPT_SCHEMA,
      operation_id: input.operation_id, goal_id: input.goal_id, todo_id: input.todo_id,
      request_sha256: requestSha}, failure,
    decode(original) {
      if (typeof original.changed !== "boolean") throw new AuthorityStoreProtocolError("update receipt changed must be boolean");
      return {fields: {todo_id: input.todo_id, original_receipt: original}, changed: original.changed};
    }});
}

function updateRequestSha(input: CoordinationTodoUpdateInput): string {
  return canonicalAuthoritySha256({goal_id: input.goal_id,
    todo_id: input.todo_id, expected_role: input.expected_role,
    actor_agent_id: input.actor_agent_id, patch: input.patch,
    ...(input.expected_provider_revision === undefined ? {} :
      {expected_provider_revision: input.expected_provider_revision}),
    ...(input.expected_registry_sha256 === undefined ? {} :
      {expected_registry_sha256: input.expected_registry_sha256}),
    ...(input.authority_reason == null ? {} : {authority_reason: input.authority_reason}),
    clear_fields: input.clear_fields, dry_run: input.dry_run,
    ...(Object.keys(input.planning_intent ?? {}).length ? {planning_intent: input.planning_intent} : {}),
    // Preserve receipt identity for pre-proof requests already persisted in v0.
    ...(input.lease_idempotency_key != null || input.lease_expected_version != null ? {
      lease_idempotency_key: input.lease_idempotency_key,
      lease_expected_version: input.lease_expected_version,
    } : {}),
  });
}

function loadUpdateTarget(
  head: JsonObject, input: CoordinationTodoUpdateInput,
): {todo: JsonObject; leases: ReadonlyMap<string, JsonObject>} | CoordinationTodoUpdateResult {
  try {
    validateCoordinationTodoReadModel(head, input.goal_id);
    const projection = indexCoordinationProjection(head, input.goal_id);
    const found = projection.todos.get(input.todo_id);
    return found === undefined
      ? failure("todo_not_found", "canonical Todo is missing")
      : {todo: found, leases: projection.leases};
  } catch (error) {
    return failure("invalid_coordination_projection",
      error instanceof Error ? error.message : "invalid coordination projection");
  }
}

function prepareUpdatedTodo(
  todo: JsonObject, input: CoordinationTodoUpdateInput, head: JsonObject,
): {next: JsonObject; changed: boolean; clearFields: string[]} | CoordinationTodoUpdateResult {
  const next: JsonObject = {...todo, ...input.patch};
  for (const field of input.clear_fields) delete next[field];
  // Preserve the public planner's legacy metadata semantics. Raw copy edits
  // already carry actor attribution, while planning-only updates historically
  // leave last_actor_agent_id untouched.
  const rawCopyChanged = Object.entries(input.patch).some(([field, value]) =>
    !Object.hasOwn(todo, field) || !canonicalAuthorityBytes(todo[field]).equals(canonicalAuthorityBytes(value))) ||
    input.clear_fields.some(field => Object.hasOwn(todo, field));
  if (rawCopyChanged || TODO_OWNERSHIP_INTENT_FIELDS.some(field => Object.hasOwn(input.planning_intent ?? {}, field))) {
    next.last_actor_agent_id = input.actor_agent_id;
  }
  next.updated_at = input.now.toISOString().replace(/\.\d{3}Z$/u, "Z");
  const clearFields = new Set(input.clear_fields);
  try {
    if (Object.keys(input.planning_intent ?? {}).length) {
      const updates = planNativeTodoUpdate(todo, input.planning_intent!, head,
        input.actor_agent_id, input.registered_agents, String(next.updated_at));
      for (const [field, value] of Object.entries(updates)) {
        // Markdown compatibility omits empty scalar metadata. Treat an
        // explicit empty planning scalar as a clear in the canonical record as
        // well; omission and clear are no longer conflated by the planner.
        if (value === null || value === "") { delete next[field]; clearFields.add(field); }
        else next[field] = value;
      }
      next.done = next.status === "done" || next.status === "deferred";
    }
    canonicalTodoRecord(next, "updated Todo");
  } catch (error) {
    return failure("invalid_coordination_todo_update",
      error instanceof Error ? error.message : "invalid updated Todo");
  }
  const changedBeforeAudit = {...next};
  delete changedBeforeAudit.last_actor_agent_id;
  delete changedBeforeAudit.updated_at;
  const originalBeforeAudit = {...todo};
  delete originalBeforeAudit.last_actor_agent_id;
  delete originalBeforeAudit.updated_at;
  const changed = !canonicalAuthorityBytes(changedBeforeAudit).equals(
    canonicalAuthorityBytes(originalBeforeAudit));
  if (!changed) {
    next.last_actor_agent_id = todo.last_actor_agent_id;
    next.updated_at = todo.updated_at;
  }
  return {next, changed, clearFields: [...clearFields]};
}

/** Update mutable Todo metadata from the canonical provider head. */
export async function executeCoordinationTodoUpdate(
  store: AuthorityStore, rawInput: CoordinationTodoUpdateInput,
  authoritySourcesCurrent: () => Promise<boolean> = async () => true,
): Promise<CoordinationTodoUpdateResult> {
  let input: CoordinationTodoUpdateInput;
  try { input = normalizeInput(rawInput); } catch (error) {
    return failure("invalid_coordination_todo_update",
      error instanceof Error ? error.message : "invalid Todo update");
  }
  const requestSha = updateRequestSha(input);
  const receipt = updateReceipt(input, requestSha);
  const replay = await receipt.read(store);
  if (replay !== null) return replay;
  const sourceChanged = () => failure("authority_source_changed",
    "Todo authority registration changed; review the current state before continuing");
  if (!await authoritySourcesCurrent()) return sourceChanged();
  // Legacy single-agent callers historically omitted actor_agent_id for an
  // unowned Todo. Keep that narrow compatibility path, while retaining the
  // registered-actor requirement for multi-agent or explicitly-owned work.
  if (input.actor_agent_id === null) {
    if (input.registered_agents.length > 1) {
      return failure("actor_not_registered", "Todo update requires a registered actor");
    }
  } else if (input.registered_agents.length === 0 ||
      !input.registered_agents.includes(input.actor_agent_id)) {
    return failure("actor_not_registered", "Todo update requires a registered actor");
  }
  const head = await store.loadAuthority();
  if (head.status !== "loaded") {
    return {schema_version: COORDINATION_TODO_UPDATE_RESULT_SCHEMA, ...head, changed: false};
  }
  if (input.expected_provider_revision !== undefined &&
      input.expected_provider_revision !== head.provider_revision) {
    return failure("provider_revision_mismatch", "Current revision changed; inspect again before continuing");
  }

  const target = loadUpdateTarget(head.head, input);
  if (isFailure(target)) return target;
  const rejected = todoUpdateAdmissionRejection(head.head, target.todo, target.leases, input);
  if (rejected !== null) return failure(rejected.code, rejected.reason);
  const prepared = prepareUpdatedTodo(target.todo, input, head.head);
  if (isFailure(prepared)) return prepared;
  const {next, changed, clearFields} = prepared;
  // The provider CAS covers Todo/lease state. Registry configuration is a
  // separate source witness, not part of a distributed transaction.
  if (!await authoritySourcesCurrent()) return sourceChanged();
  if (input.dry_run) return {schema_version: COORDINATION_TODO_UPDATE_RESULT_SCHEMA,
    status: changed ? "planned" : "no_change", changed, todo_id: input.todo_id,
    provider_revision: head.provider_revision, cursor: head.cursor, dry_run: true};
  const commit: AuthorityStoreCommit = changed ? prepareCoordinationProjectionCommit({
    goal_id: input.goal_id, operation_id: input.operation_id,
    expected_provider_revision: head.provider_revision, projection: head.head,
    mutations: [{kind: "todo_upsert", todo: next, clear_fields: clearFields}],
  }) : {operation_id: input.operation_id,
    expected_provider_revision: head.provider_revision, next_projection: head.head,
    events: [], receipts: []};
  commit.receipts = [{schema_version: COORDINATION_TODO_UPDATE_RECEIPT_SCHEMA,
    operation_id: input.operation_id, goal_id: input.goal_id,
    todo_id: input.todo_id, request_sha256: requestSha, changed}];
  return receipt.commit(store, commit);
}
