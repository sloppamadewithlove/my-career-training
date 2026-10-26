# My Career Training

Windows offline Rocket League career and scenario-training mod. GitHub is canonical;
Cursor Origin is a mirror. Start with [current status](docs/PROJECT_STATUS.md) and
[task board](docs/NEXT_TASKS.md), then only the relevant [blueprint](docs/BUILD_SPEC.md)
section. [Training/browser contract](docs/TRAINING_WORKSHOP_DIRECTION.md) owns that
product detail. Archived handoffs and dated receipts are evidence, not current orders.

Before a broad new build, establish the intended player outcome and ask only unresolved
material questions. Reuse confirmed decisions. Apply [the universal workflow](docs/DEVELOPMENT_WORKFLOW.md)
to every player-facing function. That file owns model roles, assignments, review,
failure and cost rules. Multiple scoped DeepSeek builders; Luna independently researches
and tests; Opus designs only; main reviews/integrates. Same-goal parallel work needs
separate scopes or isolated alternatives, never competing writes to one file.

Use [the project skill](skills/my-career-training-testing/SKILL.md) for coordinated
build/verification and owned game testing. One game-input owner. Preserve normal human
controls, saves and installation. No fake results, teaching references, rank claims or
completion based on buttons/tests alone. Never ship proprietary game assets. Source,
native, frozen, installer and actual gameplay evidence remain distinct.

Python 3.12, PySide6/QML, isolated RLBot worker, native BakkesMod menus. Mutable data
belongs in per-user AppData. Frozen workers need explicit worker mode. Use the correct
checkout/interpreter and validated toolchain; never import another project accidentally.
Tests: `uv run pytest`; Windows packaging/native-candidate pipeline is separate from
the old overlay bundle. Read [integration contracts](docs/INTEGRATION_CONTRACT.md)
before shared changes.

Read [privacy guidance](docs/REPOSITORY_PRIVACY.md) before publishing. No keys, personal
paths/emails, saves, raw logs, sign-in state or extracted assets. Owner-approved public
attribution in LICENSE is intentional; no email is needed. Preserve third-party notices.
Future original changes follow LICENSE; prior MIT grants are not revoked. Only main
integrates/publishes reviewed changes.
