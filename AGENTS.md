# My Career Training

Windows desktop companion for the player's installed Rocket League, using RLBot v5. GitHub is canonical; Cursor Origin is an inbound mirror. The source specification is docs/BUILD_SPEC.md.

Keep real-game evidence distinct from contract tests. Never fabricate game results, teaching references, ranked bot capability, or launcher verification. Do not ship proprietary game assets. Bots run only in the supported offline environment. Preserve saves and normal human controls.

Python 3.12, PySide6/QML, isolated worker. All mutable data is per-user AppData. Frozen worker must use the executable's explicit --worker mode. Tests run with `uv run pytest`; packaging is Windows only. Read docs/INTEGRATION_CONTRACT.md before editing shared boundaries. Parallel workers own distinct files and must preserve each other's work.
