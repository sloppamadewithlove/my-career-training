# Reset confirmation and native clock probe

Base: `5258ab392c56dcf7cdea07b284350566f4c55fc5`. No live acceptance is claimed.

The first confirmation packet may already follow a floor bounce for three of
the twelve Gold shots. The old verifier extrapolated an unbounced vertical
velocity and rejected those samples. The new exception is limited to the first
50ms, a downward launch close to the floor and a predicted floor impact. It
retains horizontal position/velocity, car, bot and cadence checks. A coupled
vertical energy cap permits a six-unit/second integration allowance. The review
rejected an earlier independent 40-unit vertical allowance; the corrected version
rejects even a seven-unit excess and excess height. Live floor friction is still
unmeasured and may require a different solution; no global tolerance was widened.

The development movie candidate gains an explicit `mct_probe_training_clock`
command. It changes the native clock to 90 seconds for at most five seconds,
then restores the saved time/unlimited flag. It never arms automatically. It
requires the owned offline active Power Shots session, current attempt, no
reference capture, a nonempty native match GUID and both native/RLBot unlimited
observations. The lease binds process, session, bridge nonce, event and match GUID.
Cleanup never writes online, into replay or a replacement match. Missing wrappers
defer cleanup. Empty stale bridge state can restore only the same process/event/
GUID; a present mismatched session detaches without writing. Failed arm readback
immediately attempts rollback; failed restoration retains the lease for retry.
Native remaining/unlimited/overtime fields now reach worker telemetry.

Validation on the combined source candidate:

- Full Python suite: **1591 passed, 15 skipped**, 162.41 seconds.
- Independent final floor-reset delta: **15 passed**; review reproduced acceptance
  of ordinary rebounds and rejection of excessive-energy samples.
- Independent native probe harness: **11 fake-wrapper cases passed**, compiled
  with MSVC 19.44/C++17. It executes the extracted method and covers identity
  changes, stale cleanup, NaN, failed flag writes and rollback retries.
- Independent adapter/worker/bridge checks: **179 passed**, 21.22 seconds.
- Native SDK compilation passed before the final small rollback/stale-state delta;
  the complete GitHub candidate must be rebuilt before launch.

DeepSeek's three-field telemetry patch completed with 356 input / 606 completion
tokens, 2.781 seconds and $0.000417. Its separate full native-method request
exhausted 5500 completion tokens in reasoning and produced no code; main authored
the method, then Luna found and verified the corrected failure paths. Do not count
that truncated request as delivered implementation. Future builder requests should
stay bounded to concrete source edits rather than full multi-state methods.

Remaining proof: observe the actual native countdown and independent RLBot clock,
confirm snapshot restoration, then investigate zero expiry separately. A successful
90-second probe does not certify native training HUD parity or safe zero behavior.
Also exercise all twelve live resets, goal progression, Up and Left/Right controls
before owner playtesting. The prior rejected build remains rejected.
