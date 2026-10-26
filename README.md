# My Career Training

An offline career and training mod for the player's installed **Rocket League
on Windows / Steam**. The intended experience is one shortcut, the game's own
menu style, a human captain with four bot squad members, and optional practice.

**The 24 October Windows ZIP failed player testing: Rocket League crashed while
loading its replacement menu. Do not treat that download as a working release.**
The repair and its evidence are tracked in [project status](docs/PROJECT_STATUS.md).
Source tests and a compiled installer do not establish playable game support.

[Website](https://my-career-training.vercel.app/) ·
[Releases](https://github.com/sloppamadewithlove/my-career-training/releases) ·
[Build guide](docs/BUILDING.md) · [Documentation map](docs/README.md)

## How the app fits together

| Part | Job |
| --- | --- |
| My Career Training | Starts the offline session, manages careers, and saves progress |
| Native menu and in-game plugin | Connect the game's buttons to career and practice actions |
| BakkesMod | Hosts that plugin and supported cosmetic/community features |
| RLBot and the private worker | Run bots, read match results, and reset practice situations |

Players open **My Career Training**. They never need to open its Worker. The
installer includes the app's support files; missing BakkesMod uses guided official
setup. Python, Visual Studio, Cursor and AI subscriptions are developer tools,
not player requirements. BakkesMod's runtime is not redistributed here.

My Career uses the supported offline launch mode. It does not grant online
inventory, modify installed game packages, or bypass online anti-cheat.
Normal Steam launch must remain separate and original. Steam is the current
test target; Epic has not passed its own acceptance test.

## Start here as a contributor

1. Read [AGENTS.md](AGENTS.md), [current status](docs/PROJECT_STATUS.md), and
   [next tasks](docs/NEXT_TASKS.md). Confirm unresolved player outcomes before a broad build.
2. Use the [build guide](docs/BUILDING.md) and
   [shared integration contract](docs/INTEGRATION_CONTRACT.md).
3. Check the [product specification](docs/BUILD_SPEC.md) and
   [native game acceptance guide](docs/NATIVE_ACCEPTANCE_SESSION.md).
4. Keep private logs, saves, game files, account IDs and credentials out of
   commits and release attachments. See [privacy rules](docs/REPOSITORY_PRIVACY.md).

| Folder | Contents |
| --- | --- |
| `src/my_career_training/` | Career, practice, bot, save and startup code |
| `native_ui/` | Authored native-menu classes and compiled bytecode |
| `plugin/` | C++ BakkesMod integration and native tests |
| `native_launcher/`, `native_file_view/` | Owned offline launch and private menu-file view |
| `scripts/`, `packaging/` | Build, installer and validation tools |
| `tests/` | Automated Python regressions using temporary data |
| `docs/`, `website/` | Current guidance, historical evidence and download page |

`runtime/`, `build/`, `dist/` and `release/` are generated and ignored by Git.
GitHub is the source of truth; Cursor Origin is a mirror. Older research notes
remain linked through the documentation map and are not acceptance claims.

## Source permissions

Copyright (c) 2026 Slava Porollo. Future original changes are not offered under
MIT; see [LICENSE](LICENSE). Earlier MIT grants and third-party licenses remain
in effect for their covered material. The repository stays public by owner choice;
visibility does not grant write access or approval to change the official project.
