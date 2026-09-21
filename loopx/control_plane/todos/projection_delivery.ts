/** Canonical projection-delivery state returned by Todo mutations. */
export type TodoProjectionDelivery = "pending" | "delivered" | "current" | "not_required";
const PROJECTION_DELIVERY_VALUES = new Set<TodoProjectionDelivery>([
  "pending", "delivered", "current", "not_required",
]);

/** Keep mutation results consistent and make the no-op meaning explicit. */
export function projectionDelivery(changed: boolean): TodoProjectionDelivery {
  return changed ? "pending" : "not_required";
}

/** Decode provider readback without letting ad-hoc strings cross the boundary. */
export function parseProjectionDelivery(value: unknown): TodoProjectionDelivery {
  if (typeof value === "string" && PROJECTION_DELIVERY_VALUES.has(value as TodoProjectionDelivery)) {
    return value as TodoProjectionDelivery;
  }
  throw new Error(`projection_delivery is unsupported: ${String(value)}`);
}

export function isProjectionDelivery(value: unknown): value is TodoProjectionDelivery {
  return typeof value === "string" && PROJECTION_DELIVERY_VALUES.has(value as TodoProjectionDelivery);
}

/** Host attests durable file readback; the provider owns revision comparison.
 * Confirmation describes one observed head, never a lock on future commits. */
export interface ProjectionReadback {
  provider_revision: string;
  changed: boolean;
}

export function decodeProjectionReadback(value: unknown): ProjectionReadback {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("projection_readback must be an object");
  }
  const row = value as Record<string, unknown>;
  if (Object.keys(row).length !== 2 || typeof row.provider_revision !== "string" ||
      !row.provider_revision.trim() || row.provider_revision !== row.provider_revision.trim() ||
      typeof row.changed !== "boolean") throw new TypeError("invalid projection_readback");
  return {provider_revision: row.provider_revision, changed: row.changed};
}

export function confirmProjectionReadback(readback: ProjectionReadback, observedRevision: string) {
  return {
    provider_revision: readback.provider_revision,
    observed_provider_revision: observedRevision,
    status: readback.provider_revision === observedRevision
      ? (readback.changed ? "delivered" : "current") : "pending",
  } satisfies {provider_revision: string; observed_provider_revision: string; status: TodoProjectionDelivery};
}
