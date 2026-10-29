# Training cleanup and native clock observation

Two scoped DeepSeek builder proposals were independently reviewed by GPT-6 Luna
Max and integrated by main from base `d0278fa175257dfd3812b906b496ae7baabf7fa3`.

## Hidden-ball cleanup

A missing server/ball wrapper previously cleared the hidden-ball lease even
though the same actor could return. The helper now defers without callbacks when
either identity is zero. Nonzero replacement identities still discard the old
lease without writing to a replacement. Offline/replay deferral, external unhide
and failed-write retry behavior are preserved.

The augmented isolated C++ test failed with the old header and passed with the
new header (direct executable and CTest 1/1). It covers initially visible and
initially hidden actors across full and partial zero identities, and verifies
that absent-wrapper callbacks are never invoked. This proves the helper fix;
it does not prove that this was the sole cause of the owner's disappearing-ball
report. Full native integration and actual game acceptance remain pending.

## Native clock telemetry

`normalized_packet` now exposes RLBot b56 `game_time_remaining`,
`is_unlimited_time` and `is_overtime`. Existing elapsed `time` remains unchanged.
Older synthetic packets without the fields report null rather than invented
values. No match-clock mutation or training rule changes are part of this patch.
The fields make the next native-timer probe observable; they do not implement
the requested per-shot native countdown by themselves.

Independent checks on the immutable proposal: 14 adapter contract tests passed,
110 worker/reference-capture tests passed, and diff whitespace validation passed.
The generated b56 FlatBuffer round-trip preserves remaining 185.5 independently
of elapsed 9.5 and both native flags.

## Actual provider receipts

- Visibility builder: `deepseek-v4-1-flash-1017`, finish `stop`, 1,254 input and
  3,637 completion tokens, 15.875 seconds, provider cost USD 0.0023703.
- Clock observation builder: same model, finish `stop`, 8,202 input and 1,691
  completion tokens, 5.922 seconds, provider cost USD 0.0022449.

Raw receipts and copied test inputs remain private. GitHub owns the integrated
source and this sanitized record. No installed game files were changed by these
patches; the currently open game is the standard reference session.
