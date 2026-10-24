# Native career management choices

`NativeCareerManagement` is a stateless helper for four career panels the current native menu does not operate: creating the first career, editing the squad, starting the next season, and changing format or difficulty. It reads the published bridge JSON and returns typed choices. It does not draw, read the clipboard, write a file, send a command, or launch Rocket League.

This is not a finished menu and it is not game evidence. The contract test uses synthetic careers shaped like `career.py`. It does not start a match, export a save, or prove that a click reached the game.

## Contract

`plugin/include/NativeCareerManagement.h`

```cpp
struct NativeManagementChoice {
    std::string id, label, reason, action;
    bool enabled = false;
    Json payload = Json::object();
};
struct NativeManagementView {
    std::string title, body;
    std::vector<NativeManagementChoice> choices;
};

NativeCareerManagement::create(state);
NativeCareerManagement::squad(state);
NativeCareerManagement::season(state);
NativeCareerManagement::rules(state);
NativeCareerManagement::careerSummary(state);
NativeCareerManagement::rewardSummary(state);
```

Root copies each choice onto an existing `CareerLayoutChoice` with kind `Dispatch`, sets `careerId` from the current career when there is one, and adds Back. The career id stays on the layout choice. It does not go inside the bridge payload. `new_career` must not contain `recruits`; omitting it keeps the domain's five default recruits.

`choose` already compares the whole choice, including label, enabled, action, and payload. These ids also change when the payload changes, so a same-label control cannot silently apply a different draft, lineup order, reserve, or baseline:

| Panel | Id |
|---|---|
| Create | `create.paste`, `create.new.<format>.<name hash>` |
| Squad | `squad.lineup.<ids>`, `squad.replace.<outgoing>.<incoming>`, `squad.rename.<id>` |
| Season | `season.next.<champion>` or `season.next.unavailable` |
| Rules | `rules.format.<n>`, `rules.baseline.<preset>.<curve>`, `rules.curve.<curve>.<baseline>` |

A panel has at most 18 choices. Body text is at most 1800 characters, labels 80, reasons 240. List scans stop at 64 items. Standings show the first 8. Completed fixtures and rewards show the last 8 of the last 64. Strings with control characters, slashes, or URLs are not copied into the text.

## What state it reads

| Field | Use |
|---|---|
| `session.busy` | Boolean `false` is required before a mutation is enabled. A missing session is treated as busy. |
| `career.pending_session` | Any value other than null disables mutations. |
| `career_draft.team_name` | Club name for `new_career`. One to 40 printable characters. Anything else becomes `My Career Club`. |
| `career` | Squad, season, and rules need a career id of letters, digits, `_`, or `-`. |
| `career.recruits`, `squad`, `lineup`, `format` | The five domain ids `anchor`, `shield`, `relay`, `comet`, and `orbit`. Roles and levels must match the domain (level 1 through 5). |
| `career.difficulty` | Baseline from 0 through 1, curve `flat`, `gentle`, or `steep`. |
| `career.seasons[current_season]` | Champion, clubs, fixtures, and playoffs that are already published. |
| `standings` | The table the bridge already published. This helper does not recalculate it. |
| `latest_result` | Not trusted for the native summary; only completed fixtures in the current career establish its played results. |
| `career.rewards` | Known types only: `match_experience`, `season_trophy`, `season_badge`. |

## Choices

`create` explains that starting a career replaces an existing one, and that the service exports the current career before the replacement. The export already lives in the Python service. This helper does not write that file. `Paste club name` is `career_name_clipboard` with `{}`. The four format buttons are `new_career` with `{team_name, format}` for formats 1 through 4. When a career exists, the labels are `Replace career with new 3v3` and the same form for 1v1, 2v2, and 4v4, so the click itself is the confirmation.

`squad` lists the published name, role, level, and starter, bench, or reserve. Lineup buttons are the combinations of the four-person squad for `format - 1` starters: one empty lineup for 1v1, four for 2v2, six for 3v3, and four for 4v4. The payload is `lineup` with `{ids: [...]}` in the current order when that set is already selected, otherwise in squad order. The current set is labeled `Current lineup:`. The one recruit outside the squad has four `replace_recruit` choices, `{outgoing, incoming}`, using the published names. Each squad member also has `rename_recruit_clipboard` with `{id}` and no name. A duplicate, unknown, or wrong-sized roster produces no mutation buttons.

`season` shows published standings, the last completed fixtures (league and playoffs) with their published scores, the champion, and known rewards. `next_season` with `{}` is enabled only when the champion is `human`, `aurora`, `cinder`, or `tidal` and the session is idle. Scores are copied from completed results. Scheduled fixtures do not get a score. A simulated other-club result can be shown as `recorded`. It is not described as the player's result and it is not calculated here. `careerSummary` is the season line, a short table, and the last played result. `rewardSummary` names the known local records and says they are not Rocket League inventory.

`rules` offers `set_format` for 1v1, 2v2, 3v3, and 4v4. The current format is labeled `Selected:`. Baseline buttons send `set_difficulty` with `0.25`, `0.5`, or `0.75` and the current valid curve. Curve buttons send `flat`, `gentle`, or `steep` with the current valid baseline, including a baseline that is not one of those three presets. An invalid curve hides the baseline buttons. An invalid baseline hides the curve buttons. 4v4 stays available here; any opponent-policy fallback is outside this helper. Game Options and backups stay on the existing settings routes. This helper does not add them.

Busy and pending choices stay in the list with `enabled: false` and a reason, except panels that have no usable career or roster. Those panels have no actions.

## Native menu integration

`NativeCareerLayout::supportedAction` accepts these eight actions. Its `push` drops disabled payloads and unrecognized dispatches; selection compares the complete typed choice against current state.

`career_name_clipboard` and `rename_recruit_clipboard` are handled by the Python service, which reads the clipboard on that explicit action and rejects any extra payload key. All eight actions are in both bridge allowlists. Settings adds backup, save-folder access, diagnostics and input-label profiles without exposing arbitrary settings keys from the movie.

`CreateCareer` and `CareerRules` join the existing Squad and Season pages. Creating a career or advancing a season returns to Career. Rules explicitly selects among the available Ground Specialists, Necto and Nexto providers. Necto/Nexto cannot launch 4v4; the player must choose Ground Specialists. Native Back and stock Options routes are preserved.

Clipboard actions carry no name. The service validates the clipboard as 1 to 40 printable characters. This helper only publishes the button.

## Test

`plugin/tests/native_career_management_tests.cpp` checks the payloads, repeated calls, input stability, missing careers, malformed rosters, busy and pending sessions, every format including an empty 1v1 lineup, reserve swaps, an unfinished season and a finished one, the action allowlist, and bounded malicious text.

The helper is header-only. CMake registers its test for both plugin configurations through the shared `mct_bridge` dependency:

```cmake
add_executable(mct_native_career_management_tests tests/native_career_management_tests.cpp)
target_link_libraries(mct_native_career_management_tests PRIVATE mct_bridge)
add_test(NAME native_career_management COMMAND mct_native_career_management_tests)
```

No Rocket League process is started by that test. A passing run does not show these labels in the game or prove the backup, clipboard, or next-season path.
