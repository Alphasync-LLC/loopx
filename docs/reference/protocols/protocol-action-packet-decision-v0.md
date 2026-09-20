# Protocol Action Packet Decision v0

## Historical v0 Contract

`protocol_action_packet_v0` was the deterministic hot-path summary emitted by
`quota should-run`. Full decisions retained the packet, and TurnEnvelope
compacted its summary only after field-level reconstruction parity. The summary
encoded actor, user/agent action requirements, quiet-noop allowance, work lane,
and a compact action label with `llm=no_api`. It was an observation, never an
execution or permission authority.

The router comparison and Codex CLI wrapper experiments evaluated that summary.
Their results do not establish compatibility for removing it from public output.

## Candidate PR-05 Migration

PR-05 proposes the following behavior for the next release window. The public
output version marker and historical-reader support window remain for the
user/maintainer to bind before release; no release date, support duration, or
approved cutover is declared here.

- New quota decisions, including live, paused, and recovery outputs, omit
  `protocol_action_packet`, including the full-decision cold path. This changes
  the default payload, independently of the opt-in TurnEnvelope view.
- Current consumers use typed contracts: `interaction_contract` for user/agent
  obligations and executable CLI actions, `work_lane_contract` for lane duties,
  and `scheduler_hint` for cadence. Removing the summary does not change
  delivery, spending, permission, scheduler, or settlement rules.
- Keep historical v0 packet readers, ordered semantic-field projection
  `protocol_action_packet_fields`, and the summary renderer used for historical
  compatibility. Read stored packets and envelopes without rewriting their
  records, summaries, residues, or signatures. Do not regenerate an opaque
  summary from current action text or let a historical summary override it.
- Preserve TurnEnvelope's verified reconstruction, field-level `residue`, and
  `unverified_retain_summary` paths. A source without a packet has no packet
  witness in `contract_capsule`; the semantic action fields remain signed.
  Its source signature document and envelope signature document must agree.
  Omitting `contract_capsule.protocol_action_packet` can change the digest
  compared with a packet-bearing source: this is not a hash-compatibility
  promise and does not permit weakening signature validation.

## Qualification and Rollback

The compatibility fixtures in `tests/test_turn_envelope.py` and
`tests/control_plane_ts/protocol_action_packet_compat.test.ts` cover absent,
synthetic historical v0, opaque, and residue cases through named readers. They
also exercise signature and authority boundaries. These fixtures are not a
complete historical archive replay or evidence about every possible reader.

Before release, qualify actual new quota/live/paused/recovery outputs and their
CLI, TurnEnvelope, host, and display consumers. Verify typed action, gate,
spend, and scheduler behavior with the packet absent; historical records must
remain unchanged and signature tampering must still fail closed. Reconcile
smokes that assert packet presence or the former default-payload wording.

Rollback to the current 1.1.0 reader requires an actual test against candidate
outputs and retained historical records. Record the reader version, tested
cases, and failures before calling rollback compatible. Until that passes, a
reader downgrade is unqualified; reverting the producer change is the code
rollback, not proof that the older reader accepts intervening outputs. Unknown
external consumers that require the packet need their own migration or
qualification and must not be assumed compatible.

## Operating Boundary

Routine quota/status/heartbeat routing stays deterministic and should not call
Codex CLI, direct LLM APIs, runner adapters, or paid compute for this migration.
Cold-path summarizer experiments remain explicit, isolated, and sidecar-only;
they must not persist raw stderr, private session traces, or credentials.
PR-05 neither introduces a CLI flag nor closes #4447. Release binding, rollback
qualification, and historical-support acceptance remain separate from this
candidate contract.
