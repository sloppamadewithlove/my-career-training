# PERFORMANCE-01 — configured work budgets

Read-only inspection of the isolated research candidate. These are configured
limits and source-derived work counts, not measured latency or gameplay results.
DeepSeek supplied the source survey; the coordinating pass corrected claims about
timer frequency, lock scope, image counts and callback threading.

| Area | Configured work | Source reference |
| --- | --- | --- |
| Desktop/service polling | 200 ms desktop timer; 100 ms service timer. Actual scheduling frequency is unmeasured. | `bridge.py:183-185`; `bootstrap.py:327-365` |
| Bridge publication | `FileBridge.poll()` publishes on each invocation, even without a state change. Atomic replacement retries sharing violations. | `ingame.py:61-73,114-116` |
| Plugin bridge reads | At most 8 MiB; unchanged mtime/size skips file parsing. Freshness accepts timestamps from five seconds old through two seconds ahead. | `LocalBridge.cpp:120-204` |
| Bridge commands | At most 32 files per intake, 65,536 bytes each; bounded seen-ID set. | `ingame.py:87-113` |
| Native garage catalog | At most 200 products inspected per tick, 100,000 total; sorting once on completion. | `MyCareerTraining.cpp:1346,1504-1537` |
| Community downloads | One in-flight plugin job, cancellation event, one completion consumed per poll. | `bridge.py:326-416` |
| Community catalog | Two workers; 50 pages and 512 rows; one result consumed per poll. | `bridge.py:36-40,420-577` |
| Thumbnail work | One worker, queues of 128, at most 64 results consumed per poll. | `browser_images.py:290-315,381-395,515-552` |
| Thumbnail fetch | 2 MiB body limit, 10-second socket timeout, 15-second checked deadline, two redirects, 64 KiB chunks. This is not an exact end-to-end deadline including all processing. | `thumbnail_cache.py:47-61,463-495` |
| Thumbnail conversion/cache | 2,048 pixels per side, four megapixels, output at most 480×270; 128 receipts/32 MiB cache; 24-hour freshness. | `browser_images.py:32,164-183,457-476`; `thumbnail_cache.py:52-61` |
| Lesson covers | Eight covers with individual art/receipt limits of 256 KiB/8,192 bytes. | `browser_images.py:30,137-161,230-277` |
| Workshop scan | At most 4,096 examined files, depth six, 1 GiB per package, four-byte magic check. Inventory coverage can stop at the cap. | `workshop.py:22,114-124` |
| Executable hashing | 2 GiB size ceiling, checked 10-second elapsed budget, 64 KiB chunks. Neither value promises disk throughput. | `ExecutableHash.h:25-54` |

## Work worth measuring before optimization

`LocalBridge::state()` returns the JSON state by value under its mutex, and
`Render()` calls it per rendered frame (`LocalBridge.cpp:205-208`;
`MyCareerTraining.cpp:1758`). Skipping unchanged file reads does not skip this
copy. Measure document size and copy duration before deciding whether it matters.
The 8 MiB input ceiling is not a typical observed state size.

Thumbnail `poll()` tries ownership for each result. It may publish some results
and then stop when the lock is contended; it is not all-or-nothing for the entire
tick. Staging holds ownership during hashing/conversion/cache work, so contention
can defer the remaining results. Record published-result count and deferred polls.

Refreshing the published image-file map scans the current images. The community
token bound is 128, with lesson covers also represented; do not describe every
scan as a strict 128-entry maximum. The repeated scans are bounded work, but no
timing measurement establishes them as a bottleneck.

The service's nominal 100 ms timer does not prove a fixed 10 Hz disk-write rate.
Nor does it prove that the plugin's unchanged-file fast path rarely runs: that
depends on both callers' actual scheduling. Measure publication intervals and
unchanged-read ratios together.

Native product collection is a multi-tick job, approximately `ceil(N / 200)`
collection ticks for N inspected products, followed by completion work. It adds
work to the plugin tick callback. This inspection did not establish that render
and tick execute on the same thread; do not infer that from callback names.

## Cancellation and publication identity

Community jobs use one in-flight operation plus cancellation, rather than a
generation ID. The busy guard prevents a second superseding job. Download
completion after the commit boundary is intentionally reported. The absence of
a generation field alone is not evidence of a stale-result defect.

`Backend.close()` calls the thumbnail service's `close()`, which cancels and
invalidates its generation. The worker's bounded queue handoff then recognizes
staleness. A hypothetical caller that abandons polling without closing is not
evidence that the existing shutdown path does so.

There is no measured aggregate page-load deadline. Multiplying 128 jobs by a
15-second checked fetch deadline is illustrative queue arithmetic, not a wall-clock
guarantee. Cache hits, network waits, cancellation and staging alter total time.

## Next evidence

Collect per-job fetch/stage time, per-page terminal-row coverage, ownership-lock
deferrals, state-copy duration/size, bridge publish/read intervals, product-count
and collection duration, and Workshop examined-versus-cap counts. Establish user
visible responsiveness requirements before assigning performance thresholds.
Ghost render cost and live frame time were outside this pass; no benchmark,
build, game session or production edit was performed.
