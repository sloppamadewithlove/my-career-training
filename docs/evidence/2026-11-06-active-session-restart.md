# Active-session restart checkpoint — 6 November 2026

The prior active target was 05:01:00 UTC. It passed while the chat was idle;
there was no persistent timer, so this is not recorded as an actively missed
review. Active work resumed at 05:30:22 UTC. The next active-chat target is
06:15:22 UTC. No unattended timer or review is claimed. Documentation base:
`f27f7c5176c5940a7f8d48af0e133c0c15657905`.

## Current evidence

- Exact `bd9336d869363c51375bb9c35f0ae351aea74bb0` remains the packaged native
  pause candidate. Its 1,659 passed/15 skipped, 38 plugin and 13 launcher CTests,
  Return fixture, frozen smoke, and staged-to-frozen pause-ABC hash match are
  already recorded. No build is repeated for this restart.
- The live handoff had reached stock Play before focus was lost. The helper
  refused the next input; no click was dispatched. User has said continue.
  Read-only process/foreground verification is underway, with no new input sent.
  Native pause remains unverified.
- The experimental drawing branch head `8759a83` documents source
  commit `a983c6183c7b7f9a1cefbad05d0da39d01791912`: an independently reviewed,
  pure diagnostic frame-preparation core. Its dedicated C++ check passed 1/1;
  it registers no drawable and has no renderer, live rendering or ghost. Full
  plugin/package and live checks remain unrun for that experiment.

## Restart practice

On resuming after idle, record the actual restart time and call it a restart,
not a missed active review. Start with read-only process/foreground verification;
send no input until the same game and foreground are confirmed. Reuse `bd9336d`
build, smoke and hash evidence while its inputs are unchanged. Native pause still
needs a live result on that candidate. Keep the drawing experiment separate from
renderer or ghost acceptance. No game input, build or source change was made for
this documentation checkpoint; no private paths, save contents, account data,
raw logs or game assets are included.
