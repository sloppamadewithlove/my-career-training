# Clock lease regression in CTest

The native-results source base is `9ee0c3333686be74afdd5de0e24cde2932b1af61`.
This branch registers the previously reviewed standalone clock lease regression
from `25afb586513e487d392783a4696faaf847188a8c` with the plugin CTest suite.
The test file's Git blob is unchanged (`bc0ecc9218b9ccb8c1ba8f79ef2e77a304943735`).

The test covers offline and replacement-event detach without unintended writes,
and retention of a lease after a failed restoration until a successful retry.
On Windows, MSVC 19.44 built the registered Release target with the plugin build
disabled; CTest passed 1/1 on this base. An independent verification confirmed
the original-base file identity, CTest registration and a passing existing test;
it did not independently rebuild that executable. The clock helper and CMake
file are identical between the original and native-results bases.

This is a focused helper test, not a full plugin build, installed candidate,
live clock check or acceptance of the native-results repair. Integration and
updated-game compatibility remain separate work.
