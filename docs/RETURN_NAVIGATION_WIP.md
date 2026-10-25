# Paused native Return implementation

This branch is an unfinished handoff snapshot, not a build or release candidate.
Do not merge or deploy it. The user requested that work stop and be preserved.

The partial implementation is commit `dd1c176`, based on `68448b7`. It changes
only `NativeReturnGate.h` and `NativeMovieProtocol.h`. The new gate signature is
not connected to its existing callers, so this branch is intentionally not
buildable yet. Only whitespace checking and a separate test-project CMake
configuration completed; no implementation test or live verification passed.

The integrated repair branch is `fix/windows-startup-and-download`. Its
`3cdaad0` commit prevents the legacy fullscreen overlay from taking input while
native READY is absent. Bring that completed change into the eventual combined
repair before acceptance. Keep this snapshot separate until implementation and
review are complete.

## Confirmed failure and intended repair

An actual saved career result returned through SDK `disconnect` to
`StartMenuMovie`. Leaving the match is not proof of reaching the authored hub.
The legacy overlay then covered the title screen. The separate overlay repair
addresses input ownership; it does not repair this navigation destination.

Use the verified typed ActionScript `Shell.ExitToMainMenu` after the exact
durable service acknowledgement. Preserve the pause menu's stock
`m_bExitingMatch` behavior. Do not invent an engine ABI, use raw console input,
or call cached movie objects after unloading.

Keep the native-click intent bound to bridge nonce, activity, fixture, and a
one-shot token. Include fixed navigation authorization in the published view's
signature/generation. Verify the native consumption acknowledgement before the
fixed typed call. Authorization, attempted navigation, and actual arrival are
different states. Complete only after fresh authored frontend READY and the
verified SDK menu stack reports `RootMenuMovie` in the same owned offline game.
Block new activities while Return remains pending.

Preserve pending intent if the pause movie unloads while the worker drains.
The pinned SDK declares `OnOpenPauseMenu`, but its opening behavior is not
verified. A single guarded call on a fresh controller has been authorized for
an owned offline test after the exact service acknowledgement; observe the
actual pause movie and READY before relying on it. Do not retry blindly or
claim that a void call succeeded. Stock screen removal unloads its movie, so
retaining an ActionScript timer is not a reliable recovery strategy.

## Work still required

1. Review and finish the partial gate/protocol implementation.
2. Connect the host and validated native callback path; remove raw disconnect.
3. Implement authored pause/results consumption, rebuild bytecodes and pins.
4. Update and run meaningful gate, stale-scope, generation, protocol, and
   pause-unload tests. Run the normal plugin build too.
5. Integrate with the completed overlay guard in the repair branch.
6. Build one coherent candidate and test real Return from results, practice,
   and an unfinished fixture, including Resume during delayed cleanup.
7. Verify the exact frozen installer input before publishing any player build.

Actual Cursor CLI Grok 4.7 High provided the architecture review. Its code-writing
run was stopped at the user's pause request before making changes. The two
partial headers were written by the coordinating agent alongside that advice.
