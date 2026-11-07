# Session handoff: flip-reset ghost, Training and workflow

The owner stopped the persistent goal on 7 November 2026. Do not start another
game, schedule an unattended job, or resume the goal merely because this handoff
exists. The owner asked for a simpler process, a real translucent-looking ghost
that demonstrates a flip reset, working Training, and an audit of implicit state
machines. **The ghost has not been seen in-game, no successful demonstration has
been obtained, and Training exit has not been verified on the updated game.**

## What the owner wants

- A flip-reset lesson first: a ghost car approaches the ball, touches it with
  its wheels/underside and demonstrates an actual successful reset. The ghost
  and its faint visual ball share one fixed-start timeline; they must never
  collide with or change the player's car, ball, scoring or attempt. Down
  toggles the ghost; turning it off hides its controller display too.
- The owner cannot personally perform the flip reset and asked us to find
  another way. An installed bot is an experiment, not a demonstrated solution.
  The owner does not have a Ballchasing account. Never request credentials or
  describe a video or reconstructed motion as an observed successful trace.
- Retain native Training menus/behavior and verify its exit repair. Earlier
  sessions reached native Training and verified Pause/Resume; End Training
  exposed a stuck results screen. A repair was built before a game update but
  has not been tested against the updated executable.
- The owner allows a controlled **offline** test using Steam's official
  anti-cheat-disabled option, with Steam online and saves preserved. They gave
  permission for an owned test and for the previously identified interactive
  PowerShell to remain. Revalidate ownership, current processes and scope for
  every new test; do not ask the same permission again.

## Where the work lives

GitHub is the source of truth; recheck branch heads and PR state before editing.
At handoff:

| Artifact | Exact head | Meaning |
| --- | --- | --- |
| [Draft PR #10](https://github.com/sloppamadewithlove/my-career-training/pull/10) | `282db0d17e9f8c5ad304b0206ee375e9f54a2e16` | Older draft; not the newer ghost or state-machine branches. |
| [Ghost and bot-capture source](https://github.com/sloppamadewithlove/my-career-training/tree/feat/flip-reset-native-integration-2026-11-06) | `26a8a5461c81f1e2766baf2abb5c9c0e82fc5c65` | Independently reviewed source: paired car/ball playback, native screen-space car-shaped renderer, toggle/control path, and a private bounded installed-bot capture experiment. No real reset trace, installed build or live ghost. |
| [State-machine hardening](https://github.com/sloppamadewithlove/my-career-training/tree/feat/state-machine-hardening-2026-11-07) | `331829c41049151105c78cdaad0a60ac1969d2d8` | Includes the ghost source plus reviewed Retry/Stop ordering and plugin recovery-journal fixes. Not merged or live-tested. |
| [Coordination and evidence](https://github.com/sloppamadewithlove/my-career-training/tree/docs/flip-reset-priority-2026-11-06) | See branch head containing this file | Current handoff and workflow history; documentation branch, not a release. |

The original working checkout contains substantial pre-existing uncommitted
changes. Preserve them; use an exact-base isolated worktree. The paused session
also left **local-only, unreviewed UI work**: the setup/controller branch ending
at `f2f223c` was individually reviewed, but its combined test run hit a native
Qt garbage-collection crash. A follow-up candidate `f41b905` was built and
tested locally but was not independently reviewed or published. Its exact
native corruption cause is unknown. Do not silently lose, publish, or merge it;
check local worktrees and complete independent review before using it. A separate
native state audit found no validated defect in its inspected slice.

## Evidence and limits

- One native integration checkpoint at `59504d6` built a Release plugin against
  the pinned SDK and passed 46 CTests; 214 focused Python checks passed. Later
  Python deadline corrections were independently reviewed; the earlier DLL is
  not a later packaged/loaded candidate. The screen-space proxy has no world
  depth test and its in-game opacity, clipping and appearance are unverified.
- Steam's UI actually offered the official anti-cheat-disabled choice. The owned
  game launched with the expected observer arguments and executable identity;
  BakkesMod core and SDK modules loaded and matched their reviewed files. The
  game was only observed at its title screen. The console opened, but fast text
  entry dropped a letter and a correction landed at the end. Neither incorrect
  command was submitted; the observer never loaded. Do not repin the existing
  old-build guard merely because the new executable shares a version number.
- The test was closed; Steam's original normal launch choice and empty launch
  arguments were restored and verified. Plugin configs match their retained
  baselines, and the staged observer and active marker were removed. Five
  previously present save files, including the original profile save, were
  missing after startup; verified private baseline bytes were restored with
  CreateNew and independently checked 5/5. At that check the identified roots
  had zero missing, 12 changed and two new entries. Restored metadata differs,
  the newer backup was preserved, Steam Cloud remains enabled, and full profile
  completeness and future cloud writes were not proved. Revalidate current
  state; do not blindly overwrite any save or publish private paths or data.
- The user requested all implicit state machines be found and fixed. The audit
  found and reviewed real Retry/Stop and deferred recovery-journal defects;
  fixes are on the hardening branch. Setup and controller findings are in the
  local-only UI candidate above. The inventory is bounded: it does not prove all
  state machines or all defects have been found.
- A public replay page reported flip-reset statistics, but anonymous file
  download returned an HTML login response, not replay data. The owner has no
  account. Public checkpoints can supply a starting setup, not a recorded ghost.
  Videos are useful for visual reference; synchronized game/replay data and
  permission are still needed for a real demonstration. Reconstructed inputs
  must remain labeled as estimates.

## Best next sequence

1. Recheck current GitHub heads, the restored saves, Steam/launcher state,
   running processes and all existing recovery journals. Keep private copies and
   avoid overwriting current or cloud-created data. The previous test left a
   private HTTP login response after an automatic review rejected its deletion;
   preserve it and do not retry or broaden that cleanup.
2. Use one bounded visible goal: get the reviewed ghost rendering in an owned
   offline game from a clearly labeled test trace, then prove toggle and
   non-interference. This is a display test only; it is not a real flip-reset
   demonstration. Establish compatibility with the updated game first. Prefer
   the existing loader and a paced, visually verified console input route; avoid
   another layer of general-purpose testing machinery.
3. Obtain a permitted actual successful reset with the installed bounded bot
   experiment or a usable replay/reference that does not require the owner to
   perform the maneuver. Validate actual car/ball relationship, reset evidence,
   timeline gaps, provenance and distribution rights before shipping it.
4. Build and test one exact integrated candidate, including native Training
   End/Return and normal Career regressions. Inspect in-game rendering, toggle,
   resets and score/ball/car isolation. Report what happened and restore test
   settings and profiles before moving on.
5. Continue the state-machine audit by actual producer-to-consumer transitions;
   review the local UI/Qt lifetime candidate and inspect unexamined owners.
   Fix demonstrated failures, not every flag merely because it stores state.

The owner-selected builder routes are DeepSeek V4.1 Flash 1017 max and GPT-6.1
Sol high; independent code review is GPT-6 Astra max. Avoid unnecessary agents,
repeated full test runs and new safety frameworks when an existing reviewed path
does the job. The requested 10-minute/45-minute checks were not installed as
recurring app schedules; active-session checks were sometimes late. Document
actual checks and improvements rather than claiming background timers ran.

See [live test and recovery evidence](2026-11-07-live-observer-workflow-review.md)
and [ghost integration workflow review](2026-11-06-ghost-integration-workflow-review.md).
