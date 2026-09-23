# Goal Instance Identity and Orphan Recovery (v0)

- **RFC status:** Draft
- **Delivery maturity:** Proposal
- **Authors / owners:** LoopX contributors
- **Created:** 2026-09-23
- **Last normative revision:** 2026-09-23
- **Implementation baseline:** `d3dc4083c9c73911addeae8c0643640f0046874b`
- **Related contracts:** [Issue #4801](https://github.com/loopx-project/loopx/issues/4801), [orphan fence slice #4808](https://github.com/loopx-project/loopx/pull/4808)
- **Language mirror:** [Chinese semantic mirror](goal-instance-identity-and-orphan-recovery-v0.zh-CN.md)

## Document map and maintenance contract

Sections 1-10 are the durable design and acceptance contract. Section 11 is
the normative delivery plan. Section 12 contains unresolved decisions;
recommendations there are not approval. Appendices are non-normative evidence
and decision history.

The English and Chinese documents are semantic mirrors. Any normative change
must update both in the same pull request.

---

## 1. Decision summary

This RFC makes five linked decisions:

1. `goal_id` remains the human-readable alias. A project-registry-owned,
   immutable `goal_instance_id` identifies one Goal lifetime.
2. Every durable host, session, channel, automation, Turn, and quota binding
   carries the exact pair. The source project registry, not a global
   projection or a binding store, authorizes execution.
3. Instance identity is enabled only in a strict project-registry envelope
   that released legacy binaries cannot decode as a registry. This is the
   mechanical mixed-writer gate.
4. Orphan recovery is one preview-first, journaled lifecycle operation with
   explicit per-candidate `adopt`, `migrate`, `archive`, or `delete`
   dispositions. It never guesses or merges.
5. Legacy registries and bindings remain inspectable and migratable. In the
   final enforcement release they are read-only: they cannot activate a host,
   resume a session, deliver a channel event, wake automation, mutate Goal
   state, or spend quota.

The existing state-file locations, host-specific runtime directory layouts,
provider revision domains, leases, and global registry role do not become new
Goal authorities. This RFC does not approve automatic cleanup of every
external provider, automatic candidate selection, or direct mutation of
orphan state by ordinary bootstrap.

## 2. Problem and motivation

Today one `goal_id` serves as both a display name and a durable identity. A
Goal can disappear from the project registry while active-state files,
sessions, host bindings, Goal Channels, and heartbeat automations survive.
Creating a new Goal with the same `goal_id` can make those old records appear
current. This is an ABA failure:

1. Goal A named `release` creates durable attachments.
2. Goal A is removed, but some attachments remain.
3. Goal B is created with the same name.
4. An attachment that only stores `release` cannot distinguish A from B.

The fence shipped by #4808 correctly blocks guided bootstrap when a registry
entry is absent but a project state candidate remains. It does not distinguish
Goal lifetimes, resolve the orphan, or invalidate attachments after
delete-and-recreate.

No individual host or session store can solve this locally. If a host invents
identity, it becomes a second Goal authority. If deletion synchronously knows
every provider, it becomes a cross-owner distributed cleanup transaction.
LoopX instead needs one authority-bearing identity and a final source-registry
check at every effect boundary.

### Invariants

1. The source project registry is the only authority that creates or resolves
   a Goal instance.
2. A new Goal after terminal removal receives a fresh random instance ID,
   including when its `goal_id`, path, objective, or configuration is reused.
3. Updating configuration, reconnecting a provider, renewing a lease, opening
   a Turn, or rewriting a binding never rotates the instance ID.
4. A stale, missing, malformed, or legacy binding cannot authorize execution
   for an instance-aware Goal.
5. A stale global projection may route a lookup but cannot authorize a write.
6. An incomplete orphan-resolution journal blocks every Goal activation and
   mutation, including after a project Goal record has been published.
7. Resolution leaves exactly one selected writable state authority or leaves
   the Goal absent with no writable candidate.
8. Destructive resolution requires a verified targeted backup, exact plan
   digest, explicit Goal confirmation, and post-write readback.
9. Crash retry reuses the prepared instance ID and provider idempotency keys.
10. A released old writer cannot silently open or rewrite an instance-aware
    project registry.

## 3. Scope and non-goals

### In scope

- Project-registry Goal lifetime identity and exact binding comparison.
- A registry-wide compatibility boundary for old readers and writers.
- Instance propagation through first-party durable binding owners.
- Final checks at activation, resume, delivery, state mutation, and quota
  authorization.
- Preview, backup, apply, resume, and rollback for project-local orphan state.
- Diagnostics for orphan state, legacy identity, stale bindings, stale global
  projections, incomplete journals, and manual cleanup.
- A staged migration that separates observation from enforcement.

### Non-goals

- Changing the human-facing `goal_id` or placing instance IDs in state paths.
- Migrating low-level Codex, Pi, OpenCode, or other host runtime directories.
- Merging multiple active-state candidates.
- Treating timestamps, paths, content equality, global projections, or host
  records as identity evidence.
- Making physical deletion from an external provider the safety boundary.
- Introducing a public generic binding-provider framework.
- Changing Claim, Lease, authority revision, Turn, or provider idempotency
  semantics beyond binding them to a Goal instance.
- Allowing an old binary to downgrade or edit a strict registry.

## 4. Current-system contract

These are implementation facts at the named baseline, not proposed behavior:

- `loopx/bootstrap.py` builds and merges Goal records by `id`. A forced merge
  may replace the full Goal record.
- `loopx/registry.py` and `loopx/history.py` accept any JSON object as a
  registry. They do not reject an unknown `schema_version`.
- The project registry is normally `.loopx/registry.json`; global registry
  entries carry `source_registry` and are synchronized projections.
- `loopx/control_plane/goals/orphaned_goal_state.py` discovers current and
  legacy state candidates and supplies the #4808 read-side bootstrap fence.
- `loopx/state_backup.py` owns the existing backup format and verification
  mechanics.
- Goal deletion and host/session/channel data have separate owners. Deleting a
  registry Goal does not prove every attachment was physically removed.
- Current Goal attachments generally bind by `goal_id`, path, session ID, or a
  store-specific revision. None identifies one same-name Goal lifetime.
- The current registry loader's permissive object decoding means an additive
  capability field or warning cannot stop a released old binary from writing.

This RFC therefore treats mixed-writer exclusion as a storage-format
requirement, not a diagnostic recommendation.

## 5. Proposed architecture

### 5.1 Ownership and authority

The source project registry owns Goal identity. It mints a
`goal_instance_id` only while holding the existing registry mutation lock and
only when it commits a fresh Goal record. The global registry copies that
identity and remains a routing projection.

`loopx/control_plane/goals/identity.py` owns pure parsing and comparison. It
cannot mint or persist an ID. Current storage owners persist and validate their
own bindings. `orphaned_goal_state.py` remains read-only discovery and fence
logic. The new
`loopx/control_plane/goals/orphaned_goal_state_resolution.py` owns resolution
policy, journaling, recovery, and receipts while delegating file backup,
registry mutation, and owner-local cleanup to existing owners.

No binding record, host state, timestamp, state-file path, or global registry
entry may create, infer, repair, or override Goal identity.

### 5.2 Goal identity model

`goal_instance_id` is opaque, immutable, public-safe, and not a credential. Its
canonical form is `ginst_` followed by 32 lowercase hexadecimal characters,
providing 128 random bits.

```python
from dataclasses import dataclass
from typing import Literal, NewType

GoalId = NewType("GoalId", str)
GoalInstanceId = NewType("GoalInstanceId", str)


@dataclass(frozen=True, slots=True)
class GoalRef:
    goal_id: GoalId
    goal_instance_id: GoalInstanceId


@dataclass(frozen=True, slots=True)
class LegacyGoalRef:
    goal_id: GoalId


RegisteredGoalRef = GoalRef | LegacyGoalRef


@dataclass(frozen=True, slots=True)
class BindingMatch:
    decision: Literal[
        "current",
        "legacy_read_only",
        "missing_goal_instance_id",
        "goal_instance_mismatch",
        "goal_not_registered",
        "resolution_in_progress",
        "invalid",
    ]
```

An instance-aware Goal record contains:

```json
{
  "id": "release-2026",
  "goal_instance_id": "ginst_6ff38d6d143d4b72a6ff894b95f067c1",
  "status": "active",
  "repo": "/project",
  "state_file": ".codex/goals/release-2026/ACTIVE_GOAL_STATE.md"
}
```

The absolute path above is illustrative, not public evidence. Stored paths
continue to follow existing privacy and portability rules.

Every durable attachment stores:

```json
{
  "goal_id": "release-2026",
  "goal_instance_id": "ginst_6ff38d6d143d4b72a6ff894b95f067c1"
}
```

The matching matrix is exhaustive:

| Registry state | Binding state | Read-only inspection | Execution or mutation |
| --- | --- | ---: | ---: |
| Exact instance | Exact same instance | allow | allow after final source check |
| Exact instance | Missing instance | allow with finding | reject |
| Exact instance | Different instance | allow with finding | reject |
| Legacy Goal | Legacy binding | allow with finding | reject in enforcement release |
| Legacy Goal | Instance binding | allow with finding | reject |
| Goal absent | Any binding | allow as historical | reject |
| Resolution incomplete | Any binding | allow with finding | reject |
| Invalid record | Any | fail closed | reject |

An earlier observation release may report legacy execution without blocking it,
but it cannot claim the ABA invariant. The enforcement release has no
`legacy_compatible` execution branch.

### 5.3 Identity independence

The following revision domains remain independent:

| Event or identity | Rotates `goal_instance_id`? | Reason |
| --- | ---: | --- |
| Fresh creation after terminal retirement | yes | Starts a new Goal lifetime |
| Orphan `adopt` or `migrate` that creates a Goal | yes | Establishes a new authority |
| Forced bootstrap or configuration update | no | Changes configuration within one lifetime |
| Provider reconnect or provider revision | no | Changes an attachment or backend generation |
| Authority revision or migration receipt | no | Versions authority state, not Goal existence |
| Claim or Lease epoch | no | Coordinates work inside one lifetime |
| New Turn or session | no | Creates execution lineage within one lifetime |
| Binding revision | no | Versions one owner's attachment record |
| Global registry synchronization | no | Copies a source-owned identity |
| Rollback to orphaned bytes | never restores one | Restored bytes have no execution authority |

`--force` cannot replace an instance ID. Imports into a new project authority
mint a new identity rather than copying an identity owned by another registry.

### 5.4 Strict registry envelope and mixed-writer gate

Instance identity is activated per project registry, not per Goal. The
activated registry keeps the same path but changes from the legacy JSON-object
root to a strict two-element JSON-array envelope:

```json
[
  {
    "schema_version": "loopx_project_registry_envelope_v1",
    "minimum_writer_protocol": "goal_instance_v1",
    "payload_sha256": "sha256:..."
  },
  {
    "schema_version": "0.1",
    "goals": []
  }
]
```

This shape is intentionally incompatible with released legacy loaders, which
require the JSON root to be an object. They fail before selecting a Goal or
performing a registry-backed mutation. An additive object field is forbidden
because old code would ignore it.

New code opens both formats through one registry codec:

```python
@dataclass(frozen=True, slots=True)
class OpenedProjectRegistry:
    format: Literal["legacy_object_v0", "strict_envelope_v1"]
    payload: dict[str, object]
    writer_protocol: str | None
    payload_sha256: str


def open_project_registry(path: Path) -> OpenedProjectRegistry: ...


def mutate_project_registry(
    path: Path,
    operation: str,
    reducer: Callable[[OpenedProjectRegistry], ProjectRegistryMutation],
) -> ProjectRegistryReceipt: ...
```

The transaction API preserves the envelope, validates the payload digest, and
owns atomic writeback. Direct project-registry writes are forbidden after M0.
A repository check maintains an exhaustive list of project-registry writers
and fails when a new bypass appears.

Activation is preview-first and registry-wide:

```console
loopx activate-goal-instance-identity --project . --format json

loopx activate-goal-instance-identity \
  --project . \
  --execute \
  --plan-revision sha256:31ab... \
  --confirm-registry-path .loopx/registry.json
```

The apply operation requires:

1. no active host, session, automation, or Goal mutation lease for any Goal in
   the registry;
2. a verified backup of the legacy object and affected local bindings;
3. all installed first-party hosts to advertise `goal_instance_v1`;
4. every current Goal to receive one freshly minted instance ID in the same
   atomic envelope write;
5. all legacy bindings to become non-executable until explicitly re-created;
6. readback through the new codec and a black-box rejection check against the
   oldest supported released writer.

A newly created empty project may start directly with the strict envelope. An
existing legacy registry cannot mint any instance ID until registry-wide
activation succeeds. `adopt` or `migrate` on an orphan may activate an empty
legacy registry in the same prepared transaction. If other legacy Goals exist,
the operation blocks and requires registry-wide activation first.

The global registry remains an object projection because it is not an
execution authority. Old global writers can at worst make the projection stale;
all executable paths re-read the strict source registry. Status reports the
stale projection and a current writer repairs it.

Deleting the strict registry file, extracting its payload into a legacy object,
or editing around the envelope is unsupported manual corruption. The threat
model prevents accidental mixed-version first-party writes, not deliberate
filesystem tampering by the same operating-system principal.

### 5.5 Binding owners and final checks

The first implementation uses a private exhaustive owner table. It is not a
public plugin interface:

| Owner | Durable binding | Required final check |
| --- | --- | --- |
| Project registry | session and thread bindings | before returning a resumable route |
| Attached host | activation and lock identity | before lock or execution request |
| Chat store | Goal session and upstream thread | before create, direct resume, or latest lookup |
| Turn driver | lineage and host session digest | before queue and settlement |
| Pi and OpenCode | local authority/binding record | before host action and quota call |
| Goal Channel / Lark | channel binding and connection | before inbound or outbound delivery |
| Heartbeat automation | installed command and parsed inventory | before wake and quota call |
| Scheduler and quota | executable hint and spend request | before Todo selection and spend |

Each inventory row contains a stable owner revision:

```python
@dataclass(frozen=True, slots=True)
class BindingObservation:
    owner: str
    locator: str
    binding_revision: str
    content_sha256: str
    observed_goal_ref: GoalRef | LegacyGoalRef | None
    cleanup_mode: Literal["local_idempotent", "external_unverified", "none"]
```

The complete sorted inventory and each `binding_revision` enter migration and
orphan-resolution plan digests. Adding a first-party durable owner requires
updating the owner table and its exhaustiveness test.

All executable paths follow the same order:

1. Resolve a route, possibly through the global registry.
2. Open the source project registry through the strict codec.
3. Reject a legacy Goal or incomplete resolution journal.
4. Compare the exact registered and supplied `GoalRef`.
5. Revalidate immediately before the first effect at that boundary.
6. Only then create a lock, return a resumable record, deliver, write, or spend.

A check at host activation does not replace the check at state writeback or
quota spend. Long-lived processes may outlive deletion and recreation.

### 5.6 Orphan resolution command

The command is a dry run unless `--execute` is present. Every discovered
candidate requires one explicit disposition:

```console
loopx resolve-orphaned-goal-state \
  --project . \
  --goal-id release-2026 \
  --disposition .codex/goals/release-2026/ACTIVE_GOAL_STATE.md=adopt \
  --disposition .claude/goals/release-2026/ACTIVE_GOAL_STATE.md=archive \
  --objective "Ship the release" \
  --domain engineering \
  --role owner \
  --format json
```

- `adopt` keeps one selected candidate at its already canonical location and
  registers it under a fresh Goal instance.
- `migrate` moves one selected candidate through the canonical state-path
  helper, under the same human Goal ID, then registers a fresh instance.
- `archive` moves a candidate outside every active Goal root.
- `delete` removes a candidate only after targeted backup verification.

At most one candidate may be `adopt` or `migrate`. All other candidates must be
`archive` or `delete`. An archive/delete-only plan leaves the Goal absent.
There is no implicit winner, content merge, arbitrary destination path, or
renamed target Goal.

Preview validates before computing its digest:

- the project and registry resolve inside their declared authority boundary;
- each candidate is a readable regular file inside an allowed Goal root;
- no candidate or parent is a symlink;
- resolved paths do not escape, alias, or duplicate one another;
- the requested Goal is absent from the project registry;
- no other resolution exists for the Goal;
- every candidate tree digest and binding-owner revision is stable;
- the migration destination is selected by the canonical path helper;
- the Goal creation specification is complete when required.

Execution must bind the preview and human intent:

```console
loopx resolve-orphaned-goal-state \
  --project . \
  --goal-id release-2026 \
  --disposition .codex/goals/release-2026/ACTIVE_GOAL_STATE.md=adopt \
  --disposition .claude/goals/release-2026/ACTIVE_GOAL_STATE.md=archive \
  --objective "Ship the release" \
  --domain engineering \
  --role owner \
  --execute \
  --plan-revision sha256:82e3... \
  --confirm-goal-id release-2026
```

### 5.7 Resolution transaction and journal

The journal lives under
`.loopx/lifecycle/orphaned-goal-state/<goal-id>/<plan-revision>.json`. It is
lifecycle metadata, not another Goal registry.

The apply transaction:

1. Acquires lifecycle, registry, and affected owner locks in one documented
   order.
2. Returns the existing complete receipt for an exact replay.
3. Rebuilds the plan and requires the same registry, candidate, owner, Goal
   specification, and plan digests.
4. Writes and verifies one targeted backup through `state_backup.py`.
5. If a Goal will be created, mints its instance ID and durably writes it to a
   `prepared` journal before the first candidate mutation.
6. Applies candidate dispositions idempotently, recording each step. Archive
   destinations include the plan revision.
7. Publishes the project Goal only after the selected candidate reaches its
   canonical final route and all competing candidates are inactive.
8. Requests owner-local revocation using the exact retired
   `(goal_id, goal_instance_id)` selector and stable idempotency keys.
9. Synchronizes the project record to the global projection.
10. Reads back every candidate, owner receipt, registry, global projection,
    backup proof, and final orphan fence before marking the journal complete.

A prepared or incomplete journal blocks all activation and mutation even if
step 7 already published the project Goal. Retry reuses the journaled instance
ID, resolution ID, owner selectors, and provider idempotency keys.

The completion receipt includes:

- plan revision, resolution ID, and terminal journal digest;
- each pre- and post-operation candidate digest;
- source project registry digest and exact Goal reference;
- global projection result and digest, or a typed pending-sync finding;
- backup path-independent manifest digest and verification proof;
- every binding-owner observation, revision, cleanup request, and readback;
- every local removal receipt;
- each external `manual_cleanup_required` finding;
- final orphan and in-progress fence results.

### 5.8 Logical revocation and owner cleanup

Exact instance mismatch is the safety boundary. Resolution does not depend on
physical deletion from every store.

The revocation selector is always the full retired pair:

```python
@dataclass(frozen=True, slots=True)
class RevocationSelector:
    goal_id: GoalId
    retired_goal_instance_id: GoalInstanceId
```

Goal-ID-only cleanup is forbidden because it can delete a newly created
instance. Local owners that support idempotent removal must return a receipt
before resolution completes. An external provider without verifiable deletion
remains logically inert and yields `manual_cleanup_required`; this finding does
not make stale execution possible.

### 5.9 Rollback

Rollback is also preview-first and digest-bound:

```console
loopx rollback-orphaned-goal-resolution \
  --project . \
  --goal-id release-2026 \
  --resolution-id ores_... \
  --format json

loopx rollback-orphaned-goal-resolution \
  --project . \
  --goal-id release-2026 \
  --resolution-id ores_... \
  --execute \
  --plan-revision sha256:... \
  --confirm-goal-id release-2026
```

Rollback may restore verified bytes only to an orphaned, fenced state. It
never restores a retired Goal instance ID or binding authority. It is rejected
after any post-resolution Goal write, Todo mutation, quota spend, session or
channel creation, automation installation, or binding revision. A successful
rollback removes the newly created Goal through the lifecycle owner, restores
candidate bytes, verifies their digests, and makes diagnosis unhealthy with
`orphaned_goal_state`.

If rollback is no longer legal, recovery is a forward operation: finish the
journal, retire the new Goal through normal lifecycle, and create another
resolution plan.

### 5.10 Module map

| Module | Responsibility |
| --- | --- |
| `loopx/control_plane/goals/identity.py` | Goal reference types, parsers, and exhaustive match policy |
| `loopx/control_plane/projects/registry_codec.py` | Legacy object and strict envelope decoding, digest verification, format-preserving transactions |
| `loopx/bootstrap.py` | Mint only on committed fresh creation; preserve identity on update |
| `loopx/global_registry.py` | Copy identity, classify instance replacement, never mint |
| `loopx/control_plane/goals/orphaned_goal_state.py` | Candidate discovery and read-side fence |
| `loopx/control_plane/goals/orphaned_goal_state_resolution.py` | Plan, apply, journal recovery, revocation orchestration, rollback |
| `loopx/state_backup.py` | Targeted backup plan, archive, manifest, and verification |
| Existing binding owners | Persist their pair, validate it, and perform owner-local cleanup |
| `loopx/control_plane/goals/global_registry_health.py` | Typed health findings |
| `loopx/diagnose.py` | Render findings without becoming another detector or writer |
| CLI adapters | Parse arguments and render typed results only |

## 6. Alternatives and design choices

### Generation counter

A counter under `goal_id` needs a permanent tombstone after deletion or a
second global allocator. Random source-registry identity avoids both and does
not require ordered IDs.

### Instance ID in directory paths

Instance-segment paths separate files but do not identify sessions, channels,
automations, or quota calls. They also force every human-facing path consumer
through a broad migration. Record-level identity closes the reported ABA
failure without that unrelated layout change.

### Delete every binding during Goal deletion

Cross-provider deletion is not atomic and would make Goal lifecycle know every
storage implementation. Exact matching makes stale records inert. Owner-local
cleanup then improves hygiene without becoming authority.

### Add a capability field to the current registry object

Released old loaders accept unknown object fields and schema values. They
could silently rewrite an instance-aware registry. This fails the mixed-writer
invariant.

### A new registry path with a redirect object

Released old binaries could ignore the redirect, continue using the old path,
and create split authority. Keeping one path with an incompatible root shape
causes a deterministic decode failure instead.

### Automatic candidate selection or merge

Path preference, modification time, and content equality do not prove
authority. Multiple candidates may represent divergent histories. The
operator must classify every candidate.

### One module for discovery and mutation

Combining the small read-side fence with backup, journaling, cleanup, rollback,
and registry publication would mix stable detection with a large transaction.
The sibling resolution owner preserves a deep plan/apply interface without
making the fence module a lifecycle service.

## 7. Safety, privacy, and compatibility

Identity and digests are public-safe metadata, not credentials. Backups,
candidate contents, session payloads, local absolute paths, provider handles,
and raw state remain private runtime data and must not enter public receipts,
logs, fixtures, or documentation.

The strict envelope provides format-level split-brain prevention for supported
first-party binaries. Activation remains blocked until:

- all in-repository project-registry writers use the codec transaction;
- packaged Python and TypeScript surfaces pass the same writer inventory;
- every installed first-party host reports the required protocol;
- a black-box test proves the oldest supported old package rejects the strict
  fixture and leaves its bytes unchanged;
- current code proves exact read/write/readback and crash safety.

Legacy object registries remain readable for status, diagnosis, backup,
activation preview, and orphan-resolution preview. During the observation
release they may still execute with an explicit no-guarantee finding. During
the enforcement release they are read-only until activation completes.

A strict registry cannot be downgraded. Current code must emit
`unsupported_registry_writer_protocol` before mutation when it cannot satisfy
the manifest. Recovery uses a current or newer release; it never unwraps the
payload for an old writer.

Source-registry unavailability, digest mismatch, malformed envelope, missing
instance, incomplete resolution, or owner-inventory ambiguity fails closed.
Global projection unavailability may delay visibility but cannot grant
execution.

## 8. Migration and rollback

Migration has two scopes:

1. **Fresh project.** Create a strict empty envelope and mint the first Goal in
   its committed registry transaction.
2. **Existing project.** Preview registry-wide activation, quiesce every Goal,
   back up the registry and local bindings, stamp every current Goal with a new
   instance, atomically write the strict envelope, and require explicit
   reconnection of all attachments.

No existing attachment is automatically blessed. There is no evidence that an
unstamped record belongs to the current lifetime rather than a prior same-name
Goal.

The activation cutover point is the verified strict-envelope write:

- Before it, abort leaves the legacy object authoritative.
- After it, old binaries and unstamped bindings are unsupported and fail
  closed.
- If later steps fail, current code resumes the activation journal.
- Returning to legacy execution is not rollback.

Orphan archive/delete may run without identity activation because it creates no
Goal. Orphan adopt/migrate requires an already strict registry, a fresh strict
registry, or an atomic registry-wide activation admitted by the same plan.

Before resolution preparation, abort changes nothing. After preparation, retry
the same plan. The separate rollback command is legal only before any
post-resolution business write and restores orphaned, non-executable bytes.

## 9. Validation and acceptance

| Claim | Test or evidence | Required result | Boundary / exclusions |
| --- | --- | --- | --- |
| Same-name recreation is fenced | Delete A, preserve every attachment, create B with same alias, exercise all owners | Every old path rejects before effect or quota | Does not require physical provider deletion |
| Updates preserve lifetime | Force-update config, reconnect provider, renew lease, start Turn | Same instance ID in registry and new records | Does not preserve binding revisions |
| Legacy is read-only | Exercise status, backup, migration preview, activation, resume, delivery, write, spend | Reads succeed with finding; every effect rejects | Observation release is explicitly weaker |
| Old writer is mechanically denied | Run oldest supported released package against strict fixture | Non-zero typed/decode failure and byte-identical registry | Covers supported first-party package, not arbitrary scripts |
| Strict codec is exhaustive | Static writer inventory plus Python/TS conformance | No direct project-registry write bypass | Test helpers may use isolated fixtures |
| Source authority beats global projection | Make global entry stale and invoke every executable route | Source mismatch rejects | Global routing availability is separate |
| Preview is pure | Preview 1, 2, and 4 candidates | No file, registry, binding, or journal write | Read-only filesystem metadata access allowed |
| Plan binds full state | Change candidate, owner revision, registry, or Goal spec after preview | Apply rejects before backup or mutation | None |
| Path validation fails closed | Symlink, escape, duplicate path, non-regular or unreadable candidate | Preview/apply rejects | Canonical helper owns legal destination |
| Crash retry is idempotent | Crash after every journaled step | One instance ID, no duplicate archive/delete, same owner keys | External manual cleanup may remain |
| Published-but-incomplete stays fenced | Crash after project publication before global sync/completion | Activation, mutation, and quota reject | Status remains readable |
| Cleanup failure is safe | Fail one local and one external owner cleanup | Instance mismatch stays inert; journal retries local owner; external finding persists | Completion waits for required local receipts |
| Receipt is complete | Compare receipt to owner table and all readbacks | Every owner/candidate/registry/global/backup/fence row present | Raw private contents excluded |
| Backup precedes destruction | Inject failure before and after backup verification | No destruction before proof; verified restore works | Archive-only still receives targeted backup |
| Rollback is fenced | Roll back before and after a post-resolution write | Early rollback restores orphan fence; late rollback rejects | Never restores old authority |
| Diagnostics remain unhealthy | Create orphan, legacy, mismatch, stale global, and incomplete journal states | Typed findings and exact next action | Diagnosis performs no repair |

The implementation must also run existing bootstrap, registry, deletion,
session, host, Goal Channel, heartbeat, quota, backup, docs-governance, and
public-safety suites. Skipped owner rows are not acceptance.

## 10. Operational contract

The stable findings are:

- `orphaned_goal_state`
- `orphan_resolution_in_progress`
- `legacy_goal_identity`
- `goal_instance_id_missing`
- `goal_instance_mismatch`
- `goal_not_registered`
- `stale_global_goal_instance`
- `unsupported_registry_writer_protocol`
- `binding_owner_inventory_changed`
- `manual_cleanup_required`

Every rejection identifies the source registry, Goal alias, expected and
observed instance when public-safe, owner, retryability, and one lifecycle next
action. It does not expose raw state, credentials, local session content, or
provider secrets.

Status and diagnosis are read-only. They can inspect a legacy registry,
historical binding, strict envelope, and incomplete journal. They cannot stamp
identity, repair a global projection, choose a candidate, or complete cleanup.

The lifecycle retains one verified backup and one terminal receipt per
resolution according to the existing backup retention policy. An incomplete
journal is never garbage-collected automatically. Local cleanup retry is
idempotent. External manual cleanup is advisory because logical revocation
already prevents execution.

## 11. Normative delivery plan

| Milestone | Shipped behavior | Entry gate | Exit evidence | Rollback |
| --- | --- | --- | --- | --- |
| M0: registry codec and writer census | Dual-format read codec, strict format-preserving transaction, exhaustive writer inventory; no identity minting | RFC review | Current suites plus direct-writer ratchet and old-package strict-fixture rejection | Remove unused codec; all registries remain legacy objects |
| M1: observation and stamped bindings | Identity types, owner inventory, additive binding fields, diagnostics, no enforcement | M0 green | Cross-owner read/write fixtures; legacy behavior explicitly marked unprotected | Stop emitting optional binding fields |
| M2: activation and strict creation | Preview-first registry activation; fresh projects use strict envelope; IDs minted only in strict transactions | M0/M1 green; host capability census | Quiescence, backup, old-writer denial, strict readback, update-preserves-ID tests | Before envelope write only; afterward forward repair |
| M3: final enforcement | Legacy execution read-only; exact final source checks at every owner and quota boundary | Migration guidance shipped; executable caller inventory complete | ABA, stale global, long-lived process, and missing-ID rejection matrix | No downgrade; use current release and migration |
| M4: orphan resolution | Preview, targeted backup, prepared journal, candidate dispositions, owner cleanup, complete receipt | M2/M3 identity boundary | Purity, path, crash-point, cleanup, and receipt acceptance rows | Resume or digest-bound rollback to fenced orphan state |
| M5: legacy cohort migration | Registry-wide migration for existing projects and host reconnection | M2-M4 operational evidence | End-to-end multi-Goal migration and diagnostics | Before cutover abort; after cutover forward repair |

M0 must land before any code can mint `goal_instance_id`. M3 cannot claim the
ABA guarantee while any first-party executable path retains legacy fallback.
M4 may ship archive/delete before adopt/migrate, provided it does not create a
Goal or weaken the existing fence.

## 12. Open decisions

1. **Minimum supported old package.** Release owner decides before M0 exit.
   Recommendation: test the oldest version still named in the support policy,
   plus the immediately previous release. Evidence: black-box mutation matrix.
2. **Activation command naming and confirmation token.** CLI owner decides
   before M2. Recommendation: the registry-wide
   `activate-goal-instance-identity` command shown here, because the envelope
   boundary cannot honestly be per Goal.
3. **Canonical migration destination.** State-path owner decides before M4.
   Recommendation: consume the canonical helper from the host-neutral path
   work; do not accept a free-form target path.
4. **Global sync terminality.** Registry owner decides before M4.
   Recommendation: retain `local_committed` until the global projection
   readback succeeds, while source checks continue to block execution through
   the incomplete journal.
5. **Retention periods.** Operations owner decides before M4. Recommendation:
   reuse current targeted-backup retention and retain terminal receipts at
   least as long as any owner can retain a stale binding.

---

## Appendix A: Execution ledger (non-normative)

### 2026-09-23 — Design synthesis

- **Baseline:** `d3dc4083c9c73911addeae8c0643640f0046874b`
- **Delivered:** RFC proposal only.
- **Evidence:** Current registry, bootstrap, deletion, binding, orphan-fence,
  backup, global-projection, and documentation contracts were inspected.
- **Known gaps:** No runtime implementation or acceptance fixture has shipped.
- **Effect on normative design:** Initial proposal.

## Appendix B: Decision log

| Date | Decision | Owner / approval | Alternatives | Normative sections changed |
| --- | --- | --- | --- | --- |
| 2026-09-23 | Propose source-owned random Goal instance identity plus strict registry envelope | Proposal; maintainer approval pending | Counter, path identity, additive capability marker | Initial RFC |
| 2026-09-23 | Propose explicit journaled orphan resolution with owner-local cleanup | Proposal; maintainer approval pending | Automatic merge, centralized provider deletion | Initial RFC |

## Appendix C: Evidence registry

| Evidence id | Claim | Baseline / environment | Artifact or command | Result | Privacy / validity boundary |
| --- | --- | --- | --- | --- | --- |
| E1 | Current loaders accept arbitrary object schema and reject non-object roots | Named baseline | `loopx/registry.py`, `loopx/history.py`, `loopx/bootstrap.py` inspection | observed | Static current-code fact |
| E2 | The shipped fence blocks orphaned guided bootstrap but does not resolve it | Named baseline | Issue #4801 and PR #4808 | observed | Public issue and code scope |
| E3 | Global entries are source projections | Named baseline | `loopx/global_registry.py` inspection | observed | Static current-code fact |
| E4 | Strict envelope rejects the oldest supported old writer without mutation | future M0 fixture | Black-box released-package test | unverified | Required before minting |
| E5 | Every durable binding owner validates exact identity | future M1-M3 fixtures | Owner inventory conformance suite | unverified | Required before enforcement |
| E6 | Resolution is crash-safe and recoverable | future M4 fixtures | Fault-injection and restore matrix | unverified | Required before destructive use |

## Appendix D: Rejected or superseded alternatives

- A warning-only writer capability marker cannot constrain code that does not
  understand the marker.
- A redirect object leaves the old path writable and permits split authority.
- A global counter makes the projection an allocator or requires permanent
  tombstones.
- Automatic binding upgrade guesses history from an alias and is forbidden.
- Provider-wide cleanup as a commit precondition couples availability to every
  integration and still cannot prove external deletion.
- Runtime-directory migration does not solve non-file bindings and is outside
  issue #4801.

## Appendix E: Incident and review lessons

- A healthy current state does not prove continuity from an earlier same-name
  Goal.
- An advisory compatibility check is not a writer fence when old code ignores
  it.
- Crash safety requires persisting the new identity before the first candidate
  move and treating the journal itself as an execution fence.
- Cleanup and authorization are separate: stale records may remain for audit
  while exact identity matching keeps them inert.
