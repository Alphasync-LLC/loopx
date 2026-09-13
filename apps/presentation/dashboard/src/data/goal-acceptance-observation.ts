import { z } from "zod";

const nullableText = z.string().nullable();
export const goalAcceptanceObservationSchema = z.object({
  schema_version: z.literal("goal_acceptance_observation_projection_v0"),
  goal_id: z.string(),
  read_only: z.literal(true),
  acceptance_assessed: z.literal(false),
  coverage: z.enum(["partial", "unavailable"]),
  missing_sources: z.array(z.string()),
  truncated: z.boolean(),
  historical_progress: z.array(z.object({ kind: z.string(), observed_at: nullableText, source: z.string(), evidence_refs: z.array(z.string()) })),
  acceptance_gaps: z.array(z.object({
    kind: z.string(), owner: nullableText, reason: nullableText, evidence_required: nullableText, observed_at: nullableText, source: z.string(),
    reason_code: z.string().optional(), resolution_hint: z.string().optional(),
    component_checks: z.object({
      checkpoint_satisfied: z.boolean(), checkpoint_fresh: z.boolean(),
      path_outcome_valid: z.boolean(), evidence_refs_present: z.boolean(),
      final_outcome_claim_present: z.boolean(), no_reported_outcome_gap: z.boolean(),
    }).optional(),
  })),
  guards: z.array(z.object({ kind: z.string(), todo_id: nullableText, blocks_agent: nullableText, owner: nullableText, reason: nullableText, evidence_required: nullableText, decision_scope: nullableText })),
  next_action: nullableText,
  next_action_source: nullableText,
});
export type GoalAcceptanceObservation = z.infer<typeof goalAcceptanceObservationSchema>;
