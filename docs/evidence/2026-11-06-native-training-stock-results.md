# Native training stock results candidate

Base: `bd9336d869363c51375bb9c35f0ae351aea74bb0`. This source repair is not
the live-tested binary. No new package or game session was launched by its builder.

## Observed defect and source cause

In the tester's exact `bd9336d` local native Custom Training run, stock pause and
Resume worked. End Training followed by Yes reached the training results screen
at 0%, with no usable controls and **Waiting for the offline career service**.
The backend was Idle; this was not an MCT Career result or a return to the hub.

The results movie is globally replaced. Its authored `generateControls()` creates
only a disabled RESULTS row when no current MCT results view exists, and its
details field produces that waiting message. The original training statistics
screen still appears, but the authored controls intercept its normal choices.

The tester subsequently closed all owned processes. Original and isolated MCT
careers, the local sequence, checked plugin/config and game assets matched their
preflight hashes. Three absent backup saves were restored create-new-only.
Changed current game saves and newly present profile files were preserved; this
does not establish that the entire game profile was unchanged.

## Bounded repair

The pinned original `EndGameMenu` has an explicit TRAINING/GAME_EDITOR branch:
Play Again calls the native restart, Change Mode/Match opens stock Play, and
Change Training Pack opens the native browser when native progress rows exist.
Options and the native confirmed Exit to Main Menu remain available according
to the stock feature gates. Its document owns training-result animations.

Offline TRAINING or GAME_EDITOR now delegates to those stock classes. The shared
static selector also works during the document's initial animation, before its
child menu exists. It does not depend on a custom-training flag surviving finish.
Controls, input, focus, countdown display, relevant callbacks and document chrome
remain stock. MCT details, gesture capture and service polling do not take over
this mode; late view responses cannot acquire Return holds or issue navigation.
The inherited Ready callback retains a null-button guard because the native
training branch creates no Ready button.

OFFLINE/SEASON Career and RLBot soccar results keep the authored controls,
gesture rules, durable result/Return binding and timer-hold policy. Unknown and
online modes do not gain the new delegation. No native exit implementation,
backend command, game/profile write or C++ dispatch change was added.

## Verification and limits

Apache Flex 4.16.1 compiled the authored results against a private ABC-only SDK
from the pinned original EndGame movie. The owned ABC is 26,196 bytes, SHA-256
`f6e6ae557fef858e530d9d4d295c4eabd2e9409d677748913375f074f8fda510`,
with 125 method bodies: three authored classes and seven existing JSON classes,
no linked game classes or private build paths. Original assets and decompiled
classes remain private.

The final compiled selector's exported instructions passed 24 synthetic
offline/online and training/editor/Career/unknown cases. A source contract
regression checks delegation, polling, gesture and pre-child document boundaries.
Composition/staging/candidate Python checks: 112 passed, one skipped. Ruff passed.
The production menu-contract check and composition against the exact pinned
original EndGame movie passed. Fresh MSVC builds of native match-movie,
Return-gate and saved-results timer-hold tests passed. These checks do not prove
runtime DataAPI values, visible focus or actual exit behavior.

Stage the newly compiled results ABC before building a fresh candidate. Live
acceptance still needs stock results controls after native End Training, the
chosen restart/browser/main-menu path, and an authored Career results/Return
regression. Controller behavior and teaching demonstrations remain unaccepted.
