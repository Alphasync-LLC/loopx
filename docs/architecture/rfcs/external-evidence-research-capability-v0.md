# RFC: External Evidence Research Capability v0

- Status: Draft implementation slice
- Scope: provider-neutral research planning, provenance admission, projection,
  and retirement
- Roadmap: S8 capabilities and domain integration
- Language note: the Chinese version is a semantic mirror; drift is a defect.

## Problem

LoopX currently has useful but separate pieces: host research methods,
connector inventory, provider lifecycle, managed Turn contracts, and downstream
evidence consumers. A registry row can say `supported` without proving that the
provider is installed, enabled, ready, called, or accepted. Conversely, a host
research method can produce good evidence without a typed receipt that other
LoopX callers can inspect.

The product needs one outcome capability, not a generic connector executor:
turn a decision-bound research question into compact evidence whose provenance,
admission, use, and retirement are observable.

## Decision

Add capability `external-evidence-research` with protocol
`external_evidence_research_v0` and lifecycle:

`discover → select → provider execute → provenance receipt → parent admit/reject → downstream projection → retire`.

The request must name object, user activity, decision, evidence kinds, and
constraints. A provider is selectable only when current readback says all four
of `declared`, `installed`, `enabled`, and `ready`. Provider kinds are `method`
and `connector`; their execution remains with their existing owner.

The receipt binds the exact request and selected provider. Each admitted source
has a direct non-file reference, source family, evidence basis (`stated`,
`observed`, `tested`, or `inferred`), finding, limitation, relevant dates, and a
content digest. Raw provider content is never part of the Core projection.

The parent agent explicitly admits or rejects evidence. Rejection can retire;
admission remains retained until downstream readback covers every admitted
source reference.

## Ownership and TypeScript migration

This slice follows the TypeScript migration RFC without claiming a whole
control-plane promotion. TypeScript owns the pure typed decisions and is exposed
through the existing effect runtime. Python owns only CLI parsing, local JSON
input, and transport. The PR deletes no active connector path and creates no
second persisted authority.

Connector registry remains inventory and telemetry. `supported` never maps to
`ready=true`; explicit provider lifecycle observation may override the
inventory-only row for the same provider id.

## Product surfaces

- CLI: `external-evidence plan|admit|retire`.
- Managed Turn: the same three effect-runtime methods.
- Frontend/Lark: not changed in this Core slice. A companion slice should render
  the same typed plan/admission projection and readback; it must not invent a
  second registry or lifecycle.

## Acceptance

- inventory-only connectors cannot be selected;
- method and connector providers use one protocol and receipt contract;
- stale request/provider identity, file provenance, and unsupported evidence
  basis fail closed;
- admitted source refs are a subset of receipt sources;
- retirement waits for downstream coverage of every admitted source;
- CLI and effect-runtime TypeScript tests pass from the source checkout.

## Non-goals

- a universal browser/search engine;
- provider credential storage;
- raw page or transcript persistence;
- automatic evidence admission;
- trading, publishing, or other downstream effect authority;
- treating registration or usage counters as proof of evidence quality.
