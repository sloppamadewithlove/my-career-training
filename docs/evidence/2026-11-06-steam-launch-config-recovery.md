# Steam launch and configuration recovery checkpoint — 6 November 2026

The active-session review targets at 07:47:15 and 08:32:15 UTC elapsed while the
chat remained active. This is one late catch-up, started at 08:39:31 UTC; the next
active-chat target is 09:24:31 UTC. There is no persistent timer or unattended
review claim. Documentation base: `0108312a889fb3653a0ec98118cbd70497fa9355`.

## Launch evidence and limits

- Steam build `26349479` and executable identity were read in the previous
  checkpoint. The current report says a standard Steam launch without `-rlbot`
  was inconclusive; module enumeration was denied, so plugin-loaded state remains
  unknown. This does not establish plugin absence or a cause. Candidate `9ee0c33`
  itself was not launched after the update.
- Keep standard Steam, prior `-rlbot` testing, and Rocket League's official No
  EAC route separate. The user did not authorize Steam offline/No EAC changes;
  none were made.
- The official [BakkesMod 2.0.78 release](https://github.com/bakkesmodorg/BakkesModInjectorCpp/releases/tag/2.0.78)
  identifies RL2.78/BM229 and describes an RL2.78 compatibility update. This is
  a positive version-level signal against the older [BakkesMod EAC notice](https://updater2.bakkesmod.com/articles/bakkesmod-eac.html),
  not proof that this local plugin loaded or that Steam build `26349479` maps
  exactly to RL2.78. Rocket League's [official EAC article](https://www.rocketleague.com/news/easy-anti-cheat-comes-to-rocket-league-on-pc-today/)
  describes the separate official option; no such option was changed here.

## Recovery and next work

- A temporary config override was conditionally restored to its original value.
  Four backup saves were restored, and one changed/new save was preserved. This
  does not establish that the whole profile is unchanged.
- The test-started injector failed graceful shutdown. Only the PID verified as
  owned by that test was terminated. Cleanup of the exact test-config temporary
  was blocked by automatic review with the reported reason `blocked by policy`;
  the temporary remains. No more specific review reason is known, and cleanup
  was not broadened or retried.
- A builder is preparing an isolated, default-OFF, identity-only probe. It has not
  been launched and provides no new runtime proof. Before any later live test,
  verify the exact installed executable identity and launcher/plugin capability;
  do not infer compatibility from file version, package hashes or release labels.

## Process adjustments

- Run config override/restore helpers first on disposable config data; compare
  preflight and changed/new save inventory, restore originals conditionally, and
  preserve changed data. Keep cleanup limited to artifacts verified as test-owned.
- Keep `-rlbot`, standard Steam, and official No EAC routes explicit in records.
  Treat denied module enumeration as unknown loaded-plugin state, without an
  inferred cause. Do not change Steam launch settings without authorization.
- Bound builder/process waits and continue independent work. If several active
  review targets elapse, log one catch-up with all due times, act at that natural
  boundary, and derive the next target from its actual start. Never imply timers
  or monitoring continued while idle.

No game input, game launch or source change was made for this documentation
catch-up. No account identifiers, private paths, raw logs, saves or game assets
are included.
