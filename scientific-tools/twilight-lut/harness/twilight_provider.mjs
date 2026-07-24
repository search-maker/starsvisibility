// FC-6: experimental solar-twilight provider boundary for the first-visible
// harness. This code is INJECTED at runtime into a loaded, UNMODIFIED
// production index.html (via Playwright page.evaluate). It never edits the
// production file and is inert unless the harness explicitly installs it.
//
// The provider replaces ONLY the solar twilight excess (Btwi, nL) that
// localSkyBrightnessComponents adds at the star's direction. It does NOT touch:
// the dark/night-sky floor, artificial light, the Moon term, star extinction,
// the observer threshold, clouds, or the event-search logic. The dark floor and
// Moon terms are recomputed by the original code path exactly as before.
//
// Provider contract (the function the harness supplies):
//   solarTwilightProvider({
//     sunDepressionDeg, targetGeometricAltitudeDeg, targetApparentAltitudeDeg,
//     relativeAzimuthDeg, sunStarSeparationDeg, baselineSqm, aod550,
//     observerElevationM, atmosphereScenario, surfaceAlbedo, timestamp
//   }) -> { twilightNl, uncertainty, status, metadata }
//
// installTwilightProvider(provider) monkeypatches localSkyBrightnessComponents
// so that, for the ordinary physical path, Btwi comes from the provider while
// Bdark and Bmoon are computed by the untouched original helpers. A provider
// that returns the legacy value reproduces the unmodified result EXACTLY.

export const INJECT_SRC = `
(function () {
  if (window.__twilightProviderInstalled) return;
  const originalLSBC = localSkyBrightnessComponents;
  window.__originalLSBC = originalLSBC;
  window.__twilightProvider = null;          // disabled by default
  window.__providerLastMeta = null;

  window.installTwilightProvider = function (provider) {
    window.__twilightProvider = provider || null;
  };
  window.uninstallTwilightProvider = function () {
    window.__twilightProvider = null;
  };

  // A faithful re-derivation of the ORIGINAL solar twilight excess (nL), used by
  // the legacy provider to prove exact parity. Mirrors localSkyBrightness
  // components' twilight branch: excess at the horizon-brightened baseSkySqm,
  // times the directional factor.
  window.__legacyTwilightNl = function (p) {
    let Bdark = nLFromMag(Number.isFinite(p.baselineSqm) ? p.baselineSqm : p.sqmZenith);
    const Xs = airMass(Math.max(p.starAppAltDeg, 0.1));
    if (!p.baselineIsDirectional && !p.manualLowAltApplied) Bdark *= 1 + 0.4 * Math.max(0, Xs - 1);
    const baseSkySqm = magFromNL(Bdark);
    const twilightBaseNL = twilightExcessNLCalibrated(p.sunDepressionDeg, baseSkySqm, p.twilightCalibrationRows);
    return twilightBaseNL * directionalTwilightFactor(p);
  };

  localSkyBrightnessComponents = function (p) {
    const provider = window.__twilightProvider;
    // Provider only applies to the ordinary physical path. live-total and any
    // user-supplied static total SQM bypass the LUT entirely (directive #1).
    if (!provider || p.skyBrightnessMode === "live-total") {
      return originalLSBC(p);
    }
    // Compute the ORIGINAL components first: this reuses the untouched Bdark
    // (baseSkyNL) and Bmoon (moonBrightnessNL) EXACTLY and preserves every field
    // the production code produces. We then override ONLY the twilight excess.
    const orig = originalLSBC(p);
    const provided = provider({
      sunDepressionDeg: p.sunDepressionDeg,
      targetApparentAltitudeDeg: p.starAppAltDeg,
      relativeAzimuthDeg: p.relativeAzimuthDeg,
      sunStarSeparationDeg: p.sunStarSeparationDeg,
      baselineSqm: orig.baseSkySqm,
      aod550: p.aod550,
      observerElevationM: p.observerElevationM,
      atmosphereScenario: p.atmosphereScenario,
      surfaceAlbedo: p.surfaceAlbedo,
      timestamp: p.timestamp,
      _p: p, _orig: orig
    });
    window.__providerLastMeta = provided && provided.metadata || null;
    const Btwi = (provided && Number.isFinite(provided.twilightNl))
               ? provided.twilightNl : orig.twilightAddedNL;   // fail-safe: legacy
    const Bdark = orig.baseSkyNL, Bmoon = orig.moonBrightnessNL || 0;
    return Object.assign({}, orig, {
      twilightAddedNL: Btwi,
      skyBrightnessMagArcsec2: magFromNL(Bdark + Btwi + Bmoon),
      twilightReferenceSqmAfterCorrection: magFromNL(Bdark + Btwi),
      twilightCurveMode: "experimental-provider",
      providerStatus: provided && provided.status || null,
      providerMetadata: provided && provided.metadata || null
    });
  };
  window.__twilightProviderInstalled = true;
})();
`;

// A legacy provider expressed in the page: returns exactly the original Btwi
// (from the original components already computed), so the total is identical.
export const LEGACY_PROVIDER_SRC = `
window.installTwilightProvider(function (q) {
  return { twilightNl: q._orig.twilightAddedNL, status: "legacy-provider",
           uncertainty: null, metadata: { mode: "legacy-provider" } };
});
`;
