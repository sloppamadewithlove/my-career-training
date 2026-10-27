# PERSIST-01 — save, recording and acknowledgement lifecycle

SCOPE INSPECTED
Full: `storage.py`. Partial: `training/recordings.py` 1–350; `bridge.py` 315–325, 734–750, 1347–1360, 1500–1566, 1820–1875, 1911–2110, 2112–2213, 2250–2262, 2278–2300, 2390–2414; `game_worker.py` 615–667, 669–800, 814–903, 946–1010, 1300–1330, 1374–1404; `reference_capture.py` 224–302; `ingame.py` 30–120; `app.py` 75–106.
Not inspected: `persist_result` and the worker's outbox writer, `thumbnail_cache.py`, `browser_images.py`, `community_plugins.py`, `plugin_session.py`, `map_guard.py`, `bootstrap.py`, and test bodies beyond grep hits. Nothing below is a test result.

LIFECYCLE TABLE (source predicates)
| Artifact | Writer / predicate | Atomicity | Bound |
|---|---|---|---|
| `career.json` | `Store.save` 147–156 | temp+fsync+`os.replace`; dir fsync non-Windows only | 32 MiB checked pre-write (150) |
| `career.last-good.json` | 154, copies prior live bytes | same `_atomic` | inherits |
| `before-import-<ns>.json` | `import_file` 171–172 | `_atomic` | none; no pruning path |
| `recordings/<uuid4>.json` | `bridge._store_recording` 2187–2189 | `Store._atomic` | `validate_recording` 24 MiB (recordings.py:96) |
| `recordings[]` index | 2190–2194 | via `_commit` 2200 | `[-100:]` |
| `attempts[]` | 2195–2199 | via `_commit` | `[-1000:]`, dedupe by `summary["id"]` |
| `outbox/<session>.json` | worker `persist_result` (not read) | unknown | 64 KiB read cap 2164 |
| `diagnostics.json` | 817–818 | `_atomic` | none |
| `bridge/state.json` | `ingame._publish_state` 61–73,116 | `_atomic` + 5 Windows retries | none |
| `candidates/<attempt>.json` + `.receipt.json` | `reference_capture` 287,300 | `_atomic_write` 224–241 | 24 MiB / marker cap |

VERIFIED BEHAVIOUR
V1 Ordering: `bridge.py:2086–2090` sets `latest_attempt`, calls `_store_recording` (file → index/attempts → `_commit`), then `_send("attempt_ack", attempt_id=summary["id"])`. `_commit` (734–736) assigns `self.document` only after `store.save` returns.
V2 Worker ack gating: `game_worker.py:973–975` requires `attempt_id == self.attempt_sent`; `reset()` refuses while `attempt_sent and not attempt_acked` (633–634); auto-reset requires `attempt_acked` (897–899); telemetry recovery has a dedicated unacked-save error (815–819).
V3 `publish_attempt` (1374–1392) returns early when `attempt_sent == summary["id"]`, and drops sample-less recordings. Callers are `game_worker.py:1319` and `1323`; both are inside the per-frame update path, so a republish for the same attempt id is suppressed by that predicate.
V4 `_store_recording` is not idempotent across deliveries: the recording always gets a fresh `uuid4` (2187) and is appended unconditionally (2190), while the summary is deduped by id (2196–2198). Two deliveries of one attempt event would produce two recording files and one attempt row.
V5 `_recordings` (2202–2213) scans only `document["recordings"][-30:]`, so playback reachability is bounded by that window regardless of files on disk.
V6 `_read_worker` (1864–1866) returns early when `self.buffer` exceeds 32 MiB without draining. The error branch does not emit `stateChanged` itself; `_read_worker`'s normal tail emits at 1875, which this early return skips. Whether a later signal (e.g. `_tick` 2278–2300, `_process_finished` 1850–1858, or a subsequent `readyReadStandardOutput`) surfaces the error is not established from the inspected code — the oversized buffer is not cleared in that branch, so subsequent reads of the same buffer repeat the early return until session cleanup/reset changes it.
V7 Unicode: paths use `Path`; JSON is written as UTF-8, with non-ASCII content preserved directly or escaped by the respective writer; `_atomic` uses `tempfile.mkstemp(dir=path.parent)` so temp and target share a filesystem; recording filenames are ASCII UUIDs.

RESEARCH FINDINGS (predicate → caller → limitation)
F1 Failed commit after recording write. Predicate: `bridge.py:2189` writes the file, `2200` commits. Caller: `_event` "attempt" branch (2086–2090) invoked from `_read_worker` (1872), whose handler (1871–1874) only sets `self.error`. If `_commit` fails before replacing the live document, no ack is sent and the new recording file is not referenced by the prior live document. A failure after replacement requires inspecting the resulting disk state rather than assuming the old state survived. Limitation: whether the worker republishes depends on V3's id predicate and on the worker still running; I do not claim the attempt is unrecoverable, only that no bridge-side retry or receipt exists on this path.
F2 Lost ack with a successful commit. Predicate: `_send` (745–750) writes to `QProcess`; ack is sent only at 2090. Caller: same branch. If the commit succeeded but the ack line is lost while the worker lives, the worker stays unacked (V2) and there is no attempt-side outbox analogous to `_ack_outbox`/`_recover_outbox` (2154–2181). Limitation: whether a `QProcess.write` can be lost while the worker is alive is unproven; the durable state is intact, so this is a liveness/recovery gap, not data loss.
F3 Buffer overflow. Predicate: 1864–1866. Caller: `readyReadStandardOutput` (1832), `_process_finished` (1852), `_drain_activity_results` (2252), `close` (2413). Effect: event processing stops for the session; the buffer is not cleared. Limitation: user-visible surfacing depends on signals I did not trace.
F4 Index/disk divergence. Predicate: trim at 2194 and the 30-entry scan at 2204; no deletion path for `recordings/*.json` in the inspected modules. This is a retention-policy question (bounded index vs unbounded files), not automatically a defect; the open question is whether unreachable-but-present files are intended.
F5 Oversize guidance. Predicate: storage.py:150–151. Caller: every `_commit`/`_save_current` (323–324, 734–736, 2409). Once the limit trips, saves fail until the document shrinks; the message names recordings, but growth can come from multiple document fields, not only recording metadata. Limitation: reachability of 32 MiB with realistic content is unproven.

BOUNDED ACCEPTANCE QUESTIONS
Q1 Attempt path, commit failure: with `Store.save` forced to raise, does the bridge leave no unreferenced recording file, and does the user get a recoverable, restart-surviving path? (F1)
Q2 Attempt path, ack loss: with one `attempt_ack` line dropped and the worker alive, is there a bounded re-ack or an explicit recoverable error, and is the attempt not duplicated? (F2, V4)
Q3 Duplicate delivery: two deliveries of one attempt event — exactly one recording file and one attempt row? (V4)
Q4 Retention: after exceeding 100 recordings and the 30-entry scan window, do index, files and playback reachability agree, and is unreachable-file retention intended? (F4, V5)
Q5 Overflow: after >32 MiB without a newline, does a later valid event get processed, or does the session fail closed with a visible stop? (F3)
Q6 Oversize save: at the 32 MiB limit, is the failure actionable and non-destructive, and does the message match the actual growth fields? (F5)

This is a source research baseline over the inspected paths, not an approval of the persistence contract and not a defect confirmation. F1–F5 are source-predicated observations with the limitations stated; Q1–Q6 are the bounded questions that would settle them. No tests were executed and no source was modified.

## Platform and backup boundaries

Store.save copies the prior live file into career.last-good.json before replacing the live file. It does not write the proposed new state into the backup. Parent-directory fsync occurs only on non-Windows systems; on those systems an error after os.replace may be reported even though the new file is already present. WindowsPath equality is case-insensitive, so changing only path letter case does not bypass the export guard. These facts narrow the failure cases above. No tests were executed for this source report; existing-test execution is tracked separately.
