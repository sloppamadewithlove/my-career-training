# Gold playtest and manual retry repair — 29 October 2026

## Exact candidate and scope

Candidate `e845bf9fe4697a87e5cf693432df195268bb0647` was built from the
GitHub revision and loaded into an owned offline session with a copied profile.
The operator was the main agent; generated keyboard input is not physical
controller or owner acceptance. The game was closed normally after the test.
Windows CI passed; local native checks passed 37 plugin and 13 launcher cases.

## Observed behavior

- The native Training browser opened Power Shots, its rank selector, and Gold.
- All twelve challenge indexes and the 12-to-1 boundary were reachable. Left
  moved from challenge 3 to 2. Most recorded starts took approximately 0.5–0.6 s.
- A generated Up press after timeout started a fresh attempt. With automatic
  retry disabled in the copied profile, timeout held the attempt and hid the ball.
- Challenge 5 interrupted during reset confirmation. At the first observed
  packet, 33.325 ms after placement, the ball had bounced. Horizontal velocity
  differed by 189.516 units/s; position differed by only 1.593 units horizontally.
  The reset helper allowed vertical rebound but rejected floor friction. Car
  position and velocity passed their unchanged tolerances in that sample.
- The native match clock still counted upward; the separate lesson overlay
  counted down. The explicit native-clock probe did not establish a change.
- Arrow polling also triggered lesson retry while the BakkesMod console was
  open. The later navigation loop ran after visually verifying console closure.

No human-scored goal transition, physical controller, final difficulty quality,
or native timer acceptance is claimed. Private screenshots/logs remain private.

## This change

Power Shots now waits for manual retry after timeout even when an old saved
preference requests automatic retry. The engine validates preference types
before normalizing; the bridge rejects explicit enable requests before save,
normalizes outgoing preference maps, and projects the effective setting without
mutating the saved document. Both settings surfaces omit the unavailable toggle.
Other lessons retain their existing retry behavior. Goal advancement is separate.

The opt-in clock probe now logs eligibility flags and refusal reasons without
session identifiers, to make the next runtime investigation actionable.

Independent Luna review caught and corrected a saved-preference edge case:
accepted empty/scalar values must be normalized before view projection. The
seven focused new cases pass; the broader worker/bridge/floor suite passes
187 checks. The full Python suite passes 1598 checks with 15 skips. This repair
has not yet been loaded into the game.

## Next acceptance

Repair bounded floor-contact reset verification, block lesson input while other
BakkesMod UI captures it, rebuild a coherent candidate, and verify the native
clock probe. Native zero behavior and scored-goal advancement remain open.
