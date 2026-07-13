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
- After 6 deg, the built-in curve uses about 1.0 mag/arcsec^2 per degree until 12 deg.
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
