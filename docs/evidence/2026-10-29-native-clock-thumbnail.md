# Native training clock and gameplay thumbnail candidate

The native plugin writes the scenario's remaining time to the actual game clock.
The worker retains timeout ownership; unlimited match time stays enabled to avoid
stock match end/overtime. The same-event lease captures the original clock once,
retains it through retries, skips writes while paused, and restores on cleanup.
Replaced events and online/replay transitions discard the lease without writes.
The diagnostic probes release the production lease before their own timed writes.
Native clock values and flags are exposed in plugin status for direct verification.

The duplicate overlay seconds are removed; challenge index and controls remain.
Native HUD presentation with unlimited time and sustained zero require live checks.
Pure clock lifecycle checks passed; worker and no-score timeout checks: 65 passed.

The root browser embeds a 12,655-byte, 400x225 gameplay JPEG once. It reuses the
decoded bitmap for the row/detail and keeps fallback rendering on decode failure.
ABC is 51,598 bytes, within the unchanged 65,536 cap. Source and binary pins are
updated together. See native_ui/THUMBNAIL_PROVENANCE.md for capture provenance.
Independent asset checks passed (86 plus one checkout-context check; one skipped).
Actual game decoding remains unverified until this candidate's live test.

Informational plugin-session notices now appear in Settings rather than across
every menu. Startup/restoration failures remain visible. Five focused Python and
the native layout check passed for this change. Full candidate build pending.
