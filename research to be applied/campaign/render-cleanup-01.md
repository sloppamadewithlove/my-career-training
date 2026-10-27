# RENDER-CLEANUP-01 — clear queue progress during RLBot Core shutdown

## Finding

Pinned RLBot Core `11d5d863ec2f8b2647741cff22a2c59c6b6ad08e` limits direct render clears to 1,024 per game-message clump. Normal processing resets `Rendering._numClears` at the start of each clump, under the same `_context` lock used for rendering and cleanup. `BridgeHandler.Cleanup` also holds that lock while it runs `ClearAllRenders()` and loops on `SendRenderClears()`.

The source exposes a conditional no-progress case: if `ClearAllRenders()` leaves IDs in `_renderClearQueue` after `_numClears` reaches 1,024, the next `SendRenderClears()` cannot dequeue any. Cleanup then waits for `TcpMessenger.WaitForAnyMessageAsync()` and, on success, resets only the messenger byte counter. It does not reset `Rendering._numClears`. Since cleanup retains `_context`, the normal game-clump path cannot acquire the lock to run its `ResetClearCount()` call. No second call site that resets this `Rendering` instance appears in the inspected pinned Core files.

This is a static liveness concern under that queue/counter precondition, not proof of a game or server hang. Whether the condition occurs in a particular shutdown, how `WaitForAnyMessageAsync()` handles queued/socket messages, and whether it eventually returns `false` depend on the `Bridge.TCP` implementation and runtime state. The inspected public Core README identifies `Bridge.dll` as closed source. The cleanup loop itself says it is intended to wait until all clears are sent or Rocket League closes; source does not establish that every runtime path reaches that exit.

## Exact path and progress condition

| Stage | Pinned behavior | Consequence |
|---|---|---|
| Normal tick/clump | `BridgeHandler.HandleServer` reads a clump, takes `lock (_context)`, resets the messenger byte counter and `RenderingMgmt.ResetClearCount()`, then updates/render state. It calls `SendRenderClears()` before releasing the lock (`BridgeHandler.cs:63–83, 186–187`). | The 1,024-clear budget is replenished per clump, not by elapsed time alone. The nearby comment says a clump is only an approximation of a rendered frame. |
| Queueing | `ClearRender` removes an ID immediately and increments `_numClears` while below 1,024; once at the limit it enqueues IDs for a later tick (`Rendering.cs:226–242`). `ClearAllRenders` flushes persistent debug lines, visits all tracked items, and then clears its tracker (`:200–224`). | If clears exceed the remaining budget, the excess becomes `_renderClearQueue`. Clearing the tracker does not discard that pending queue. |
| Drain call | `SendRenderClears` dequeues only while both the queue is nonempty and `_numClears < 1024`; it then sends the command queue and returns whether the clear queue is empty (`Rendering.cs:244–256`). | Once `_numClears` is 1,024, repeated calls cannot drain additional IDs unless the counter is reset elsewhere. |
| Handler cleanup | The `finally` path calls `BridgeHandler.Cleanup`. That method takes `lock (_context)`, calls `ClearAllRenders()`, and loops while `SendRenderClears()` reports pending work (`BridgeHandler.cs:191–225`). | Cleanup excludes both normal clump processing and bridge-message handling while it waits. |
| Wait between drain attempts | When `SendRenderClears()` returns `false`, cleanup blocks on `messenger.WaitForAnyMessageAsync().Result`; `false` breaks the loop, while `true` is followed only by `messenger.ResetByteCount()` (`BridgeHandler.cs:205–214`). | A successful wait does not replenish the render-clear budget in the visible Core code. Repeated successful waits leave the apparent no-progress condition unchanged. |

After `ClearAllRenders()`, a drain can empty the pending queue only if its length fits the **remaining** budget, `1024 - _numClears`. A queue of just one ID cannot drain when `_numClears` is already 1,024. In the common overflow case, `ClearAllRenders()` has exhausted that budget before enqueuing the remainder; the next drain therefore makes no dequeue progress. If the wait returns `false`, cleanup exits its loop with any remainder still pending and disposes the messenger in `finally`. Exceptions are also caught and cleanup proceeds to disposal. These are control-flow consequences of the visible code; they do not establish what the game displays after connection teardown.

## Lock and alternate reset paths

`BridgeContext` owns the `Rendering` manager used by this handler (`BridgeContext.cs:13–18, 37–45`). The only `ResetClearCount()` caller found in the five pinned Core files is the `HandleServer` clump path above. `HandleInternalMessages` also takes `_context` for every bridge message (`BridgeHandler.cs:27–51`), so it cannot run `ClearClientRenders`/`ClearAllRenders` concurrently while cleanup holds the lock. A search of the local pinned source slice found the reset declaration and that single invocation; this was not a repository-wide build or runtime trace of closed `Bridge.dll`.

`BridgeHandler.BlockingRun()` uses `Task.WhenAny` for `HandleInternalMessages` and `HandleServer` (`BridgeHandler.cs:191–192`). Therefore cleanup can start when either task ends; it does not first prove that the other task is finished. The lock serializes any code that uses `_context`, but the exact interaction between the remaining task and `TcpMessenger.WaitForAnyMessageAsync()` is not visible in the selected Core source. Treat that as an unresolved invocation detail.

## Client removal and MCT teardown

Core has a per-client clear route separate from handler-wide cleanup:

- If rendering is disabled for a session, `FlatBuffersSession` enqueues `RemoveClientRenders(clientId)` (`FlatBuffersSession.cs:442–461`).
- A disconnected session's `Cleanup()` enqueues `SessionClosed(clientId)` (`:519–548`). At the pinned server-message handler, `SessionClosed.Execute` sends `RemoveClientRenders(clientId)` and removes that session ([SessionClosed.cs](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/Server/ServerMessage/SessionClosed.cs#L4-L13)).
- `RemoveClientRenders` calls `Rendering.ClearClientRenders` ([RemoveClientRenders.cs](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/Server/BridgeMessage/RemoveClientRenders.cs#L4-L7)). It deletes only that client's tracked groups, and uses the same capped `ClearRender` path (`Rendering.cs:200–212, 231–242`). A later game clump normally resets the budget and `SendRenderClears` drains queued work.

MCT's frozen `GameSession.teardown()` calls `stop_match(shutdown_server=True)`, stops the owned Core process, then closes its relay sockets and joins worker threads (`game_worker.py:1517–1540`). It does not explicitly call a renderer clear method. The client disconnect route above is the source-backed per-client cleanup path; bridge-handler shutdown also calls `ClearAllRenders()` for every still-tracked client. This establishes intended clear requests at teardown, not that all queued remove operations reach Rocket League before the server/game connection closes.

At process shutdown, pinned `Main.cs` calls `BridgeHandler.Cleanup()` in the bridge thread's `finally` block and joins that thread after completing the bridge channel (`Main.cs:95–128`). Its termination path completes the server channel and then joins the server and bridge handlers (`:131–146`). `FlatBuffersServer.Cleanup()` completes session channels, joins session threads, and stops its listener ([FlatBuffersServer.cs](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/Server/FlatBuffersServer.cs#L134-L150)). The listener shutdown alone is not evidence that the separate Rocket League TCP messenger has already closed; the handler's cleanup loop still depends on its own messenger wait/termination behavior.

## Bounded future diagnostic

In an owned offline acceptance harness, exercise only the Core-side render manager with a tracked set that creates more than 1,024 pending clear IDs, then enter the same cleanup path with the counter at its cap. Record: initial `_numClears`, queue length after `ClearAllRenders`, each `SendRenderClears` result, whether the waiter returns `true` or `false`, any `ResetClearCount` call, and time to messenger disposal. Also test totals below the remaining budget and a normal disconnected-client `SessionClosed` path. A code-level harness or approved runtime trace would validate the static condition; this report does not run either. Do not turn the conditional finding into a confirmed runtime hang without that evidence.

## Source fingerprints and references

The selected local source files are original pinned Core bytes for commit `11d5d863ec2f8b2647741cff22a2c59c6b6ad08e` (v5.0.0-rc18). The SHA-256 values were checked against the local copies during this pass.

| Selected source | Bytes | SHA-256 |
|---|---:|---|
| `BridgeContext.cs` | 3,568 | `eda0c403a5552b4fbc4cc7c68871c40c742fb54c6eda6501b1c7cbcf67786a60` |
| `BridgeHandler.cs` | 10,064 | `d98ee7eaabb86c39a8a7c9ba7658fcc635cab9319be4d6d926c9bbec4b756785` |
| `FlatBuffersSession.cs` | 20,755 | `badb09b4b26a3dbcd1915a82056ae08f8989c652adbc743c81ba45cf9131e469` |
| `Rendering.cs` | 8,432 | `dd8470506d8ca9ae976adc5f8bd6885d2fee6998a9be424314c3da2fb5bc63df` |
| `SpecStreamReader.cs` | 1,249 | `5f33c723f32108b07407ed676f3200a705a61d1302d6df7b714f691fbc9d5e41` |
| Frozen MCT `src/my_career_training/game_worker.py` | 90,814 | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |

Pinned source links: [Rendering.cs clear queue](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/ManagerTools/Rendering.cs#L200-L256), [BridgeHandler normal clump and cleanup](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/Server/BridgeHandler.cs#L27-L82), [BridgeHandler loop and cleanup](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/Server/BridgeHandler.cs#L186-L225), [FlatBuffersSession render-disable and disconnect cleanup](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/Server/FlatBuffersSession.cs#L442-L461), [FlatBuffersSession session cleanup](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/Server/FlatBuffersSession.cs#L519-L550), [Main shutdown lifecycle](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/Main.cs#L95-L146), [FlatBuffersServer shutdown lifecycle](https://github.com/RLBot/core/blob/11d5d863ec2f8b2647741cff22a2c59c6b6ad08e/RLBotCS/Server/FlatBuffersServer.cs#L134-L150), and the existing [render-message budget report](render-message-budget-01.md) for transport, queue cap, and package context.

Additional coordinator checks used original pinned source bytes, correcting web-normalized line offsets. No runtime execution was added.

| Additional source | Bytes | SHA-256 |
|---|---:|---|
| Main.cs | 3503 | 6161765b3217ac0ef7ac8fe6d9d86553c2c4a218375467ba6fbdb6389e25f936 |
| FlatBuffersServer.cs | 4596 | 88bbeb9b420e178680c204f7a5ae93b490ae071b0c6bd57e638acea9dc21bb93 |
| SessionClosed.cs | 417 | 9dedde79f83378c0883db77fa475be5821f2e11991c23542de68197f9f9c5aa1 |
| RemoveClientRenders.cs | 231 | 9da64ee28490a050841fbf073cf3880fe7c2e97e48df0de2d2435f9fbaf53e98 |
