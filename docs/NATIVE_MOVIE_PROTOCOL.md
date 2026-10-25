# Authored native menu and local protocol

`native_ui/menus/MctRootMenu.as` is original mod code that derives from the
game's `BranchingMenu`. It creates the game's existing button controls, copies
their font for the adjacent career text, preserves menu-stack notifications,
and handles Back through the currently published `nav.back` choice. Longer
choice lists have local pagination. Stock Garage and Options are explicit
typed routes; online/store controls are absent from this authored class.

`MctMainMenuScreen` derives from the original document class and preserves its
menu-stack, screen-filter, resize and car-camera handling. It omits the parent's
challenge, friends and matchmaking listener registration, hides the challenge
and debug widgets, hides the shell news view on every offline chrome pass, and
deactivates the shell's party/friends taskbar. The root
also overrides the inherited rightward focus path into matchmaking. These
changes belong only to the privately composed offline movie. Shell changes
remain within that game process; the normal online handoff closes it first.

The stock Garage keeps its preset switcher, customization and preset management.
While it is on this screen, the private document hides and disables its premium
inventory, trade-in, blueprint and reward controls, removes their focus routes,
and cancels their click events in the capture phase. It also removes the stock
buttons' inherited rightward matchmaking focus route. These guards run again
after stack changes and on each frame because stock data callbacks may update
button state. The later full car-customization screen's lifetime and navigation
still need the focused game check; compiling these guards does not verify that
transition.

This is a development candidate. Earlier source checkpoints loaded the authored
frontend, pause and results movies in Rocket League; see `PROJECT_STATUS.md`
for their exact evidence and the observed Return failure. A rebuilt movie needs
its own acceptance. The plugin wires `NativeMovieHost`, but its CMake option
defaults to OFF. An opt-in build also requires the exact session, game
hash/build, BakkesMod version and current owned offline surface. Native builds
suppress the legacy fullscreen interface even during READY gaps. A nonblocking
training HUD remains separate from native-menu input ownership.

## Wire format

`NativeMovieProtocol` adapts the existing `NativeCareerLayout`, so the movie
does not implement career rules or choose arbitrary bridge actions. The host
opens the model with a live owned/offline/fresh scope, then publishes a bounded
view with protocol 1, session, timestamp, active state, title, body and controls.
Each control has an id, label, reason, enabled flag, revision and optional
`garage`/`options` stock route. Generations and revisions are decimal strings
to preserve 64-bit identity in ActionScript.

Heartbeat-only publications retain their generation. A changed binding,
accepted click, reopened scope or invalidated view requires a new generation.
The retained binding includes its action and payload even though those fields
are not sent to the movie. A click carries only protocol, session, generation,
revision and control id; extra caller-supplied action or payload fields fail.
The model rechecks the current backend state and ownership on selection.

The authored movie reads a session-specific decoded Windows path using
`URLLoader`; the game tests rejected the earlier `file:///` form. It refuses a
mismatched session or data older than five seconds.
It sends custom choices through the existing `DevUtil.Log` wrapper with the
fixed category `MCT_NATIVE_UI_V1`. The development host validates the caller,
bounded string parameters, current game build, session and live ownership
before passing the message to this protocol. Unrelated log calls remain
unrelated. Neither a file nor a log message establishes ownership. A separate
three-field frontend readiness message carries protocol, session and
`event:"ready"`. Pause/results readiness also carries the actual surface and
generation. The rebuilt frontend also sends the five-field form, and Return
arrival requires that current generation-bound READY. Pause/results choices
carry surface as well. Surface selection is
derived from the host's game observation, never from the movie's request.
The root continues polling while retained in the menu stack behind a native
Garage transition, but only rebuilds controls or handles choices when it is
the active menu on the current screen and no modal covers it. Leaving the stack
stops the timer.

Local-file loading and native callbacks worked at the recorded source
checkpoints. That evidence does not certify a new compiled artifact or every
stock-screen transition. The class falls back to a connection message and an
explicit native Exit control if its view is unavailable.

## Return repair exchange

The host retains a Return intent for one bridge session, activity and fixture.
Only the exact durable service acknowledgement may authorize the fixed typed
`Shell.ExitToMainMenu` route. It does not accept an engine command in JSON.
The required exchange is:

1. Publish `navigation` with `phase:"authorize"`, `intent`, `activity`, and
   `fixture`. The one-shot intent is 32 lowercase hexadecimal characters.
2. The current movie sends `return_navigation_consumed` with protocol, session,
   surface, generation, intent, activity, and fixture. It remembers that
   consumption locally and does not exit yet. The log API returns no success
   value, so logging alone cannot prove host acceptance. At most two additional
   identical consumption messages, at least one second apart, may follow while
   that same fresh authorization remains current. The exit call is never retried.
3. After validating that consumption, publish `phase:"execute"` with the same
   identities and `consumed_generation`. Both phase changes alter the view
   signature and generation. A movie without the matching local latch cannot
   execute the grant.
4. Immediately before its one-shot typed call, the movie logs
   `return_navigation_issued`, carrying the execute generation and consumed
   generation. The pause movie retains the stock exiting-match flag. This is
   attempted navigation, not evidence of arrival.
5. Complete Return only after the new frontend earns READY and the live menu
   stack reports `RootMenuMovie`. Independently verify the visible hub in the
   owned foreground game. Keep new activities blocked until then.

The repair must revoke a consumed grant when its movie unloads while preserving
the accepted Return intent. Scope or activity replacement revokes the intent.
Transient stale reads cannot authorize effects. See `INTEGRATION_CONTRACT.md`
for bounded committed-Return retention and external-unload recovery, and
`NATIVE_ACCEPTANCE_SESSION.md` for the separate source/frozen game checks.

## Build evidence and distribution boundary

The source compiled with Apache Flex 4.16.1, Temurin JRE 21.0.9, a PlayerGlobal
32 reference and SWF version 20. A private SWC containing the owned game's ABC
declarations was supplied through `external-library-path`, which excludes that
library from the output. The compiler reference's GFX media tags were omitted
from that private SWC because Flex's SWF reader cannot parse those tags.

The compiled classes, hashes, and method count are in
`native_ui/compiled/manifest.json`.
The original mod ABC is stored under
`native_ui/compiled/`. It contains placeholders for the local view URL and
session. It contains no linked game classes or game artwork. Rebuild the ABC
when editing its source; the composition step must bind the placeholders and
validate its pinned hash before using it.

Private game SDKs, original/modified GFX movies and original/modified UPK
packages must stay outside the repository and distribution. Players should
receive our compiled code and a bounded transform for their own matching local
game, not the compiler, Java, a private SDK or redistributed game assets.

The plugin protocol's focused executable covers navigation, duplicate and
stale choices, unrelated callbacks, caller payload refusal, reconnects,
heartbeat focus stability, offline scope and the fixed Exit dispatch. It does
not start a game.

## Results save recovery

Results offers Retry saving after a career save error. The host binds this
control to the current activity and fixture. The service reads only that
activity's bounded durable receipt, checks both identities again, and uses the
normal result commit. Failure retains the receipt and pending fixture; success
unlocks Return to My Career. Repeating the command cannot score the fixture
twice. Automatic receipt recovery after a worker exit also updates the current
results state, unless a stop transition already owns the session.

The results explanation and leave-match confirmation appear before bounded
error details. Synthetic checks cover failed and repeated saves, old identities,
and worker-exit recovery; they do not establish live movie compatibility.
