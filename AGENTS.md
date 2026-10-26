# My Career Training

Windows offline career mod for the player's installed Rocket League, using native menus, BakkesMod and RLBot v5. GitHub is canonical; Cursor Origin is an inbound mirror. Start at docs/PROJECT_STATUS.md and docs/README.md; the product specification is docs/BUILD_SPEC.md. The native candidate pipeline is distinct from the older overlay bundle.

Keep real-game evidence distinct from contract tests. Never fabricate game results, teaching references, ranked bot capability, or launcher verification. Do not ship proprietary game assets. Bots run only in the supported offline environment. Preserve saves and normal human controls.

Python 3.12, PySide6/QML, isolated worker. All mutable data is per-user AppData. Frozen worker must use the executable's explicit --worker mode. Tests run with `uv run pytest`; packaging is Windows only. Read docs/INTEGRATION_CONTRACT.md before editing shared boundaries. Parallel workers own distinct files and must preserve each other's work.

Players open one MyCareerTraining executable or shortcut. Helpers belong in _internal and must not present a terminal. Never commit private logs, saves, user paths, account IDs, environment files, credentials or game assets. Read docs/REPOSITORY_PRIVACY.md before publishing evidence.

For implementation/test coordination read docs/DEVELOPMENT_WORKFLOW.md. For owned Windows game-state navigation use skills/my-career-training-testing/SKILL.md. Keep one game-input owner; recorded source, native, frozen, installer and gameplay evidence are separate. Check current status before reusing a historical route.

Latest owner roles (26 October): main interviews, defines contracts and independently reviews/integrates; GPT-6 Luna max handles research, exploration and testing; Claude Opus 5.5 high handles visual design only. DeepSeek V4.1 Flash 1017 through RunInfra is the preferred implementation builder; GPT-5.6 Sol high through Codex CLI and Grok 4.7 high through Cursor CLI are additional builders selected by problem depth. A bounded authenticated RunInfra request returned the intended model; credentials remain protected outside the repository. Other agents use existing login sessions without additional API keys. Follow docs/DEVELOPMENT_WORKFLOW.md and docs/TRAINING_WORKSHOP_DIRECTION.md. The owner has resumed building and confirmed the other demo session finished; establish fresh ownership before game input.

Strict owner correction: Opus is DESIGN ONLY. It supplies visual mockups, layout/appearance specifications and design reviews. DeepSeek, Sol and Grok own implementation, including HTML/CSS/JavaScript previews, input behavior, bug fixes and builds. Do not assign code authoring, scripts, compilation or behavior fixes to Opus, even when the artifact is called a preview. Main coordinates, reviews and sends incorrect builder work back for correction; Luna researches and tests. This overrides older design-engineer/code-authoring assignments.
