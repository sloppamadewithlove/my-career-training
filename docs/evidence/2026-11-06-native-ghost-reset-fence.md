# Native ghost reset/Off correction — 6 November 2026

Review base: `19891da`. Corrected code: `09ab19bfb123d57d6dd9d5ffebfe18bfdbf48cde`.
Builder: GPT-6.1 Sol high. The companion recorded-pose dependency remains the
one named in [the production wiring receipt](2026-11-06-native-ghost-production-wiring.md).
Independent delta review is still required. No game operations were performed.

Review found two actual state defects. Manual retry reset the worker's attempt
and playback cursor while Backend retained the previous visible source and pose;
the native consumer could keep drawing it within the 100 ms window. The assistance
Ghost Off path sent preferences to the worker but similarly retained the old
visible cache, and delayed On telemetry could restore it.

## Reset barrier

Backend now hides the retry pose before sending the actual retry command, while
preserving the desired On state and saved preferences. It suppresses old-generation
telemetry until an observed active packet from the new reset arrives.

That cache change alone cannot revoke a native consumer between bridge polls.
The existing state file has Backend as its writer and is cached by the plugin;
the command and status files run in the opposite direction. The correction adds
one fixed ephemeral file, `bridge/native-ghost-reset.json`, without a caller-selected
IPC path or general messaging framework.

Before each whole actor reset or scenario replacement, the in-game worker reads
the fixed bounded state file, requires its own exact session and a canonical bridge
nonce, and atomically publishes a new reset generation using the existing atomic
writer. A failed authentication or fence write prevents the actor write. A callback
arriving while reset is in progress carries no valid generation. The generation is
captured with each packet callback, so a pre-reset queued packet keeps its old
generation even if processed after the engine has changed attempts.

The native scope reads the fixed fence afresh, with a 1 KiB limit and shared-delete
file access, on each draw. Missing, malformed, oversized, wrong-session, wrong-nonce
or invalid-generation fences fail closed without a cached fallback. The actual
generation participates in native draw identity and must match the packet source.
Thus cached telemetry cannot be admitted after a reset by getting a newer attempt
label or bridge heartbeat. Receipt expiry clocks are sampled after fence/SDK reads.

New-generation source packets also need the existing engine's actual active state
and observed start time. Sending a state-setting message is not called an applied
reset acknowledgement. Existing settle/launch observation remains the authority.
Closing FileBridge revokes the fence before publishing the closed state. No save
or recording format changes, actor/control writes or new game input were added by
the native renderer; existing lesson reset behavior remains in the worker.

## Assistance Off

The actual assistance action now clears visible practice state before sending
preferences, sets the existing runtime desired flag Off, and cancels pending On
adoption for that same worker/lesson. Delayed visible packets and late On answers
cannot restore it. The assistance action retains its existing saved-preference
semantics: it changes that lesson preference and does not rewrite global training
display preferences through the toggle's separate synchronization path.

## Evidence and limits

The corrected full Release DLL and native probe compiled against the real pinned
SDK and the exact companion header previously recorded. Seven native CTests passed,
including playback, renderer, projection, immutable frame, proxy, diagnostic scope
and LocalBridge contracts. Ruff and whitespace checks passed.

The isolated implementation passed 103 focused Python checks with the two
companion-dependent transport checks skipped. A preliminary combined verification
checkout `fd87ac687da4c113ae83b85dcdcecd12955f0b76` passed 116 checks with four other optional companion parser/menu checks
skipped. The correction test uses actual Backend dispatch, worker command handling,
engine reset/settle/launch observation, FileBridge and the compiled native consumer.
Only the game SDK/packet bodies are synthetic.

That regression proves fence publication and rejection of the consumer's old
snapshot before the SDK actor-write boundary, preserved On through manual retry,
pre-reset queued packet rejection, new observed-packet recovery, reordered old IPC
rejection and automatic retry. Automatic retry uses an actual attempt event, Backend
storage and Backend-produced `attempt_ack`, then the real worker acknowledgement
path; no acknowledgement is invented. Assistance Off covers both speed flip and
flip reset, including pending/late On answers, saved preferences and delayed visible
telemetry. The compiled regression also covers missing/invalid/oversized/old-worker/
old-bridge fences and closure. Authentication-negative tests prove no actor write
with missing state, the wrong worker or an invalid bridge nonce.

A standalone Release native benchmark of 2,000 valid fixed-fence reads measured
187.5 microseconds median and 460.5 microseconds at the 95th percentile on this host.
This measures the reader under a synthetic workload, not live game performance.
An eligible update reads once, submission rechecks it, and every draw independently
rechecks it; hidden/unavailable samples skip native observation. Disk latency,
antivirus contention, gameplay scheduling and visible jitter still need live proof.

This source still fails closed on the existing unmatched-build verifier and retains
the Canvas screen-overlay limitation. No game was opened, no DLL installed, no
package built and nothing published. Provider token/time/cost totals were unavailable.
