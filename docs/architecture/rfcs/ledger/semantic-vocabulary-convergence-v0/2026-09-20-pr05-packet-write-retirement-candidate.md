# PR-05: candidate retirement of protocol action packet writes

Candidate migration contract for [PR #4794](https://github.com/huangruiteng/loopx/pull/4794),
Refs [#4447](https://github.com/huangruiteng/loopx/issues/4447). This entry does
not approve a release or close the tracker. The
[protocol decision](../../../../reference/protocols/protocol-action-packet-decision-v0.md)
owns the concrete migration and qualification requirements.

- **Gap and delivered change.** Public references still required direct packet
  consumption and retention in every full decision. Five references now
  distinguish that historical v0 contract from candidate packet-free new
  quota/live/paused/recovery outputs. Current consumers use typed interaction,
  lane, and scheduler contracts; no new capability, flag, or authority is added.
- **Retained boundary.** Preserve historical packet readers, opaque summaries,
  residues, `protocol_action_packet_fields`, the historical summary renderer,
  and signature validation without rewriting old records. A new source may
  lack the capsule's packet witness; source/envelope agreement does not promise
  the same hash as an older packet-bearing source.
- **Evidence limit.** PR #4794's synthetic absent/v0/opaque/residue fixtures
  exercise named Python/TypeScript readers and authority checks. They do not
  qualify complete historical archives, unknown external consumers, or rollback
  to the current 1.1.0 reader. Runtime writer removal and producer/display smoke
  updates belong to the accompanying implementation, not this documentation
  slice; its integration must establish actual packet-free output behavior.
- **Documentation-slice validation.** Documentation governance and 29 focused
  Python plus five TypeScript compatibility tests pass. The existing protocol
  decision smoke fails its old wording assertion and also needs its old section
  ordering updated with the implementation. The 1.1.0 downgrade is untested here.
- **Release and rollback still pending.** The user/maintainer must bind the
  public output version marker and historical-support window before release.
  No date or support duration is promised. Test the 1.1.0 reader against new
  outputs and retained history before claiming downgrade compatibility;
  reverting the producer does not prove that compatibility.
- **Bounded follow-through.** Replace smokes that require the old “Keep” and
  default-full-payload claims with checks of the migration boundary. Retaining
  the existing semantic projection and historical read seam is sufficient for
  this slice; no new compatibility framework is needed.
