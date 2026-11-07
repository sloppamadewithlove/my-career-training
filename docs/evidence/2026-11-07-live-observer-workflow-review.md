# Active workflow review — live observer and recovery

The active review was due 6 November 2026 at 23:52:35 UTC. It began on
7 November at 00:21:41 UTC, 29 minutes 6 seconds late, while the owned game test
and save restoration took priority. No recurring timer is installed. Next active
review target: 01:06:41 UTC.

## Observed live boundary

- The actual Steam UI offered the official anti-cheat-disabled option. A bounded
  launch used that choice and the exact requested observer arguments. The owned
  game executable and arguments matched the identity candidate; installed
  BakkesMod core and SDK modules were observed loaded with matching file hashes.
  This does not prove observer compatibility or the game's EAC/internal state.
- At the title screen the BakkesMod console opened. Rapid Unicode input dropped
  one letter, and an attempted cursor correction appended it instead. Neither
  incorrect command was submitted. The observer was not loaded; no ghost,
  Training exit, game scenario or reset was tested. The owned game and injector
  exited. Steam's original launch choice and empty arguments were restored and
  read back; plugin configuration hashes matched baseline and the staged DLL and
  marker were absent.
- The game removed five previously existing .save entries. Verified private
  copies existed. An independently reviewed CreateNew-only recovery restored
  five files without overwriting changed/new files; its receipt reported five
  verified copies and the identified-root comparison reported zero missing.
  Independent endpoint hash verification is pending. Steam Cloud was enabled;
  it is not a guarantee that later writes cannot occur. Restored identities and
  timestamps differ, and a byte-identical entire profile is not claimed.

## Changes to the workflow

- Use one small live test with an immediate visible goal. Diagnose actual input
  behavior on the console; verify text after a paced or supported input method,
  not merely after SendInput returns. Do not submit an unverified command.
- Protect and reconcile the actual game profile before and after every launch.
  Preserve changed/new saves, use CreateNew for absent baseline files, and treat
  cloud activity as an ongoing race rather than assuming the client is quiescent.
- Favor the existing mod, plugin SDK, installed tools and a verified replay or
  one real bot capture over building broad new infrastructure. A video can show
  the desired maneuver but is not itself synchronized car/ball/input telemetry.
  Replay-derived estimates must remain labeled as estimates; use rights-cleared
  sources and never call a reconstructed move a verified successful trace.
- The owner requested an audit of implicit state machines. The first reproduced
  defect is Retry discarding an attempt before a failed actor reset; its repair is
  independently under review. Inventory stateful runtime paths, prioritize
  observed wrong transitions, and do not claim all bugs fixed from an inventory.

Keep exact source, compiled DLL and live-game evidence separate. The current
published ghost remains unaccepted in-game and the user cannot perform the
flip reset personally; pursue another permitted capture route.

## Save restoration verification

Independent readback subsequently verified all five restored targets against
retained baseline bytes and the private completion evidence. The original save
was restored first. The identified-root comparison reported 501 unchanged,
12 changed, 2 new and 0 missing; restored file identities and timestamps differ.
Both plugin configurations match their baselines, the temporary observer and
active marker are absent, and Steam's normal launch choice and empty launch
arguments were restored. A newer backup remains present and was not targeted;
no separate before/after byte comparison for that backup is claimed. Steam Cloud
writer exclusion and full profile-root completeness remain unproved.
