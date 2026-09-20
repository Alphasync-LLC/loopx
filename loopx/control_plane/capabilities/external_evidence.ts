import { createHash } from "node:crypto";

import type { JsonObject } from "../effect_program.ts";
import { EffectRuntimeRequestError } from "../effect_runtime_errors.ts";
import {
  requireJsonObject,
  requireNonEmptyString,
  requireStringLiteral,
} from "../runtime_decode.ts";

export const EXTERNAL_EVIDENCE_REQUEST_SCHEMA_VERSION =
  "loopx_external_evidence_request_v0";
export const EXTERNAL_EVIDENCE_DISCOVERY_SCHEMA_VERSION =
  "loopx_external_evidence_discovery_v0";
export const EXTERNAL_EVIDENCE_PLAN_SCHEMA_VERSION =
  "loopx_external_evidence_plan_v0";
export const EXTERNAL_EVIDENCE_EXECUTION_SCHEMA_VERSION =
  "loopx_external_evidence_execution_v0";
export const EXTERNAL_EVIDENCE_RECEIPT_SCHEMA_VERSION =
  "loopx_external_evidence_receipt_v0";
export const EXTERNAL_EVIDENCE_ADMISSION_SCHEMA_VERSION =
  "loopx_external_evidence_admission_v0";
export const EXTERNAL_EVIDENCE_RETIREMENT_SCHEMA_VERSION =
  "loopx_external_evidence_retirement_v0";

const PROVIDER_KINDS = ["method", "connector"] as const;
const RECEIPT_STATUSES = ["succeeded", "failed", "no_evidence"] as const;
const EVIDENCE_BASES = ["stated", "observed", "tested", "inferred"] as const;
const ADMISSION_DECISIONS = ["admit", "reject"] as const;
const SHA256_RE = /^sha256:[0-9a-f]{64}$/;
const PROVIDER_ID_RE = /^[a-z][a-z0-9_.:-]{1,95}$/;
const SOURCE_REF_RE = /^(https?:\/\/|[a-z][a-z0-9+.-]*:\/\/|urn:)/;

function requireThat(value: unknown, message: string): asserts value {
  if (!value) throw new EffectRuntimeRequestError(message);
}

function boundedText(value: unknown, label: string, max = 4096): string {
  const result = requireNonEmptyString(value, label).trim();
  requireThat(result.length <= max, `${label} exceeds ${max} characters`);
  return result;
}

function boundedStrings(
  value: unknown,
  label: string,
  maxItems = 16,
  maxText = 256,
): string[] {
  requireThat(Array.isArray(value), `${label} must be an array`);
  requireThat(value.length <= maxItems, `${label} has too many items`);
  return value.map((item, index) =>
    boundedText(item, `${label}[${index}]`, maxText)
  );
}

function canonicalValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalValue);
  if (typeof value !== "object" || value === null) return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, child]) => [key, canonicalValue(child)]),
  );
}

function digest(value: unknown): string {
  return `sha256:${createHash("sha256")
    .update(JSON.stringify(canonicalValue(value)), "utf8")
    .digest("hex")}`;
}

function normalizeRequest(value: unknown): JsonObject {
  const request = requireJsonObject(value, "external evidence request");
  const normalized: JsonObject = {
    schema_version: EXTERNAL_EVIDENCE_REQUEST_SCHEMA_VERSION,
    objective: boundedText(request.objective, "request.objective"),
    user_activity: boundedText(request.user_activity, "request.user_activity"),
    decision: boundedText(request.decision, "request.decision"),
    evidence_kinds: boundedStrings(
      request.evidence_kinds,
      "request.evidence_kinds",
      8,
      96,
    ),
    constraints: request.constraints === undefined
      ? []
      : boundedStrings(request.constraints, "request.constraints", 16, 256),
  };
  requireThat(
    (normalized.evidence_kinds as string[]).length > 0,
    "request.evidence_kinds must not be empty",
  );
  normalized.request_id = digest(normalized);
  return normalized;
}

function normalizeProvider(value: unknown, index: number): JsonObject {
  const provider = requireJsonObject(value, `providers[${index}]`);
  const providerId = boundedText(
    provider.provider_id,
    `providers[${index}].provider_id`,
    96,
  );
  requireThat(PROVIDER_ID_RE.test(providerId), `providers[${index}].provider_id is invalid`);
  const providerKind = requireStringLiteral(
    provider.provider_kind,
    PROVIDER_KINDS,
    `providers[${index}].provider_kind`,
  );
  requireThat(
    provider.protocol === "external_evidence_research_v0",
    `providers[${index}].protocol is unsupported`,
  );
  for (const field of ["declared", "installed", "enabled", "ready"] as const) {
    requireThat(
      typeof provider[field] === "boolean",
      `providers[${index}].${field} must be boolean`,
    );
  }
  const ready = provider.ready === true;
  requireThat(
    !ready || (
      provider.declared === true &&
      provider.installed === true &&
      provider.enabled === true
    ),
    `providers[${index}] cannot be ready before declared, installed, and enabled`,
  );
  const unavailableReason = provider.unavailable_reason === null ||
      provider.unavailable_reason === undefined
    ? null
    : boundedText(
      provider.unavailable_reason,
      `providers[${index}].unavailable_reason`,
      512,
    );
  requireThat(
    ready || unavailableReason !== null,
    `providers[${index}] requires unavailable_reason when not ready`,
  );
  return {
    provider_id: providerId,
    provider_kind: providerKind,
    protocol: "external_evidence_research_v0",
    declared: provider.declared,
    installed: provider.installed,
    enabled: provider.enabled,
    ready,
    unavailable_reason: unavailableReason,
  };
}

function normalizeProviders(value: unknown): JsonObject[] {
  requireThat(Array.isArray(value), "providers must be an array");
  requireThat(value.length <= 64, "providers has too many items");
  const providers = value.map(normalizeProvider);
  requireThat(
    new Set(providers.map((provider) => provider.provider_id)).size === providers.length,
    "provider ids must be unique",
  );
  return providers;
}

export function projectExternalEvidenceDiscovery(params: JsonObject): JsonObject {
  const providers = normalizeProviders(params.providers);
  const readyProviders = providers.filter((provider) => provider.ready === true);
  const methodCount = providers.filter((provider) => provider.provider_kind === "method").length;
  const connectorCount = providers.length - methodCount;
  return {
    schema_version: EXTERNAL_EVIDENCE_DISCOVERY_SCHEMA_VERSION,
    status: providers.length === 0
      ? "empty"
      : readyProviders.length > 0
      ? "ready"
      : "inventory_only",
    providers,
    summary: {
      provider_count: providers.length,
      method_count: methodCount,
      connector_count: connectorCount,
      ready_count: readyProviders.length,
      unavailable_count: providers.length - readyProviders.length,
    },
    ready_provider_ids: readyProviders.map((provider) => provider.provider_id),
    truth_contract: {
      registry_presence_is_readiness: false,
      supported_status_is_readiness: false,
      execution_observed: false,
      evidence_coverage_observed: false,
    },
  };
}

export function planExternalEvidenceRequest(params: JsonObject): JsonObject {
  const request = normalizeRequest(params.request);
  const providers = normalizeProviders(params.providers);
  const preferredProviderId = params.preferred_provider_id === undefined ||
      params.preferred_provider_id === null
    ? null
    : boundedText(params.preferred_provider_id, "preferred_provider_id", 96);
  if (preferredProviderId !== null) {
    requireThat(
      providers.some((provider) => provider.provider_id === preferredProviderId),
      "preferred provider is not in the current inventory",
    );
  }
  const readyProviders = providers.filter((provider) => provider.ready === true);
  const selected = preferredProviderId === null
    ? readyProviders[0] ?? null
    : readyProviders.find((provider) => provider.provider_id === preferredProviderId) ?? null;
  const status = selected === null ? "blocked" : "ready";
  const executionEnvelope = selected === null
    ? null
    : {
      schema_version: "loopx_external_evidence_execution_envelope_v0",
      request_id: request.request_id,
      provider_id: selected.provider_id,
      provider_kind: selected.provider_kind,
      protocol: selected.protocol,
      authority: "read_external_sources_only",
      raw_content_persistence: "provider_private",
      result_contract: EXTERNAL_EVIDENCE_RECEIPT_SCHEMA_VERSION,
    };
  const plan = {
    schema_version: EXTERNAL_EVIDENCE_PLAN_SCHEMA_VERSION,
    status,
    request,
    provider_candidates: providers,
    selected_provider: selected,
    execution_envelope: executionEnvelope,
    blocker: selected === null
      ? preferredProviderId === null
        ? "no_ready_provider"
        : "preferred_provider_not_ready"
      : null,
  };
  const planId = digest(plan);
  return {
    ...plan,
    plan_id: planId,
    execution_envelope: executionEnvelope === null
      ? null
      : { ...executionEnvelope, plan_id: planId },
  };
}

function normalizeReadyPlan(value: unknown): JsonObject {
  const plan = requireJsonObject(value, "external evidence plan");
  requireThat(
    plan.schema_version === EXTERNAL_EVIDENCE_PLAN_SCHEMA_VERSION && plan.status === "ready",
    "external evidence execution requires a ready plan",
  );
  requireThat(plan.blocker === null, "a ready external evidence plan cannot have a blocker");
  const request = normalizeRequest(plan.request);
  const suppliedRequest = requireJsonObject(plan.request, "external evidence plan request");
  requireThat(
    suppliedRequest.request_id === request.request_id,
    "external evidence plan request_id does not match its normalized request",
  );
  const providers = normalizeProviders(plan.provider_candidates);
  const selected = normalizeProvider(plan.selected_provider, 0);
  requireThat(selected.ready === true, "external evidence selected provider is not ready");
  const selectedCandidate = providers.find(
    (provider) => provider.provider_id === selected.provider_id,
  );
  requireThat(
    selectedCandidate !== undefined && digest(selectedCandidate) === digest(selected),
    "external evidence selected provider does not match its provider candidate",
  );
  const planId = boundedText(plan.plan_id, "external evidence plan.plan_id", 71);
  requireThat(SHA256_RE.test(planId), "external evidence plan.plan_id is invalid");
  const executionEnvelope = {
    schema_version: "loopx_external_evidence_execution_envelope_v0",
    request_id: request.request_id,
    provider_id: selected.provider_id,
    provider_kind: selected.provider_kind,
    protocol: selected.protocol,
    authority: "read_external_sources_only",
    raw_content_persistence: "provider_private",
    result_contract: EXTERNAL_EVIDENCE_RECEIPT_SCHEMA_VERSION,
  };
  const suppliedEnvelope = requireJsonObject(
    plan.execution_envelope,
    "external evidence execution envelope",
  );
  requireThat(
    suppliedEnvelope.plan_id === planId &&
      digest(suppliedEnvelope) === digest({ ...executionEnvelope, plan_id: planId }),
    "external evidence execution envelope does not match the plan",
  );
  const normalizedPlan = {
    schema_version: EXTERNAL_EVIDENCE_PLAN_SCHEMA_VERSION,
    status: "ready",
    request,
    provider_candidates: providers,
    selected_provider: selected,
    execution_envelope: executionEnvelope,
    blocker: null,
  };
  requireThat(
    planId === digest(normalizedPlan),
    "external evidence plan_id does not match the normalized ready plan",
  );
  return {
    ...normalizedPlan,
    plan_id: planId,
    execution_envelope: { ...executionEnvelope, plan_id: planId },
  };
}

function sourceRecord(value: unknown, index: number): JsonObject {
  const source = requireJsonObject(value, `receipt.sources[${index}]`);
  const sourceRef = boundedText(source.source_ref, `receipt.sources[${index}].source_ref`, 2048);
  requireThat(
    SOURCE_REF_RE.test(sourceRef) && !sourceRef.startsWith("file://"),
    `receipt.sources[${index}].source_ref must be a non-file provenance URI`,
  );
  const contentDigest = boundedText(
    source.content_digest,
    `receipt.sources[${index}].content_digest`,
    71,
  );
  requireThat(SHA256_RE.test(contentDigest), `receipt.sources[${index}].content_digest is invalid`);
  return {
    source_ref: sourceRef,
    source_family: boundedText(
      source.source_family,
      `receipt.sources[${index}].source_family`,
      128,
    ),
    basis: requireStringLiteral(
      source.basis,
      EVIDENCE_BASES,
      `receipt.sources[${index}].basis`,
    ),
    finding: boundedText(source.finding, `receipt.sources[${index}].finding`, 4096),
    limitation: source.limitation === null || source.limitation === undefined
      ? null
      : boundedText(source.limitation, `receipt.sources[${index}].limitation`, 2048),
    publication_date: source.publication_date === null || source.publication_date === undefined
      ? null
      : boundedText(
        source.publication_date,
        `receipt.sources[${index}].publication_date`,
        64,
      ),
    accessed_at: boundedText(source.accessed_at, `receipt.sources[${index}].accessed_at`, 64),
    content_digest: contentDigest,
  };
}

function normalizeExecutionReceipt(
  planValue: unknown,
  value: unknown,
): { plan: JsonObject; receipt: JsonObject } {
  const plan = normalizeReadyPlan(planValue);
  const request = requireJsonObject(plan.request, "external evidence plan request");
  const selected = requireJsonObject(plan.selected_provider, "external evidence selected provider");
  const receipt = requireJsonObject(value, "external evidence receipt");
  requireThat(
    receipt.schema_version === EXTERNAL_EVIDENCE_RECEIPT_SCHEMA_VERSION,
    "external evidence receipt schema is invalid",
  );
  requireThat(receipt.plan_id === plan.plan_id, "receipt plan_id does not match the plan");
  requireThat(receipt.request_id === request.request_id, "receipt request_id does not match the plan");
  requireThat(receipt.provider_id === selected.provider_id, "receipt provider_id does not match the plan");
  requireThat(receipt.provider_kind === selected.provider_kind, "receipt provider_kind does not match the plan");
  const status = requireStringLiteral(receipt.status, RECEIPT_STATUSES, "receipt.status");
  requireThat(Array.isArray(receipt.sources), "receipt.sources must be an array");
  requireThat(receipt.sources.length <= 64, "receipt.sources has too many items");
  const sources = receipt.sources.map(sourceRecord);
  requireThat(
    new Set(sources.map((source) => source.source_ref)).size === sources.length,
    "receipt source refs must be unique",
  );
  requireThat(status !== "succeeded" || sources.length > 0, "a succeeded receipt requires evidence sources");
  requireThat(status === "succeeded" || sources.length === 0, "failed or no_evidence receipts cannot carry admitted sources");
  return {
    plan,
    receipt: {
      schema_version: EXTERNAL_EVIDENCE_RECEIPT_SCHEMA_VERSION,
      plan_id: plan.plan_id,
      request_id: request.request_id,
      provider_id: selected.provider_id,
      provider_kind: selected.provider_kind,
      status,
      sources,
      summary: boundedText(receipt.summary, "receipt.summary", 4096),
      limitations: receipt.limitations === undefined
        ? []
        : boundedStrings(receipt.limitations, "receipt.limitations", 16, 1024),
      completed_at: boundedText(receipt.completed_at, "receipt.completed_at", 64),
    },
  };
}

export function recordExternalEvidenceExecution(params: JsonObject): JsonObject {
  const { plan, receipt } = normalizeExecutionReceipt(params.plan, params.receipt);
  const executionIdentity = {
    plan_id: plan.plan_id,
    request_id: receipt.request_id,
    provider_id: receipt.provider_id,
    receipt_digest: digest(receipt),
  };
  return {
    schema_version: EXTERNAL_EVIDENCE_EXECUTION_SCHEMA_VERSION,
    execution_id: digest(executionIdentity),
    plan_id: plan.plan_id,
    request_id: receipt.request_id,
    provider_id: receipt.provider_id,
    provider_kind: receipt.provider_kind,
    status: receipt.status,
    receipt,
    truth_contract: {
      provider_execution_observed: true,
      evidence_produced: receipt.status === "succeeded",
      evidence_coverage_observed: false,
      automatic_admission: false,
      automatic_promotion: false,
      raw_source_fallback_allowed: true,
    },
  };
}

export function evaluateExternalEvidenceAdmission(params: JsonObject): JsonObject {
  const normalized = normalizeExecutionReceipt(params.plan, params.receipt);
  const plan = normalized.plan;
  const receipt = normalized.receipt;
  const request = requireJsonObject(plan.request, "external evidence plan request");
  const selected = requireJsonObject(plan.selected_provider, "external evidence selected provider");
  const status = receipt.status as string;
  const sources = receipt.sources as JsonObject[];
  const completedAt = receipt.completed_at as string;
  const receiptDigest = digest(receipt);
  const decision = requireJsonObject(params.decision, "parent admission decision");
  const disposition = requireStringLiteral(
    decision.disposition,
    ADMISSION_DECISIONS,
    "decision.disposition",
  );
  const reason = boundedText(decision.reason, "decision.reason", 2048);
  const admittedRefs = decision.admitted_source_refs === undefined
    ? []
    : boundedStrings(decision.admitted_source_refs, "decision.admitted_source_refs", 64, 2048);
  const availableRefs = new Set(sources.map((source) => source.source_ref as string));
  requireThat(
    admittedRefs.every((sourceRef) => availableRefs.has(sourceRef)),
    "decision.admitted_source_refs must refer to receipt sources",
  );
  requireThat(
    disposition !== "admit" || (status === "succeeded" && admittedRefs.length > 0),
    "admit requires a succeeded receipt and at least one admitted source",
  );
  requireThat(
    disposition !== "reject" || admittedRefs.length === 0,
    "reject cannot carry admitted sources",
  );
  const admitted = sources.filter((source) => admittedRefs.includes(source.source_ref as string));
  const admissionIdentity = {
    plan_id: plan.plan_id,
    request_id: request.request_id,
    provider_id: selected.provider_id,
    receipt_digest: receiptDigest,
    disposition,
    admitted_source_refs: admittedRefs,
  };
  return {
    schema_version: EXTERNAL_EVIDENCE_ADMISSION_SCHEMA_VERSION,
    admission_id: digest(admissionIdentity),
    plan_id: plan.plan_id,
    request_id: request.request_id,
    provider_id: selected.provider_id,
    provider_kind: selected.provider_kind,
    receipt_status: status,
    receipt_digest: receiptDigest,
    completed_at: completedAt,
    disposition,
    reason,
    admitted_source_refs: admittedRefs,
    downstream_projection: {
      schema_version: "loopx_external_evidence_projection_v0",
      plan_id: plan.plan_id,
      request_id: request.request_id,
      objective: request.objective,
      decision: request.decision,
      disposition,
      sources: admitted,
      summary: boundedText(receipt.summary, "receipt.summary", 4096),
      limitations: receipt.limitations === undefined
        ? []
        : boundedStrings(receipt.limitations, "receipt.limitations", 16, 1024),
    },
  };
}

export function projectExternalEvidenceRetirement(params: JsonObject): JsonObject {
  const admission = requireJsonObject(params.admission, "external evidence admission");
  requireThat(
    admission.schema_version === EXTERNAL_EVIDENCE_ADMISSION_SCHEMA_VERSION,
    "external evidence admission schema is invalid",
  );
  const admittedRefs = boundedStrings(
    admission.admitted_source_refs,
    "admission.admitted_source_refs",
    64,
    2048,
  );
  const downstreamRefs = params.downstream_source_refs === undefined
    ? []
    : boundedStrings(params.downstream_source_refs, "downstream_source_refs", 64, 2048);
  const covered = new Set(downstreamRefs);
  const missing = admittedRefs.filter((sourceRef) => !covered.has(sourceRef));
  const retireReady = admission.disposition === "reject" || missing.length === 0;
  return {
    schema_version: EXTERNAL_EVIDENCE_RETIREMENT_SCHEMA_VERSION,
    admission_id: admission.admission_id,
    plan_id: admission.plan_id,
    request_id: admission.request_id,
    status: retireReady ? "retire_ready" : "retained",
    retire_ready: retireReady,
    missing_downstream_source_refs: missing,
    reason: admission.disposition === "reject"
      ? "parent_rejected"
      : retireReady
      ? "all_admitted_sources_projected"
      : "admitted_sources_not_yet_projected",
  };
}
