# Gold reference catalog candidate

Source base: `440f7ce8a03a8ebfedff2f64036a065cf0d6aeae`. This commit replaces
the two rejected provisional Gold feeds with twelve reference-derived shots.
This is implementation and source-test evidence, not owner gameplay acceptance.

Both references were downloaded through ordinary Rocket League Custom Training.
The read-only decoder verified the CRC and unchanged input hash. Ground Shots
by Poquito (`6EB1-79B2-33B8-681C`) has 50 rounds, each with a ten-second limit;
Powershot Practice by Skogur (`C9E4-0F05-B71A-C322`) has 12 five-second rounds.
Private pack SHA-256 values are respectively
`b0279aeef10985f661d55372c2e60b7d1bb17ef511ff9b6b3e0272db273d2948` and
`0df420917471ccc4f45f99588e558f9ee1720d0e9d79795855e5136edde78aa0`.
Raw pack binaries, actor identifiers and account-bearing captures stay private.

The selected order interleaves Poquito shots 1, 3, 7, 8, 9, 12 with Skogur shots
1 through 6. Numeric ball position, pitch/yaw, speed and time limit are retained;
car placement uses the grounded DynamicSpawnPointMesh transform. The separate
IsPC actor's role is not established here. The candidate adapts these exercises
to the mod's designated stadium and adds one ground keeper. It does not assert
that the original packs contain bots or that their creators certified Gold rank.

Gold navigation now wraps twelve IDs; other ranks retain their two provisional
IDs. The original first two identifiers remain valid for saved preferences.
The catalog data adds no dependency or binary asset. Source speeds range from
800 to 2600 game units/second; no additional old Gold multiplier is applied.

Independent GPT-6 Luna Max review matched all twelve records to checked input
geometry. Exact candidate checks: 265 passed across bridge, storage, scenarios,
setup and reference catalog; four additional Gold 12-to-1 saved-event tests
passed, including stale/missing/mismatched session rejection. Main reviewed the
DeepSeek rank-aware setup patch and integrated the companion catalog/bridge code.
DeepSeek reported 1426 input / 2113 completion tokens, 4.953 seconds and $0.0014817.

Native reference observations: before movement, Skogur's top-left shot timer
remained at 0:05. After a short forward input it counted down; a captured 0:00
frame had no ball. Later captures showed a later shot; the exact cause/timing of
that transition is not established by the sparse captures. The reference game
was closed normally before candidate compilation. The mod is not yet running
this source.

Blocking live work: the engine assumes a pre-bounce confirmation packet, but
Poquito shots 3, 7 and 8 can reach the floor within 32ms. An independent synthetic
reproduction rejected their first post-bounce sample despite continuous cadence.
The rebound coefficient in that test is illustrative, not a native-physics
measurement. Preserve reset validation while repairing that path. Also prove
Up retry, timeout ball restoration, actual native countdown, goal/Left/Right
transitions and gameplay usefulness before asking the owner to accept this pack.
