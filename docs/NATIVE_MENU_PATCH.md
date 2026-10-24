# Private native menu patch

`scripts/native_menu_patch.py` builds one development movie for `menus.RootMenu`. It rewrites selected method bodies in an owned `MainMenu.gfx` and writes a new file outside this repository. It does not launch Rocket League, write an installed package, or load the candidate into the game.

Running the script with no arguments prints help and does not read a movie. `plan` reads only the two local text exports named on the command line. `build` also reads the movie, Java, and FFDec paths named on the command line. There is no default game path.

The owned movie must be SHA-256 `57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0`. The class must be `menus.RootMenu`, and each selected method must have the one body id below. A mismatch raises before the candidate file is created. Output that is the source file, a reparse point, or a path inside an installed game tree is refused.

FFDec 26.4.0 replaces one AS3 method body from pcode and does not recompute body stats. The generator keeps each method's original local count, initial scope depth, and max scope depth. It writes `maxstack` explicitly and raises that value only when the new instructions need a deeper operand stack. The replacement pcode does not use PlayerGlobal.

## Seven controls

`generateControls` is body `11257`, method `11397`. The new body always builds seven `BranchingMenu.createControl` buttons, validates each one, and focuses My Career when `currentFocus` is null. It does not build the stock play, shop, pass, club, esports, or play-now controls.

| Label | Existing field | Callback | New body |
|---|---|---|---|
| My Career | `m_playButton` | `openPlayMenu` | `MenuStack.ButtonTriggered("MCT_CAREER")` |
| Training | `m_itemShopButton` | `tryOpenShopMainMenu` | `MenuStack.ButtonTriggered("MCT_TRAINING")` |
| Garage | `m_garageButton` | `openGarageSelectionMenu` | unchanged |
| Workshop | `m_profileButton` | `openProfileMenu` | `MenuStack.ButtonTriggered("MCT_WORKSHOP")` |
| Community | `m_rocketPassButton` | `tryOpenRocketPassScreen` | `MenuStack.ButtonTriggered("MCT_COMMUNITY")` |
| Settings | `m_optionsButton` | `openOptionsMenu` | unchanged |
| Exit | `m_quitButton` | `Shell.ExitGame` | unchanged static callback |

`openPlayMenu` is body `11273`. `tryOpenShopMainMenu` is body `11268`. `openProfileMenu` is body `11274`. `tryOpenRocketPassScreen` is body `11264`. Those four bodies call `tagame.api.MenuStack.ButtonTriggered` and do not call the stock shop, pass, or play-menu functions. `MenuStack` is the class in this movie. `MovieMenuStack` is not used.

`handleAddedToStage` still refreshes through the parent menu, and that refresh runs `generateControls` while `m_shell` can be null. The new body keeps that case: it starts the movie's existing retry timer and returns. `tryRegenerateControlsOnTimerComplete` is not rewritten.

Garage and options keep `openGarageSelectionMenu` and `openOptionsMenu`. Exit uses the existing `Shell.ExitGame` callback directly. The career layout's bridge action `quit_game` is not emitted.

## Helpers replaced with no-ops

These RootMenu helpers are emptied because they auto-open a stock mode, decorate a field this candidate reuses, or ask the game to go online. Each no-op keeps the original signature and body stats.

| Method | Body | Why it is empty |
|---|---|---|
| `processReturnEvents` | 11258 | opens stock play from season, offline, tournament, and training returns |
| `updateEsportEvents` | 11253 | loads the live esports row the stock menu turns into a button |
| `updateIcons` | 11260 | badges the reused buttons and reads online product state |
| `updateItemShopBreadcrumb` | 11261 | badges the training field when the shop catalogue changes |
| `updateEsportLogoImage` | 11262 | downloads an esports image onto a menu button |
| `refreshEsportLogoImage` | 11263 | paints that image onto a menu button |
| `updateClubButton` | 11277 | invalidates the menu and would bring a club control back |
| `syncLocalClub` | 11279 | asks the privileges manager to go online |

`openShopMainMenu`, `openRocketPassScreen`, `openPlayNow`, `openEsportsLink`, and the club openers stay in the movie. They are not the callbacks of the seven buttons. This candidate does not claim that every other native online hotkey is disabled. `handleAddedToStage` still registers shop, pass, club, esports, news, ban, and tutorial listeners.

## Check after writing

The script asks FFDec to export the candidate class as ActionScript and as pcode. The check requires the seven literal labels, the four `MCT_` calls, empty helper bodies, the original garage and options operations, and the same body ids. A separate SWF walk requires the file to stay an uncompressed GFX movie whose tags match the source except the DoABC payload and, when the bytecode grows, the header length.

The private manifest records `constructed: true` only after those checks. `runtime_verified` and `production` stay false.

## Still blocked

The candidate is not installed and has not been shown in the game. The host does not yet route `MCT_CAREER`, `MCT_TRAINING`, `MCT_WORKSHOP`, or `MCT_COMMUNITY`. Exit still calls `Shell.ExitGame`, not bridge `quit_game`. Labels are literals, not localized strings. No controller, visual, or offline-session pass has been run.
