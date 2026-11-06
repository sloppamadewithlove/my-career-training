# Recorded car/ball native handoff — source checks only

Base: `936adc2df332ea8edbf7b296962238b4ea881476`. The patch connects the
existing worker recording playback payload to `NativeGhostRenderSample`; its
SDK renderer consumer is a separate integration. No game was launched or changed,
and no actual recording or teaching demonstration is supplied by this patch.

Flip-reset practice now keeps recorded car and recorded ball in their original
world positions, on one recording clock with sample-held logical actions. It
does not re-anchor to the human. The existing translated car-only drills retain
their placement; the shared transform now also preserves an observed ball.
Other ball/wall drills remain unsupported. A flip-reset practice recording must
declare success, be untruncated and contain observed ball positions throughout.
Those are eligibility checks on supplied data, not independent success proof.
Existing personal/import labels and `independently_validated:false` remain.

`nativeGhostSampleFromState` consumes actual `telemetry.ghost_practice`, checks
the active worker/lesson, visibility, compatibility, pending toggle/capture state,
matching pose/cursor/actions and finite physics, and converts recording `w,x,y,z`
quaternions to native proxy `x,y,z,w` exactly once. The SDK consumer must still
bind fresh owned/offline scope, game/actor/attempt identity, pause state and frame
age through the existing native draw lease. The adapter grants no rendering or
teaching-reference authority by itself.

## Player action contract

1. Preconditions: an active offline flip-reset lesson and an explicitly selected
   compatible complete recording declaring success. A real permitted successful
   trace and live non-interference acceptance are still required for a teaching demo.
2. Input: existing explicit recording selection/load, then a fresh Down key or
   D-pad Down edge. The existing command dispatcher sends `ghost_control` with
   the desired `enabled` value; it never silently enables on load.
3. State outcome: On starts paired playback at its recorded beginning; Off clears
   pose, lines and recorded controller actions immediately. Left/Right/Up keep
   their prior behavior in flip reset; only Down bindings are temporarily owned.
   Existing Power Shots controls retain their four-direction behavior.
4. Persist: existing backend assistance preference persistence is unchanged;
   recording samples and game state are not changed by playback.
5. Failure/recovery: incompatible, incomplete and unsuccessful flip traces are
   rejected before replacing the selected players. Missing content stays
   unavailable. Pending commands, paused/capture/Career scope and held keys do
   not dispatch a new toggle. Scoped bindings restore prior values, preserving
   external edits, including transitions to/from Power Shots.
6. Proof: 51 focused Python checks passed, including actual worker-command ->
   backend-state JSON -> compiled native parser with a clearly synthetic fixture.
   Four native CTests passed: recorded payload parsing, immutable render frame,
   ghost menu layout and production lesson-input/binding state. Down testing
   includes uneven arrivals and a held key across a frame gap/acknowledgement.
   Ruff and `git diff --check` passed. No native DLL build/package, live draw,
   physical controller or successful real flip-reset execution was tested.

## Remaining entry and content work

Existing explicit `play_recording` commands load and validate the selected
recording, leave practice Off, and acknowledge only after application. The
existing legacy automatic-best path remains watch/lead playback. The worker's
startup `request.recording` field only assigns its stored recording value; it
does not load either playback object. This patch does not add automatic startup
selection, manufacture a trace, or claim a native stock-training lesson entry.
Main must integrate the separate SDK callback consumer and verify one exact
candidate before claiming visible native synchronized playback.

## Selection correction after independent review

The saved recording index had no truncation or observed-ball completeness data.
The backend now adds a runtime-only `practice_eligible` field to flip-reset rows
by reading and validating the capture itself and calling the same eligibility
predicate used by `GhostPractice.load`. It hydrates the newest 64 indexed rows,
matching the native selector's existing bound. Its parse cache key includes the
resolved file path, device/file identity, size and modification/change times.
Bounded file-metadata checks invalidate changed/replaced/deleted files; unchanged
capture bytes are not reread per refresh, and invalid parses are cached too.
Stored career indexes and recordings are unchanged. Missing/invalid files and
unsafe paths are unavailable. Actual load revalidates the full recording.
Changes racing a metadata check or deliberately preserving all file identity and
timestamp fields can leave the summary stale until a changed signature; the
summary is not a file-integrity monitor or certification.

The native menu skips ineligible newer flip-reset rows, preserving access to the
newest eligible older row, and describes fixed recorded car/ball positions rather
than placement ahead of the human. Existing personal/import provenance remains.
Sixty-four focused Python checks passed, including failed, truncated and ball-less
newer files through actual stored recording bytes -> backend state -> compiled
native menu selection. They also check unreadable/missing/path-invalid captures,
unchanged saved indexes, changed/deleted/replaced/same-id-different-file cache
invalidation and no repeat capture read on view refresh. Native menu
layout checks and Ruff passed. No gameplay, real reset success, publication or
DLL/package acceptance is established by this correction.
