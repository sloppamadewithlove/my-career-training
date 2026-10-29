# Background diagnosis: 29 October 2026

## Scope and ownership

The owner is using the PC. Automated game input, window focus, screenshots, game
process attachment and live gameplay tests are suspended. Ordinary Steam Rocket
League remains open; it is not the My Career candidate. The rejected replacement
session was normally closed, and the BakkesMod injector exited before the standard
reference session started. Neither target training pack has been acquired yet.

Research compares exact mod source `7ba05345cb2451d95dbbde64301d7c0ee4024d13`,
SDK declarations `479e8f571cf554b25f4eeb64d611dec4133edcaf`, installed SDK SHA-256
`421df9b1ccb65cc0e316189d824f25f0d00bb05352e0ea4e5219e7f400ec8813`, and the prior
[eight-hour campaign](https://github.com/sloppamadewithlove/my-career-training/tree/f81227462aaad405f00dcacb62a61fa942fc9f95/research%20to%20be%20applied).

## Actual workers and limits

Two independent provider workers report model `deepseek-v4-1-flash-1017` and make
read-only evidence/source tool calls. Their scopes are training reset/timer/goal
lifecycle, and Garage/Workshop/plugin lifecycle. Both obtained actual REA export
evidence `ev_1ec56e5d3776f7c42066cf5c187c1fc813c153deeaed91f2614766298f1c6796`
(8,801 exports); the training worker also has retained function-body dossiers.
Exports alone never establish behavior. No new whole-game decompilation or live
process inspection is claimed.

Campaign planning began at 08:16 UTC; the long-running workers started later after
setup. The bounded deadline is **10:16:20 UTC / 06:16:20 America/New_York**. Each
worker has a 120-provider-call ceiling and 6,500 output-token ceiling per call;
provider failure, truncation and incomplete output are recorded, not accepted.
These are research workers, not unattended code integrators. Private raw receipts
stay private; main publishes reviewed findings here. This document records an
observed run, not a promise that a process survives PC sleep or shutdown.

Three GPT-6 Luna Max agents completed public-source/exploration passes. Two are
now independently reviewing the DeepSeek conclusions against complete callers and
helpers. Root owns integration. No DeepSeek code-building job was dispatched for
this background-only diagnosis step; previous builder receipts are separate.

## Confirmed source gaps

1. **Mods activation is not implemented for production.** Download receipts say
   `downloaded_not_enabled` and `can_activate=false`; the native browser disables
   Enable. Production profiles are empty. The separate pinned development trial
   does not make general Mods enable/disable work.
   Sources: `src/my_career_training/community_plugins.py:142`,
   `src/my_career_training/native_community.py:25`,
   `plugin/include/NativeCareerLayout.h:1815`.
2. **The development plugin lifecycle lacks an app-issued unload confirmation.**
   The host executes `plugin load`; shutdown restores held values and releases its
   staged-file pin, but does not unload the separately loaded plugin. File cleanup
   waits for game exit. Implementing the owner's requested toggle needs explicit
   ownership, unload, loaded-list confirmation and subsequent file cleanup.
   Sources: `plugin/include/NativeCommunityHost.h:313` and `:613`,
   `src/my_career_training/community_session.py:93`,
   `src/my_career_training/native_community.py:297`.
3. **Workshop launch is not verified map entry or return.** The normal Python
   catalog cannot launch; a development native route dispatches `load_workshop`.
   Callback return is expressly not map-arrival proof. A complete player workflow
   still needs arrival, playable state, Return and restoration evidence.
   Sources: `src/my_career_training/workshop.py:162` and `:247`,
   `plugin/include/NativeWorkshopLauncher.h:615`,
   `docs/NATIVE_WORKSHOP_LAUNCHER.md`.
4. **Gold still has two rejected feeds, not twelve reference-derived challenges.**
   The three old cached packs are not Poquito or Skogur. Public metadata and SDK
   exports cannot supply their missing geometry. Acquiring the two packs remains
   a later normal-game step when the owner returns input control.

The requested outcome of working Workshop and Mods is already decided. These are
implementation gaps, not reasons to ask whether a download-only library suffices.

## Research quality correction

A preliminary DeepSeek result incorrectly said keyboard polling was XInput-only.
Main rejected it: `plugin/src/MyCareerTraining.cpp:840` explicitly reads
`GetAsyncKeyState(VK_UP)` and the other arrows. An empty bound notifier is not proof
that the keyboard route is dead. Reviewer tasks now require the whole producer /
consumer chain and relevant helpers before accepting a defect.

The worker evidence adapter was improved to prioritize retained function bodies
over summary views, search exact source before guessing line numbers, share
verified cross-agent findings, and admit only bounded read-only tools. Follow-up
questions must be answerable with available evidence, rather than repeatedly
requesting an unavailable decompiler or reconfirming owner decisions.

## Hypotheses awaiting proof

- Garage clears focus callbacks on customization/preset controls every frame;
  controller navigation may be affected, but this is not an observed failure.
  Source: `native_ui/MctMainMenuScreen.as:101`.
- Quit relies partly on plugin unload/scope loss for cosmetic restoration. A
  graceful-close timeout needs examination of the actual cosmetic helper and
  cleanup path. Returning to the hub is not automatically leaving My Career.
- Native game-clock countdown, expiry/ball removal, physical Up and goal-to-next
  challenge remain unverified. Tests of synthetic metadata are not live proof.

## Relevant public implementation evidence

[TeamTrainingPlugin](https://github.com/daftpenguin/teamtrainingplugin/blob/808adb9816a2323d4b13c96f1e372dfbc185ade4/TeamTrainingPlugin/TeamTrainingPlugin.cpp#L3383)
hooks native custom-training round reset and advances drills while converting a
pack that is already open. It is not an offline pack downloader.
[CustomTrainingUnlimitedTimePlugin](https://github.com/tedle/CustomTrainingUnlimitedTimePlugin/blob/091d6a55f10f3ddd5434a714dfb96fc7c62b8bbd/CustomTrainingUnlimitedTimePlugin/CustomTrainingUnlimitedTimePlugin.cpp#L4)
sets the native unlimited-time flag after StartPlayTest in custom training. That
is not proof of finite Soccar expiry behavior.

## What the heartbeat actually improved

The scheduled worker authored the evidence privacy scanner and tests in draft
PR #11. Main independently checked 25 privacy tests and aligned that branch with
the current source. The checked combined head is
`d2e7beb74ee5aea1a06c2cd4c35832dd83f5c8db`; native Windows CI passed there and at
PR #10 head `7ba0534`. Vercel Preview Comments checks passed; that name alone is not
a claim that a product deployment was validated.

Main separately repaired the saved-result Calibration bypass and changed both
Windows CI concurrency layers to preserve an active build. Those changes were
not authored by the scheduled worker. No heartbeat or passing CI has established
a working twelve-shot Gold pack, native timer or complete mod lifecycle.
