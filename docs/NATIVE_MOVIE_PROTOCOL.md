# Authored native menu and local protocol

`native_ui/menus/MctRootMenu.as` is original mod code that derives from the
game's `BranchingMenu`. It creates the game's existing button controls, copies
their font for the adjacent career text, preserves menu-stack notifications,
and handles Back through the currently published `nav.back` choice. Longer
choice lists have local pagination. Stock Garage and Options are explicit
typed routes; online/store controls are absent from this authored class.

This is a development candidate. It has not been loaded in Rocket League.
The normal plugin does not yet publish this protocol or install its command
hook. The native-file loading experiment is separate. Global shell hotkeys and
routes inside other stock screens are not disabled by this class alone.

## Wire format

`NativeMovieProtocol` adapts the existing `NativeCareerLayout`, so the movie
does not implement career rules or choose arbitrary bridge actions. The host
opens the model with a live owned/offline/fresh scope, then publishes a bounded
view with protocol 1, session, timestamp, active state, title, body and controls.
Each control has an id, label, reason, enabled flag, revision and optional
`garage`/`options` stock route. Generations and revisions are decimal strings
to preserve 64-bit identity in ActionScript.

Heartbeat-only publications retain their generation. A changed binding,
accepted click, reopened scope or invalidated view requires a new generation.
The retained binding includes its action and payload even though those fields
are not sent to the movie. A click carries only protocol, session, generation,
revision and control id; extra caller-supplied action or payload fields fail.
The model rechecks the current backend state and ownership on selection.

The authored movie reads a session-specific local `file:///` URL using
`URLLoader`. It refuses a mismatched session or data older than five seconds.
It sends custom choices through the existing `DevUtil.Log` wrapper with the
fixed category `MCT_NATIVE_UI_V1`. A future host hook must validate the caller,
bounded string parameters, current game build, session and live ownership
before passing the message to this protocol. Unrelated log calls remain
unrelated. Neither a file nor a log message establishes ownership.

Both local-file loading in Rocket League's GFx runtime and this specific log
callback remain unverified. A compiling class and passing model tests do not
grant runtime compatibility. The class falls back to a connection message and
an explicit native Exit control if its view is unavailable.

## Build evidence and distribution boundary

The source compiled with Apache Flex 4.16.1, Temurin JRE 21.0.9, a PlayerGlobal
32 reference and SWF version 20. A private SWC containing the owned game's ABC
declarations was supplied through `external-library-path`, which excludes that
library from the output. The compiler reference's GFX media tags were omitted
from that private SWC because Flex's SWF reader cannot parse those tags.

The inspected result contains exactly one class, `menus::MctRootMenu`.
Its current hashes and method count are in `native_ui/compiled/manifest.json`.
The original mod ABC is stored under
`native_ui/compiled/`. It contains placeholders for the local view URL and
session. It contains no linked game classes or game artwork. Rebuild the ABC
when editing its source; the composition step must bind the placeholders and
validate its pinned hash before using it.

Private game SDKs, original/modified GFX movies and original/modified UPK
packages must stay outside the repository and distribution. Players should
receive our compiled code and a bounded transform for their own matching local
game, not the compiler, Java, a private SDK or redistributed game assets.

The plugin protocol's focused executable covers navigation, duplicate and
stale choices, unrelated callbacks, caller payload refusal, reconnects,
heartbeat focus stability, offline scope and the fixed Exit dispatch. It does
not start a game.
