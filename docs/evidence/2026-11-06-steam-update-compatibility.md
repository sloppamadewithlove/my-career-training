# Steam update compatibility checkpoint — 6 November 2026

The active review target was 07:01:37 UTC; this checkpoint started at 07:02:15 UTC,
38 seconds later. This records one review. The next active-chat target is
07:47:15 UTC. No persistent timer or unattended review is claimed. Documentation
base: `5604b0154b1f792a35424051d507d92c4ed648f1`.

## Update and candidate evidence

- Current session evidence reports that Steam automatically updated Rocket League
  between 06:08 and 06:15 UTC, moving Steam build ID `25914621` to `26349479`.
  A read-only check of the actual installed executable confirmed Steam build ID
  `26349479`, FileVersion `1.0.10897.0`, and SHA-256
  `bcfb323316bc9f4e44cc1dc761e47a55d5529ebdb42ed14217361cda51a6bd1c`.
  The file version is unchanged from the prior candidate's observation, while
  the hash differs from the old `56b499…` prefix. Three menu-package hashes were
  reported matching; they establish asset identity only, not executable/plugin
  compatibility.
- Candidate source at `9ee0c3333686be74afdd5de0e24cde2932b1af61` completed its
  build, tests and smoke per the current report. No game launch occurred after
  the reported update. A prior assumption that the candidate was safe was stopped
  before launch while the exact compatibility guard remained unverified.
- Static inspection of `plugin/include/NativeBuildGate.h` and
  `plugin/src/NativeMovieHost.cpp` found the diagnostic gate still pinned to the
  old executable SHA-256
  `56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7`, Steam
  build `25914621`, FileVersion `1.0.10897.0`, and BakkesMod core version `229`.
  The gate explicitly describes itself as a fail-closed read-only diagnostic
  trial, not a compatibility or mutation allowlist. The native movie host checks the exact running executable hash and
  BakkesMod version and Psyonix build ID `261013.63066.530866`; on mismatch it
  refuses the diagnostic path, removes its hook and suspends. This source behavior
  is not proof that the updated game can load the launcher/plugin. Its exact hash
  and Steam build comparisons would refuse the new executable if evaluated; no
  post-update runtime load or compatibility acceptance was performed. The game
  process was not running during the read-only check.

## Required gate

Before any game launch, establish an owner-reviewed compatibility contract for
the now-identified executable and the supported launcher/plugin path. The current
diagnostic guard's exact comparisons would reject the new hash/build because its
reviewed pins are still old; do not repin those constants based only on version
or treat the unchanged FileVersion as approval. A changed pin alone cannot
establish support. Preserve the `9ee0c33`
build, test and smoke receipts as candidate evidence; refresh the runtime
compatibility proof only after the exact capability check is established, while
retaining asset hashes and candidate provenance.

No game input, launch, source edit or asset change was made for this documentation
checkpoint. The installed executable's full path was not recorded. No account
identifiers, raw logs or game assets are included.
