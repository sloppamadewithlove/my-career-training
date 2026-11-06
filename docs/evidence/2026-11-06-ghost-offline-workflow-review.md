# Active workflow review — ghost and offline-test progress

On 6 November 2026 the active-session review was due at 23:07:31 UTC and
began at 23:07:35 UTC, four seconds late. This is an active-work check; no
recurring app timer is claimed. Next active review target: 23:52:35 UTC.

## What the work established

- A real, bounded observer configuration stage and conditional restoration
  succeeded with no game launch. Both plugin configs matched retained baseline
  hashes afterwards; the staged observer and active marker were absent; the
  private transaction journal remained. A comparison of previously identified
  profile roots found 513 unchanged entries and no changed/new/missing entries.
  This does not establish complete save/cloud coverage or game compatibility.
- The source integration branch contains independently reviewed ghost frame,
  rendering consumer, recorded car/ball/action transport, selection controls,
  acquisition-evidence retention and a bounded installed-bot capture experiment.
  One integrated checkpoint passed a full SDK plugin build and eight CTests; a
  later source integration passed 333 independent Python tests. No successful
  reset trace or game-visible ghost is established.
- Actual Backend-to-worker-to-native tests revealed that a Retry could briefly
  show an old frame, and a settings Off path did not immediately hide it. A
  correction adds reset generation invalidation and was then found to prevent
  settings On after Off. The second correction is still under review. Unit passes
  alone did not prove the full control flow.
- Bot-trial review found a deadline gap during startup and then a slow policy
  return that could send input after expiry. Both corrections passed independent
  review; the deadline is cooperative and cannot interrupt a blocked native call.
  The installed policy's ability to perform a flip reset remains unverified.

## Improvements for future sessions

Exercise every user-facing control through real producer, backend, transport and
consumer paths, including Off then On, Retry and delayed packets. Validate a
failure boundary before publishing a successful receipt; retain ambiguous files
for recovery. Test asynchronous deadlines before and after external calls, not
just at the top of a loop. Keep the next actual game step small: observe the
installed Steam UI's official Without EAC selection, preserve the original
launch settings, then establish owned process/loader/lease evidence. Version
metadata, a staged DLL or a fixture is not proof of a game-visible result.

The owner requested an alternative to performing the reset personally. The next
candidate is an explicitly bounded experiment with an already-installed bot;
keep captures private, record failures honestly, and never present declared
success as independently validated teaching evidence.
