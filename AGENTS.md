# My Career Training

Windows offline career mod for the player's installed Rocket League, using native menus, BakkesMod and RLBot v5. GitHub is canonical; Cursor Origin is an inbound mirror. Start at docs/PROJECT_STATUS.md and docs/README.md; the product specification is docs/BUILD_SPEC.md. The native candidate pipeline is distinct from the older overlay bundle.

Keep real-game evidence distinct from contract tests. Never fabricate game results, teaching references, ranked bot capability, or launcher verification. Do not ship proprietary game assets. Bots run only in the supported offline environment. Preserve saves and normal human controls.

Python 3.12, PySide6/QML, isolated worker. All mutable data is per-user AppData. Frozen worker must use the executable's explicit --worker mode. Tests run with `uv run pytest`; packaging is Windows only. Read docs/INTEGRATION_CONTRACT.md before editing shared boundaries. Parallel workers own distinct files and must preserve each other's work.

Players open one MyCareerTraining executable or shortcut. Helpers belong in _internal and must not present a terminal. Never commit private logs, saves, user paths, account IDs, environment files, credentials or game assets. Read docs/REPOSITORY_PRIVACY.md before publishing evidence.
