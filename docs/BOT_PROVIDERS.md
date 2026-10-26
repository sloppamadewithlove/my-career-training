# Offline bot providers

The in-game provider selector changes the actual controller used by every bot
in the next career fixture. A selected unavailable provider stops with a clear
error; it never silently substitutes the experimental ground controller.

| Provider | Actual implementation | Formats | Difficulty meaning |
| --- | --- | --- | --- |
| Ground Specialists | Original MCT ground controller | 1v1–4v4 | Recruit level and difficulty tune ground decisions; no ranked claim |
| Necto | Original pretrained Necto TorchScript policy, CPU inference | 1v1–3v3 | Creator historically estimated around Diamond; current integration has no rank certification |
| Nexto | Original pretrained Nexto TorchScript policy, CPU inference | 1v1–3v3 | Creator historically estimated around GC1; current integration has no rank certification |

For a Diamond player, choose **Necto** to start evaluating a comparable learned
opponent or **Nexto** for a stronger challenge. These are historical estimates
from the [original creator's README](https://github.com/Rolv-Arild/Necto/tree/2e6ed7d6ed2b352e8ff529d4a12a0c9c70c28cca).
They are not a promise about current ranked play, specific mechanics, or this
build's observed in-game performance. Real Windows evaluation is still needed.

The learned policies are fixed pretrained models. Career XP is still saved,
but recruit role, XP and difficulty sliders do not retrain or change these
models. Neither model learns from the player's matches or training sessions.
No rank-labelled reskin of the ground controller is used.

## Reproducibility and license

Source and weights: `Rolv-Arild/Necto`, revision
`2e6ed7d6ed2b352e8ff529d4a12a0c9c70c28cca`.
The current [RLBot v5 port](https://github.com/VirxEC/NectoFamily) distributes
the same model bytes; this app adapts the original explicitly licensed source.

| Artifact | SHA256 |
| --- | --- |
| Necto | `137f94924afb0402af7ae9f12b7f2d7e47adff962afad4dbed7bf864c34c542b` |
| Nexto | `bf5343b5eeacac6bf7cdb75dac4a5c14ba0f94d820eae75f00a211b6119d69fa` |
| Original license | `1349a4b6148492b44f629e64eed676612e234fe9a839e4f3b277c1482c8849f1` |

Models and adapted observation/action code are a separate
**CC BY-NC-SA 4.0** component, attributed to Rolv-Arild and the RLGym/Necto
contributors. The project's rights notice and earlier MIT grants do not relicense these components or
grant commercial permission. Full license and attribution are shipped under
`bots/_vendor/` and `bots/resources/`.

Models are bundled, not downloaded during play. The build helper
`scripts/fetch_bot_provider.py --verify` checks the exact bytes without network
access. Without `--verify`, it can recover missing artifacts only from the
pinned source and only after checking their SHA256. Runtime refuses unknown
provider IDs, changed weights and missing licenses before loading TorchScript.
No arbitrary model import is exposed to users.

## Runtime contract

`bots.providers.provider_catalog()` returns capabilities and availability
without importing Torch into the visible process. `ensure_provider(id, format)`
rejects unsupported selections before a match. `create_controller(id, role,
level, difficulty, seed)` returns `step(frame, player_index, intents=None)`,
`reset()`, `manifest()`, `intent`, and `last_decision`, matching the ground
controller boundary. Necto and Nexto ignore role, level, and difficulty.

Normalized frames require observed standard-arena positions, velocities,
angular velocities, pitch/yaw/roll, boost amounts, jump/flip state, frame
number, and 34 boost pads with position and availability. RLBot v5 pad order is
mapped to historical RLGym order by position. Player indices remain stable;
the observation orders the controlled player first, then teammates, then
opponents. Each bot has its own observation and controller history; model
weights are shared read-only within the isolated worker. Inference uses CPU,
one Torch thread, and upstream 8-tick cadence. The upstream speed-flip kickoff
sequence runs only when the worker reports an actual Kickoff phase.

Use `is_demolished` for demolition handling and `is_kickoff` (or
`phase: "Kickoff"`) for kickoff handling. Terminal matches return neutral
controls. Time rewinds reset policy history. Malformed, unsupported or missing
telemetry raises a provider error instead of substituting a different bot.

The Windows package bundles CPU Torch and NumPy. `model_self_test()` loads the
verified models, warms the actual TorchScript operators, and performs CPU
inference on representative 1v1/2v2/3v3 observations. It must pass inside the
frozen Windows worker. Passing that check proves packaging and inference, not
Rocket League gameplay or bot rank.

## Additional providers

[Wisp v2](https://github.com/NicEastvillage/RLBot-Wisp-v2-py) is a candidate for
later evaluation: its creator documents 1v1/2v2/3v3 possession, teamwork and
aerial focus, with MIT terms plus a no-cheating restriction in the README.
Its current runtime also depends on RocketSim, collision data, NumPy, Numba
and Torch. It is not bundled or represented as installed in this build.
