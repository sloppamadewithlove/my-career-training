# Input, native-clock and Return follow-up — 29 October 2026

## Actual candidate evidence

`a8b6a3475b5c7dcac19fbf2142282df9b2a54b96` passed 37 native plugin and 13
launcher checks, then launched in a copied offline profile. The loaded module's
file hash matched the staged candidate. Main was the sole operator.

Windows initially refused foreground access during startup. Input stopped and
help was requested. A later read-only check observed that the same owned game
had become foreground; capture and input resumed without another focus request.
The private input helper now observes foreground only and never requests focus.

The native browser/rank route opened Gold. Timeout remained finished with the
ball hidden, without changing the copied profile's automatic-retry setting.
However, generated Up did not retry with the console closed: the cursor-only
guard added at a8b6 was too broad. This is a regression, not a completed fix.

The explicit clock probe produced eligibility logs. The owned offline RLBot
match had no match GUID, so the previous mandatory GUID condition blocked it.
The submitted diagnostic was at a finished attempt, also ineligible. No native
clock mutation, countdown or restoration is claimed from this run.

To isolate the separate reset defect, main exercised existing service retry/step
commands while the owned game remained foreground. Nine challenge-5 starts
produced six active attempts and three reset interruptions. These are real game
observations through the service route, not proof of keyboard or controller input.
The sampled bridge could miss the first READY frame because that diagnostic was
overwritten by subsequent packets. Physics tolerances and pack geometry remain
unchanged until the retained first-frame data resolves the failure.

The owned test was closed normally before replacing loaded components.

## Source corrections

- Replace cursor visibility with ImGui's actual keyboard-capture signal, sampled
  in Render using the supplied context and published atomically to the game tick.
  Context and close boundaries clear the sample. A real console/HUD test remains
  necessary; this is not a claim of a console-open API.
- Permit the bounded opt-in clock probe in a local match without a GUID. Fresh
  owned process/session/attempt checks bind arming, the event pointer binds writes,
  and a captured nonempty GUID remains an additional identity check. Existing
  same-event cleanup and replacement-event refusal are retained. This is still a
  development probe, not a native lesson countdown or zero-expiry implementation.
- Preserve the first READY reset snapshot and ball angular velocity per attempt.
  Later bridge sampling no longer destroys that measurement; retry clears it.
- Allow a durable non-Career Return to preserve an unrelated valid saved Career
  fixture. Previously the service acknowledged this cleanup while the native
  gate rejected it. Nonempty-fixture Career returns remain strict, and malformed
  pending data or a different activity receipt cannot authorize navigation.

The worker/bridge/reset Python checks pass 188 cases. Independent native Return
and continuation tests each pass 1/1 under MSVC. The exact extracted probe method
passes 15 fake-wrapper cases, including empty-GUID restoration and wrong-process
refusal. Independent ImGui review confirmed context/API and overlay lifecycle;
actual console capture still needs a live check. Source tests do not certify the
next DLL or any live control effect.

## Delivered workflow improvement

The scheduled worker's privacy checker was aligned at `c969569`, independently
verified with 25 tests, zero evidence/research scanner findings and Ruff, and
passed Windows CI. PR #11 was merged as `c14cb5d`; its tree exactly matches the
tested combined tree. It is now integrated, rather than a pending recommendation.
The task was separately read back as active with a 45-minute interval.

The training product contract is corrected to the owner's later decisions:
approved Gold reference packs, goal-to-next progression, manual timeout retry,
and actual native timer. Earlier contradictory prose must not guide new work.
