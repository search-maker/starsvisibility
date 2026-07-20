Star Visibility Calculator - scientific model review notes

Changed file:
- outputs/cloudflare-upload-star-visibility/index.html

Functions/areas changed:
- Default twilight brightness curve after 6 deg solar depression.
- Physical limiting magnitude threshold now has observer-mode bonus diagnostics.
- Empirical comparison formula updated to the new intercept/slope and expert floor rule.
- Advanced table and CSV diagnostics now include observer and twilight-curve fields.
- UI help text and English labels were added for the new controls/columns.

Twilight curve:
- Legacy 0-6 deg behavior is preserved.
- External twilight calibration CSV still overrides the built-in curve.
- After 6 deg, the built-in curve uses 0.95 mag/arcsec^2 per degree until 12 deg.
- 12 deg is NOT hard-coded as full night.
- From 12 to about 16 deg, the model blends smoothly toward the local base SQM.
- Final sky brightness remains Btotal = Bdark + Btwilight + Bmoon.

Old-vs-new default twilight example, base SQM 21.8:
- Sun depression 6 deg: old 15.27 SQM, new 15.27 SQM.
- Sun depression 8 deg: old 16.05 SQM, new 17.27 SQM.
- Sun depression 10 deg: old 16.82 SQM, new 19.27 SQM.
- Sun depression 12 deg: old 17.57 SQM, new 21.27 SQM.
- Sun depression 16 deg: old 21.01 SQM, new 21.80 SQM.

Observer modes:
- ordinaryOrGuided: 0.00 mag, default.
- trainedObserver: 0.60 mag.
- expertKnownPosition: 1.10 mag.
- Manual override allowed from 0 to 1.5 mag.
- The bonus is added to limiting magnitude, not subtracted from star effective magnitude.

Browser validation performed locally:
- Page loaded at http://127.0.0.1:8801/ with no load error.
- Calculation completed with no error.
- Main table column parity passed: 109 headers and 109 first-row cells.
- CSV parity passed: 138 columns, 8410 rows, no bad rows, no missing required diagnostic fields.
- Observer modes produced ordered visible counts:
  ordinaryOrGuided 2849, trainedObserver 3880, expertKnownPosition 4185.
- Manual kV override checked: kV=0.33 in manual mode produced source "Manual kV" and kV used 0.33.

Limitations:
- The requested Kiryas Pupa / Croton Dam / Seven Lakes observation tables were not included as machine-readable data in this request, so RMS residual validation against those tables could not be completed.
- Sun/sunset/timezone/star geometry/refraction/airmass/catalog logic was not intentionally changed.
- These changes were not deployed to production.

Three-Star annual worker architecture:
- The annual worker currently re-executes the single-file application script with a minimal fake DOM, so it can use exactly the same calculator functions as the main page.
- Replacing that bootstrap in this release would require separating the calculation closure, catalog state, weather inputs, and result serialization from many DOM-backed controls. That is a broad refactor and was intentionally deferred to avoid changing scientific behavior.
- Focused follow-up: extract a DOM-independent `calculateThreeStarTime(settings, date)` module plus pure catalog/sky/visibility dependencies; import that same module from the page and annual worker; then require optimized-versus-exhaustive parity tests before removing the current worker bootstrap.

Three-Star known-exclusions performance:
- The broad known-exclusions selection now applies two conservative bounds before the detailed visibility scan: the object must be capable of reaching the selected apparent-altitude threshold at a real scan boundary, and its brightest mathematically possible effective magnitude must not be fainter than the darkest possible limiting magnitude for the supplied settings.
- Planets are retained unconditionally by this optimization. Extinction is treated optimistically as zero and the full allowed -0.35 mag color brightening is included, so the magnitude test cannot remove an object that the detailed model could make visible.
- The result metadata records eligible, retained, and optimization-prefiltered candidate counts. A test-only `globalThis.__THREE_STAR_EXHAUSTIVE__` switch bypasses the safe reduction for parity testing; it is not exposed as a user control.

Annual cache policy:
- Every cache item stores the complete normalized settings JSON and is reused only after an exact JSON match, in addition to the model/version/result checks.
- Only the six most recently used annual calculations are retained. Storage quota, private-mode, and malformed-cache failures are ignored without interrupting calculation.

Three-Star exhaustive parity validation (2026-07-20):
- Ran 320 scenarios through the calculator's real `calculate()` path in both optimized and exhaustive modes: 100 targeted and 220 deterministic randomized scenarios (seed `0x53A7F11E`).
- Coverage included northern/equatorial/southern and Arctic locations, six seasonal date groups across five years, kV 0.12-0.65, catalog/effective/known-exclusions selection, two- and three-object requirements, four thresholds, Moon on/off, and equal English/Hebrew coverage.
- Compared result existence, no-result reason, event timestamp, minutes after sunset, Sun altitude, qualifying objects with first-visible timestamps, and completing objects.
- Result: 0 mismatches. The known-exclusions optimization remains enabled; no exhaustive fallback was required.
- Known-exclusions candidate counts across all 185 cases: minimum 2, median 9, maximum 4,874. The maximum was a no-sunset Arctic case where the detailed scan returns immediately. Among valid-sunset cases: minimum 2, median 9, maximum 1,308; the high maximum was a deliberately conservative high-minimum-altitude edge case and matched exhaustive output exactly.
- Full reproducible report and results remain outside the production upload in `validation/three-star-parity-report.md` and `validation/three-star-parity-results.json`.
