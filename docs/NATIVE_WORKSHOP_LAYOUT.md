# Native workshop layout

The opt-in native movie can offer Play for one installed Steam workshop map. The choice is a `LocalWorkshop` effect. It carries the host's bound package, and it does not carry `play_workshop`, a console command, or a path on the movie wire. Default release stays off. `game_verified` and `production_allowed` stay false. Nothing here is a verified game launch.

`docs/NATIVE_WORKSHOP_LAUNCHER.md` describes the executor. This page describes the menu binding.

## What the movie sees

The click JSON stays five fields: `protocol`, `session`, `generation`, `revision`, `control`. Each published control stays six fields: `id`, `label`, `enabled`, `reason`, `stock`, `revision`. The protocol keeps the package path, content root, workshop id, nonce, and generation in its private signature so a same-label row with a different file is stale. Those fields are not copied onto the wire.

An enabled Play choice has an empty action and an empty payload. `supportedAction` still rejects `play_workshop`. A forged click that adds a path, an action, or any extra field is rejected before the layout accepts it.

## How a row becomes playable

`NativeCareerLayout::bindWorkshop` reads the bridge `workshop.items` array the Python library already publishes. Python was not changed. A row is bound only when all of these hold:

- `origin` is `steam_workshop`
- `installed` is true
- `workshop_id` is numeric
- `path` is a canonical package under `steamapps\workshop\content\252950\<workshop id>\`
- that content root is the Steam library of the verified game executable (`...\steamapps\common\...`)

A catalog row with `launch_id` is playable only when that id matches exactly one bound Steam row. The menu id stays the catalog id. The request path is the Steam package. Zero matches or several matches stay disabled with "Choose the installed map file." `local_import` stays "Imported maps cannot be played from this menu yet."

The executable's library is the initial limit. A path under another library is "This map is in another Steam library." An executable that is not under `steamapps\common` leaves every Play disabled with "This game's Steam library could not be confirmed." Root can review that limit.

With no bound context, the workshop page keeps the previous disabled list, including favorites and refresh. A bound context paginates valid rows by 8, scanning up to 512, so a map past the first 64 can be reached with "More maps" and "Previous maps". Favorites and refresh stay bridge actions.

Play is disabled, in plain language, when the session is busy, a map is already held, a package is still preparing, or the owned offline frontend is not ready. The status line uses the same sentences. Entering a map does not release its pin. A lost owned session or new bridge nonce cancels pending preparation without joining its worker on the game tick; an already-dispatched package remains pinned until plugin unload. Normal online handoff closes the owned offline process first.

## Host

`NativeMovieHost` passes the workshop context into open, publish, and select. On `LocalWorkshop` it calls the injected request callback and does not call the console. `MyCareerTraining` builds the context, calls `begin` from that callback, and calls `poll` from the game-thread tick. The only `executeCommand` for this route is the launcher callback, and only with the command the plan derived. The compiled-out trial does not construct the launcher.

Pins are copied into the scope only after `NativeMovieHost::verifiedBuild` has compared the running executable hash, BakkesMod version, and Psyonix build. An unverified host leaves those strings empty, so `prepare` refuses the request.
