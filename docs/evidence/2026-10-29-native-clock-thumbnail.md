# Native training clock and gameplay thumbnail candidate

The native plugin writes the scenario's remaining time to the actual game clock.
The worker retains timeout ownership; unlimited match time stays enabled to avoid
stock match end/overtime. The same-event lease captures the original clock once,
retains it through retries, skips writes while paused, and restores on cleanup.
Replaced events and online/replay transitions discard the lease without writes.
The diagnostic probes release the production lease before their own timed writes.
Native clock values and flags are exposed in plugin status for direct verification.

The duplicate overlay seconds are removed; challenge index and controls remain.
Native HUD presentation with unlimited time and sustained zero require live checks.
Pure clock lifecycle checks passed; worker and no-score timeout checks: 65 passed.

The root browser embeds a 12,655-byte, 400x225 gameplay JPEG once. It reuses the
decoded bitmap for the row/detail and keeps fallback rendering on decode failure.
ABC is 51,598 bytes, within the unchanged 65,536 cap. Source and binary pins are
updated together. See native_ui/THUMBNAIL_PROVENANCE.md for capture provenance.
Independent asset checks passed (86 plus one checkout-context check; one skipped).
Actual game decoding remains unverified until this candidate's live test.

Informational plugin-session notices now appear in Settings rather than across
every menu. Startup/restoration failures remain visible. Five focused Python and
the native layout check passed for this change. Full candidate build pending.

## Live 3beada6 follow-up

The compiled candidate passed 38 plugin/13 launcher checks. Full Python source run
at f9ee696: 1,641 passed, 15 skipped, one outdated overlay-timer assertion failed.
The only subsequent source changes updated that assertion for both running/timeout;
the complete 101-case Power Shots suite then passed. Source/native 3beada6 was rebuilt.

Owned live test: the hub no longer shows the global plugin-session notice. Native
clock visibly displayed 0:07 after Up retry; timeout hid the ball and held the same
playable session with direct remaining=0, no overtime/end flag. However, the actual
HUD remained at 0:01. This is a failed zero-display acceptance, not a finished timer.
The next repair calls the SDK OnGameTimeUpdated notification on display-second
changes and records both integer timer getters. Retained SDK wrapper analysis shows
a no-argument Soccar event dispatch, not score/restart writes; game-side semantics
still require live verification.

The gameplay thumbnail showed its fallback. The next candidate removes the
thumbnail's unnecessary unsupported SecurityErrorEvent listener, moves listener
setup inside error handling, and adds bounded private runtime lifecycle markers.
The rebuilt authored ABC is 51,926 bytes; asset checks: 87 passed, one skipped.

Rapid Right navigation also reproduced a missed Gold3 launch confirmation: the
first response was a parked ball after a four-step gap. The next repair reissues
the launch once only when the first <=50ms response has that gap/parked signature.
It preserves the original evidence/attempt ID and every verification gate; strict
capture is excluded. A second failure remains a bounded interruption. CPU load as
the cause is an inference, not established by that observation.

## Integer clock cache and pixel-image follow-up

Candidate c1f4fce passed 38 plugin/13 launcher checks and 314 targeted Python
checks (one skipped). Owned live Up retry displayed native 0:08. After timeout,
73 sampled zero-field observations spanned 7.686 seconds with round active,
no overtime and no match end, but the visible HUD still said 0:01. The independent
integer getter confirmed SecondsRemaining=1 while GameTimeRemaining=0. Notification
alone did not fix that cache. The next change snapshots, writes, verifies and restores
both fields together, then notifies on integer-second changes. The pure lifecycle
test covers original integer restoration and held zero; live proof is still required.

Generated Right navigation reached challenge 9 with no interrupted reset in that
run. An actual generated-key shooting attempt timed out without a goal; it provides
no evidence for goal advancement. No scores or physics were injected by that test.

The JPEG thumbnail still fell back. The alternate stores the same gameplay pixels
as RGB332 indices: 20,648 compressed bytes expand once to a 400x225 BitmapData.
It uses ByteArray.uncompress and BitmapData.setPixels, documented GFx APIs, instead
of image Loader callbacks. The new ABC is 62,429 bytes within the unchanged 65,536
limit. Independent decoding matched all 360,000 ARGB bytes of the prepared preview;
asset/composer checks: 87 passed, one skipped. Reduced color precision is visible;
this is a genuine captured scene, not generated content. Runtime acceptance pending.
