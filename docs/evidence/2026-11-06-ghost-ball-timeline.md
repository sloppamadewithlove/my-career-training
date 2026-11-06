# Recorded ghost ball timeline — 6 November 2026

Base: `8759a83eaed240ad37579e9d75fc10431964d005`.
Source change: `769a43a593f4b479b4d5b9e72b65e936ed53359a`.

Recorded ball positions can now be interpolated at the same playback time as
the car. Missing ball samples remain unavailable; no ball motion is invented
across a recording gap. Existing car-only recordings remain supported. This
does not enable ball-dependent ghost practice or register a native renderer.

The author and an independent Luna tester each ran 50 focused tests; Ruff
passed. Independent GPT-6 Astra max code review found no blocker and reported
98 passing tests, including endpoint, single-sample, legacy, gap, mutation and
JSON checks. Reviewer token and cost information was not available.

`GhostPractice` still uses car-only relative placement and does not draw a
demonstration ball. No actual flip-reset recording, translucent car, native
renderer, plugin build or live lesson was tested or accepted by this change.
