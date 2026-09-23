# Replan history decision owner

Goal/source: overall roadmap #4574, typed control-plane T3 consumer ownership.
The observed gap was independent Python history scans with different retry,
ACK, neutral-accounting and lane semantics. The delivered boundary is one
`work_item.replan_history.project` request, with in-process reuse of the existing
Todo resume planner. Python keeps legacy codecs and public obligation rendering;
its replaced historical trigger scans and duplicated neutral vocabulary are removed.

Four independently specified regression cases failed on baseline `709734cd6`:
periodic retry overcount, Monitor retry overcount, accepted ACK not resetting
progress repetition, and neutral accounting breaking equivalent progress. The
new owner corrects them while retaining thresholds, precedence and obligation
identity. Typed negative cases and the 280-row multi-agent interleaving fixture
cover scope-before-ACK, retries, missing identities, invalid input and source
immutability. Real File/SQLite consumer tests delete the display before reading
status and invoking quota, rather than substituting an in-memory store.

A read-only local-source rehearsal covered 345 active Todos, 600 history rows
and five agent lanes: all five historical projections matched baseline; isolated
File/SQLite readback and public quota CLI passed without changing the source.
This was an active read-model snapshot, not whole-Goal promotion. Complete source
capture independently rejected an archived dependency with missing/incompatible
role/task-class facts. That migration hold remains and was not bypassed or repaired
in active state.

This closes the history-trigger decision family, not all T3 or default adoption.
Progress fingerprint codecs, obligation assembly, frontier settlement and broader
capture/provider qualification retain their owners. No new model observer,
provider selection, frontend configuration or optional capability is introduced.
