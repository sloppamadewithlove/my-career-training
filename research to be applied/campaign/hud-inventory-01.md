# HUD-INVENTORY-01 — current HUD movie and selected training sources

The exact installed `GFX_Hud_SF.upk` package was read with the existing project package reader. Separate DeepSeek workers built and reviewed a small inventory wrapper; the coordinator executed it. No game process was launched, attached, modified or controlled.

The package is 1,260,419 bytes, SHA-256 `1a6c92191333c5612711b84fa4570d4f088bc977feb7cad58f4ec4343d0e5a59`. Its `HUD` movie is 1,145,308 bytes, SHA-256 `65535317cbc36b2added175b2ff3c817b9093a2ea83951e08d7349c15c1073ef`. The existing pinned FFDec 26.4.0 and Java 21 toolchain ran `-dumpAS3` with deobfuscation disabled. It exited 0 and produced 25,337 bytes: 742 nonblank lines, of which 741 matched the observed script-name/index format. These are tool inventory entries; global functions may appear alongside classes.

Before that run, independent review caught an incorrect package hash and a stale result key. Both were corrected and reviewed. Coordinator checks rejected empty, banner-only and error-only output, and counted two parsed entries separately from three nonblank lines in a mixed fixture. The exact installed package hash matched the corrected pin. These are bounded local diagnostic checks, not game acceptance tests.

The inventory identified `tagame.hud.TrainingView`, the training and game-event API tables, training-use-action rows, per-shot progress, training enums and relevant label/movie wrappers. A separate direct CLI selection then exported exactly fifteen identified classes, exited 0, and retained all source privately. The [sanitized receipt](../evidence/hud-inventory-01.json) records file hashes, tool identity and both stages. It contains no decompiled source or movie payload.

The next source analysis traces which host fields drive the timer, score, shot counter, progress and control labels; it also checks whether screen anchoring or visibility can be established from these classes. Package names and successful exports alone do not establish timer units, native expiry order, ball disappearance, runtime layout or input behavior. The stock HUD may require host-populated training tables absent from MCT's RLBot Soccar lesson; that distinction must survive implementation.

The initial inventory helper has a 90-second subprocess timeout and post-hoc package/movie/list size bounds. These are not live memory or output quotas. It refuses an existing output directory and confines newly written private artifacts to the supplied workspace. Raw game assets and decoder material remain outside the published research folder.

CLI syntax was checked against the [official FFDec command-line reference](https://github.com/jindrapetrik/jpexs-decompiler/wiki/Commandline-arguments). The project reader was the existing fallback after REA did not support this UE3 package format; no new broad package decoder was introduced.
