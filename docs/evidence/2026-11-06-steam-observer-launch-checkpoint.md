# Steam observer and launch-mode catch-up — 6 November 2026

The 09:24:31 UTC active-session target elapsed while the chat remained active.
This is one late catch-up, begun at 09:29:02 UTC, 4 minutes 31 seconds later. The
next active-chat target is 10:14:02 UTC. There is no persistent timer or
unattended review claim. Documentation base: `cf8b5038787cd67d27e64e2edc80fa90885ece10`.

## Source review and launch evidence

- The default-OFF identity observer (`8b6b5bf`) and Windows directory-handle
  correction (`3b4f34a`, branch head `d64d5dd`) were independently reviewed and
  approved for an isolated identity observation. Review reproduced an ancestor
  junction swap race in the earlier adapter; the correction adds a Windows
  regression for that actual check/open race. This remains source/test evidence:
  the observer has not been loaded or executed live, and proves no EAC state,
  local plugin loading, MCT readiness or compatibility.
- The latest reported Bakkes-only standard Steam launch without `-rlbot` was
  inconclusive. Module access was unavailable and no fresh log was retained, so
  plugin-loaded state, EAC state and cause remain unknown. This is not proof the
  plugin is absent or present.
- Official [BakkesMod 2.0.78](https://github.com/bakkesmodorg/BakkesModInjectorCpp/releases/tag/2.0.78)
  lists RL2.78/BM229 and an RL2.78 compatibility update, released 20 October.
  This is later version-level metadata than BakkesMod's [28 April post-EAC notice](https://updater2.bakkesmod.com/articles/bakkesmod-eac.html),
  which predicted no support for game versions from that date onward. The newer
  metadata does not establish local plugin loading or compatibility with Steam
  build `26349479`.
- Rocket League's [official EAC article](https://www.rocketleague.com/news/easy-anti-cheat-comes-to-rocket-league-on-pc-today/)
  says turning EAC off permits third-party mods in Training and offline/LAN
  play. This EAC choice is distinct from [Steam Offline Mode](https://help.steampowered.com/en/faqs/view/0E18-319B-E34B-B2C8),
  which disconnects the Steam client from its network. The user prefers Steam
  online and permits gameplay offline only. The user has not answered whether
  to select `Without EAC` if the launcher presents it. Actual EAC state is
  unverified. No claim about local EAC state, plugin load or MCT compatibility
  is made here.

## Recovery and next gate

- The temporary config override was conditionally restored. Four missing backup
  saves were restored and changed/new saves were preserved. The whole profile is
  not proven unchanged.
- The test-started injector failed graceful close; only its PID verified as
  owned by that test was terminated. The exact test-config temporary remains
  because cleanup was blocked by automatic review with the reported reason
  `blocked by policy`. No further reason was given; cleanup was not broadened or
  retried.
- Before a live identity observation, establish the exact owned process identity,
  obtain a fresh short lease, stage the exact config and rollback, and keep normal
  MCT excluded. Only offline gameplay is permitted; keep Steam online as preferred.
  If the `Without EAC` launcher choice appears, wait for the user's answer before
  selecting. Record what is actually selected; do not infer EAC state. Review the
  exact observer output before any separate compatibility trial. Missing or stale
  output stays inconclusive.

## Process adjustment

For identity observers on Windows, regression-test the real directory-junction
swap between validation and open, and retain validated handles through use;
canonicalized path strings alone do not close that race. Keep process identity,
lease, config staging and rollback requirements explicit in the test card. When
module access or fresh logs are unavailable, record unknown state without a
causal guess. Keep the 45-minute active-review record to actual due/start times;
never imply that a timer ran independently of the active chat.

No game input, game launch or source edit was made for this documentation
catch-up. The exact temporary cleanup remains pending; no path, raw log, save,
account identifier or game asset is included.
