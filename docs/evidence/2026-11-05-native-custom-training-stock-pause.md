# Native Custom Training stock pause candidate

Base: `0bc322b2ff511a178ffc5e2dbe279d8ec9bb5a41`. The loaded game evidence below
belongs to earlier exact candidate `a59c45f`, not this source repair.
Status: source/compiled authored-movie checks passed; not packaged or live tested.

## Observed defect and source cause

In a separate bounded `a59c45f` run, the existing local sequence entered native
Striker training. Idle showed 0:10. Backspace was pressed at the initial state
with no visible change, so reset was not accepted. A short W input moved car/ball
and showed 0:07; a later initial scene at 0:10 supports an automatic reset
inference only. No exact zero frame was captured. The local training file was
unchanged; native Custom Training telemetry was not retained.

Escape showed **My Career paused**, Resume, Game options and a disabled Return
to My Career. The source explains that outcome: the private midgame replacement
subclasses the stock pause class but unconditionally destroys its buttons, while
the host admits any owned offline midgame pause. The manual native activity has
no MCT session id, so the authored Return control is disabled. Suspending the
host alone would still leave the authored waiting screen rather than stock UI.

Read-only inspection of the pinned midgame movie confirmed its original
`MidGameMenu` retains training-specific Save and Exit, End Training and ordinary
exit confirmations. It chooses between the native editor-playtest callback and
main-menu exit according to native state. The candidate delegates to that class
instead of copying a single exit action. Extracted assets remain private.

## Bounded contract

- Offline `GAME_EDITOR`, or `TRAINING` with the native custom-training flag,
  uses the original pause buttons, input, focus, resizing and screen chrome.
  The match-type check prevents a retained training flag from changing Career.
- Authored details, view polling and Return locks do not take over this mode;
  late view responses are ignored. Native save/discard/cancel prompts and the
  native choice of destination remain intact. No automatic exit/save is added.
- All native Custom Training, including the older native-pack service route,
  uses stock pause. Ordinary Career and RLBot soccar lessons retain authored
  pause, Return/forfeit and results behavior. Results composition is unchanged.
- Live acceptance must establish the selector's actual native state, visible
  stock pause/confirmation, resume and native exit destination, plus a Career
  pause/Return regression. Native-pack service state after stock exit is a
  separate integration boundary; this patch adds no backend cleanup shortcut.

## Verification and limits

Apache Flex 4.16.1 compiled the authored pause against a private ABC-only SDK
derived from the pinned original midgame movie. Final-source recompilation
produced the same owned ABC: 22,138 bytes, SHA-256
`2b9efc322e3facd8a7fb6f10a212db6cee3ea3483527360cedf672461a31b942`.
Its export contains three authored classes and seven existing JSON classes only.
The manifest/composer and staging/runtime inventories agree; the full production
menu-contract check passes with imports verified from this checkout.

The actual compiled selector's exported instructions passed twelve synthetic
offline/online, editor/training/Career and retained-flag cases. These are isolated
instruction checks, not a live DataAPI observation. A source contract regression
covers input, buttons, focus, resize, polling and document chrome delegation.
Composition/staging/candidate tests: 111 passed, one skipped. Current-source
MSVC builds of native match-movie, Return-gate and results-hold tests passed.
Ruff and privacy/diff checks passed.

No game input, installed-file change, plugin/frozen package or native content
redistribution was performed for this repair. The original sequence and its
normal game-owned profile rotation are outside this source candidate.
