# Native career layout

`NativeCareerLayout` is a pure menu plan for a future engine binding adapter.
It describes the offline My Career menu the adapter should present. It does not
draw that menu, write memory, send a bridge command, or launch Rocket League.

The class is not a finished native replacement. `kNativeReplacementFinished`,
`kProductionGateEnabled`, `kSuppressionEnforced`, and `kCompatibilityGrant` are
all false. Root's binder is separate. Visible labels and real consumption of
the original menu action are still unproved.

## Menu

The replacement plan has seven top-level controls:

| Control | Where it goes |
|---|---|
| My Career | Play Next Match, plus read-only Squad, Schedule, and Season |
| Training | The lesson catalog, then that lesson's practice, help, speed, and setup |
| Garage | The game's own garage, plus local bot presets when the career catalog allows them |
| Workshop | Refresh and favorites for maps already in the published library |
| Community | Lookup, private-cache download, library check, and cancel |
| Settings | The game's own options, plus the existing training-display choices |
| Exit | Bridge `quit_game`, which stops the owned session |

Play Next Match, lesson selection, practice, bot presets, workshop favorites,
community cache actions, training display, and Exit are bridge dispatches.
Squad, Schedule, and Season are read-only text from the current state, capped
at eight schedule rows, eight standings rows, and four squad members.

## Scope

`open` stores a scope only when it is owned, offline, fresh, and not online,
its nonce matches `bridge_session`, its protocol is 1, and its generation is
non-zero. The host supplies freshness from the bridge snapshot. This model
does not read the clock.

`view(current, state)` and `route(id, current, state)` require that same live
scope on every call. `current` is compared with the scope stored by `open`:
ownership, offline, freshness, online, nonce, and generation. `choose` rebuilds
the view with its click scope. There is no call that can show a replacement or
a suppression list from the stored scope alone.

`state.offline` is the backend in-game flag. It is not the live online status.
The same nonce and the same JSON still produce an empty view and a passthrough
route when the live scope is now online, stale, unowned, or on another
generation.

Normal Steam, an online flag, a missing nonce, generation 0, or a stale click
produces an empty plan. Custom dispatch does not run. Route decisions stay
passthrough, including online matchmaking.

## Effects

`choose` compares the shown control with the control rebuilt from the latest
state. Each rendered choice carries a monotonic `revision`. Logical control ids
stay stable. An accepted `Navigate` or `Dispatch` advances the revision, so a
second callback that still holds that rendered choice does not dispatch again.
`workshop_favorite`, Play Next Match, and Exit are covered. A rejected click,
including one that has not consumed the original action, does not advance the
revision. After an accepted choice advances the revision, rendering again
returns controls carrying that new revision for a later intentional click.

`open` also advances the revision, including when it is called again with the
same scope. A choice captured before that call stays stale. The counter does
not wrap. Once it is saturated, further plans fail closed.

- `Navigate` changes the local page only. It has no bridge action.
- `PreserveStockRoute` is `StockRoute::Garage` or `StockRoute::Options`. The
  action and payload stay empty, including when the caller says the original
  action was consumed. The model never pairs a stock route with a local command.
- `Dispatch` is returned only after `originalConsumed` is true, and only for an
  action in `supportedAction`. The acknowledgement is a precondition. It is not
  compatibility proof. `compatibilityGrant` stays false.
- A disabled or unavailable control returns an empty action. Match and lesson
  controls also fail when the career, fixture, or lesson id no longer matches
  the latest state.
- An unknown control id fails closed. That refusal does not ask the adapter to
  consume every other native callback.

Exit's action is `quit_game` with an empty payload. `kTerminatesProcess` is
false. The service path posts a close to the owned game window; this model
does not name a process-kill operation.

`supportedAction` is the only dispatch set:

`play_match`, `select_lesson`, `start_lesson`, `assistance`, `lesson_variant`,
`restore_explanations`, `loadout`, `refresh_workshop`, `workshop_favorite`,
`community_lookup`, `community_download`, `community_library`,
`community_cancel`, `training_settings`, `quit_game`.

Payloads use the current bridge shapes: match calls carry
`expected_career_id` and `expected_fixture_id`; loadout carries `id`,
`car_id`, `primary_color`, and `secondary_color` for a catalog body
(Octane 23, Dominus 403, Merc 30, Breakout 22).

## Routes the binder must treat specially

While a replacement plan is active, `route` and `view.suppress` list six typed
routes the binder should suppress:

`OnlineMatchmaking`, `TournamentJoin`, `Store`, `RocketPass`, `Account`, `Party`.

`AccountCloudSync` stays passthrough. `Garage` and `Options` stay
`PreserveStock`. `Unlisted`, and any value outside the enum, stay passthrough.
There is no string route name and no global callback sink.

`suppressionRequired` can be true. `enforcementVerified` is always false. The
list is a binding plan, not evidence that a click is already blocked. The model
does not propose a firewall, a network block, or a global Steam change.

## What the current backend does not let this menu do

These are gaps in the current service, not hidden commands:

- Community activation has no bridge action. Download stores a private-cache
  copy. `can_activate` true in state does not enable an activation control or a
  download of that record.
- `play_workshop` is allowlisted, and the service rejects every launch because
  the current loader would change an installed game file. Play stays disabled.
  Favorites and library refresh remain available.
- `open_link` and `import_map` are not on the plugin bridge allowlist, so this
  menu does not offer them.
- Recorded ghost playback (`play_recording`, `ghost_control`, `stop_ghost`,
  `import_recording`) needs an active lesson and a saved recording. This menu
  exposes lesson help and training display only.
- Career creation, lineup edits, launcher choice, and install path stay in the
  existing career UI. Bot presets do not grant garage inventory.

## Evidence

`plugin/tests/native_career_layout_tests.cpp` is a synthetic contract test.
It covers normal and online passthrough, a live scope that goes online, stale,
unowned, or to another generation while the JSON nonce stays the same, the
seven-control map, required original consumption, control revisions for a
repeated favorite, match, Exit, and page choice, re-opening the same scope,
stale fixture and lesson ids, disabled community activation, the supported
actions above, bounded schedule, standings, squad, lessons, workshop, and
community lists, and unknown control and route ids.

The test does not start Rocket League, attach to a process, or send a bridge
command. Passing it does not prove that the game shows these labels, that the
adapter consumed the original action, or that the six routes are blocked.
Those checks remain outstanding for the binder on an owned offline session.
