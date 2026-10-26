# My Career Training

Windows offline career mod for the player's installed Rocket League, using native menus, BakkesMod and RLBot v5. GitHub is canonical; Cursor Origin is an inbound mirror. Start at docs/PROJECT_STATUS.md and docs/README.md; the product specification is docs/BUILD_SPEC.md. The native candidate pipeline is distinct from the older overlay bundle.

Keep real-game evidence distinct from contract tests. Never fabricate game results, teaching references, ranked bot capability, or launcher verification. Do not ship proprietary game assets. Bots run only in the supported offline environment. Preserve saves and normal human controls.

Python 3.12, PySide6/QML, isolated worker. All mutable data is per-user AppData. Frozen worker must use the executable's explicit --worker mode. Tests run with `uv run pytest`; packaging is Windows only. Read docs/INTEGRATION_CONTRACT.md before editing shared boundaries. Parallel workers own distinct files and must preserve each other's work.

Players open one MyCareerTraining executable or shortcut. Helpers belong in _internal and must not present a terminal. Never commit private logs, saves, user paths, account IDs, environment files, credentials or game assets. Read docs/REPOSITORY_PRIVACY.md before publishing evidence.

For implementation/test coordination read docs/DEVELOPMENT_WORKFLOW.md. For owned Windows game-state navigation use skills/my-career-training-testing/SKILL.md. Keep one game-input owner; recorded source, native, frozen, installer and gameplay evidence are separate. Check current status before reusing a historical route.

Latest owner roles: main interviews, defines contracts and independently reviews/integrates; GPT-6 Luna max handles research, exploration and testing; Claude Opus 5.5 high handles in-game and website design; DeepSeek V4.1 Flash 1017 through RunInfra is the preferred builder for implementation and hard problems. Provider documentation confirms the endpoint/model ID; private credential setup and an actual request remain pending, so do not claim the builder is connected. Use existing authenticated sessions for other agents, with no additional API keys. Follow docs/DEVELOPMENT_WORKFLOW.md for evidence and credentials, and docs/TRAINING_WORKSHOP_DIRECTION.md for the latest product choices. HTML previews precede owner selection and native UI implementation. Do not interact with the game while another session owns the demo recording.

Strict owner correction: Opus is DESIGN ONLY. It supplies visual mockups, layout/appearance specifications and design reviews. Main and DeepSeek own implementation, including HTML/CSS/JavaScript previews, input behavior, bug fixes and builds. Do not assign code authoring, scripts, compilation or behavior fixes to Opus, even when the artifact is called a preview. Main may build and remains responsible for reviewing DeepSeek's changes; Luna researches and tests. This overrides older design-engineer/code-authoring assignments.
