# First-visible evaluator harness (FC-6)

Drives the **real production `index.html` physics** in headless Chromium
(Playwright), never editing the production file. Establishes a narrow
experimental **solar-twilight provider boundary** that replaces only the solar
twilight excess (Btwi), and proves it is exactly transparent when using the
legacy provider.

## Status

- **Provider boundary + legacy parity: DONE and PROVEN.**
  `run_provider_parity.mjs` loads the unmodified `index.html`, injects the
  provider seam at runtime, and compares the production
  `localSkyBrightnessComponents` (and downstream NELM) with the legacy provider
  installed vs uninstalled, across 354 geometry/sky/Moon cases. Result:
  **exact** (max Δtwilight = Δtotal-sky-mag = ΔNELM = 0, 0 page errors) —
  `reports/provider-parity.json`.
- **Event-search driving (evening/morning, Standard/Comparison, 1/2/3-star,
  Main/Worker, atmosphere modes, Moon on/off, altitudes, no-result/no-sunset):
  TODO.** Requires driving the full `calculate()` UI flow and reading the event
  outputs; scaffolded next on top of the proven provider boundary.

## Provider contract

```
solarTwilightProvider({
  sunDepressionDeg, targetApparentAltitudeDeg, relativeAzimuthDeg,
  sunStarSeparationDeg, baselineSqm, aod550, observerElevationM,
  atmosphereScenario, surfaceAlbedo, timestamp
}) -> { twilightNl, uncertainty, status, metadata }
```

Replaces ONLY the solar twilight excess. It does not touch the night-sky floor,
artificial light, the Moon term, star extinction, the observer threshold,
clouds, or the search logic (directive #1). `live-total` / user static total SQM
bypass the provider entirely. A provider returning a non-finite `twilightNl`
fails safe to the legacy value.

## Run

```
cd scientific-tools/twilight-lut/harness
node run_provider_parity.mjs [path/to/index.html]
```

Chromium path defaults to `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`
(override with `PW_CHROME`). Requires the repo-root `playwright` install; a
`node_modules` symlink to the repo root is provided.

## Event outputs the full harness will return (per scenario)

`eventFound, eventTimeUtcMs, displayedTime, sunDepressionDeg, completingObjects,
totalSkyMagArcsec2, limitingMagnitude, visibilityMarginMag, twilightNl,
providerStatus, providerMetadata`. Legacy-provider parity must hold on all of
these (plus raw event time, displayed minute, required star count, completing
set, 60-second stability) before any fixture/synthetic provider is used for
sensitivity testing. The experimental provider stays disabled unless the harness
explicitly installs it; production UI and defaults are never changed.
