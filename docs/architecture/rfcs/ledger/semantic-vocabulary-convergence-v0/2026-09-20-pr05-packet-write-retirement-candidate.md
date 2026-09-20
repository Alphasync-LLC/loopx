# PR-05: candidate retirement of protocol action packet writes

Refs [#4794](https://github.com/loopx-project/loopx/pull/4794),
[#4447](https://github.com/loopx-project/loopx/issues/4447). The
[protocol decision](../../../../reference/protocols/protocol-action-packet-decision-v0.md)
owns the migration contract. Release binding and history-support scope remain
pending; this entry neither grants migration approval nor closes the tracker.

- **Delivered delta.** Six live writes across four quota modules are removed,
  together with the unused packet builder and its imports. Ordinary, paused,
  required-read, capability-intent and host-recovery construction use existing
  typed contracts. The default full decision now omits the legacy field, not
  merely the compact view. No new flag, schema vocabulary or authority owner.
- **Retained responsibility.** Historical Python Markdown and TypeScript
  Effect/Envelope readers, ordered `protocol_action_packet_fields`, summary
  reconstruction, opaque fallback, residue and signature rejection remain.
  Historical records are never rewritten. The measured Python field surface
  falls from 5 to 1; TypeScript remains 2. The same-diff anchors retain those
  compatibility readers instead of pretending the field disappeared globally.
- **Behavior evidence.** Eight complete baseline/candidate quota payloads match
  after removing only the packet; canonical signature documents match after
  removing only its capsule witness. The digest may consequently change.
  Real CLI/reentry/Envelope/live tests pass (149). The renamed
  `quota-without-legacy-packet-smoke.py` rejects the previous default. The obsolete
  decision-note wording smoke is removed; runtime and compatibility regressions
  own behavior evidence, while docs governance checks document structure.
- **Versioned readback.** Actual v1.1.0 source (`607c11d75`) reads eight new and
  eight packet-bearing baseline samples with unchanged signed actions and valid
  host admission. Installed candidate wheel checks ordinary/paused output,
  bundled TS/JSON resources, real bridge and host admission. This is bounded
  synthetic evidence, not full historical archive or all-host qualification.
- **Remaining decisions.** Confirm the output release, supported historical
  formats/window, external consumer coverage and rollback commitment before
  release. Unknown external readers are not presumed compatible. Keep review
  status distinct from a passing test suite and reconcile overlapping
  quota-construction PRs on the actual integrated revision.
