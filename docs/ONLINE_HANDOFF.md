# Restore before returning to the normal game

The previous source requested the normal launcher as soon as the owned career
game exited. Its temporary BakkesMod DLL/autoload changes were restored only
when the service itself exited. That order could expose the temporary setup to
the next game and then defer restoration because another game was running.

The backend now finishes the plugin-session journal before requesting the
normal launcher. Successful `idle` or `restored` status is required; conflicts,
deferred cleanup and exceptions block the launch. The lifecycle rechecks for a
game after cleanup, and the platform launcher keeps its own final check.
Restoration removes the session's autoload addition before restoring its DLL.
It rechecks for a running game before each resource and immediately before a
replacement, retaining unfinished resources in the recovery journal.

The service's separate shutdown timer waits for an active handoff to finish.
It no longer exits merely because the career process disappeared while the
backend still needs to restore setup and request Steam. Handoff errors are
reported once. A final deferred cleanup is reported as incomplete, not a
successful service exit.

Synthetic Windows tests exercise actual temporary DLL/config files, verify
their original bytes and cleared journal inside the mocked launcher callback,
and cover conflicts, deferred recovery, another game starting during cleanup,
and timer ordering. No real game or launcher runs in these tests.

Limits: these are source/fixture checks, not a live online transition receipt.
An independently launched game can still appear between a process check and a
filesystem operation; shared global files are not process-isolated. Failed
startup or a hard crash can leave a recovery journal while another game is
open. Such files stay pending until recovery runs after that game closes; there
is no persistent cleanup service. These limitations must remain visible in
acceptance and do not lift the native-menu installer hold.
