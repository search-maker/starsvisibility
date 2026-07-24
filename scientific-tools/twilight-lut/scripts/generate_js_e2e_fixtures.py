#!/usr/bin/env python3
"""PG-2: end-to-end current-model fixtures from the REAL production JavaScript.

Runs the COMPLETE production chain in node — localSkyBrightnessComponents (Btwi,
total sky brightness) and limitingMagnitudeFromSkyBrightness (NELM) — for
representative low/medium/zenith target altitudes, and records the geometric vs
apparent altitude handling explicitly, so the Python chain is validated
end-to-end (not only function by function).

Writes fixtures/js_e2e_fixtures.json.
"""
import json
import subprocess
import tempfile
from pathlib import Path
from generate_js_parity_fixtures import extract_function, extract_const, INDEX

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

FUNCS = ["toRad", "toDeg", "norm360", "finiteProvidedValue", "refractionInfo",
         "refractionDeg", "apparentAltitude",
         "airMass", "nLFromMag", "magFromNL", "smoothstep01", "lerp",
         "legacyTwilightExcessNL", "defaultTwilightAddedNLAfter6",
         "twilightExcessNL", "interpolateSkyBrightnessBySunDep",
         "twilightExcessNLCalibrated", "directionalTwilightFactor",
         "moonBrightnessNL", "localSkyBrightnessComponents",
         "limitingMagnitudeFromSkyBrightness", "angularSeparation"]
ATMO_STATE = {"pressureHPa": 1010, "temperatureC": 10}
CONSTS = ["TWILIGHT_ANCHORS", "TWILIGHT_POST6_SLOPE_MAG_PER_DEG",
          "TWILIGHT_FAST_SEGMENT_END_DEG", "TWILIGHT_NIGHT_BLEND_END_DEG",
          "OLD_TWILIGHT_LOG_NL_AT_6", "OLD_TWILIGHT_NL_AT_6", "TWILIGHT_SQM_AT_6"]

# Representative cases: depression x (geometric target altitude, rel azimuth)
CASES = []
for dep in (2, 4, 6, 8):
    for alt in (10, 30, 90):           # low, medium, zenith
        for raz in (0, 90, 180):
            if alt == 90 and raz != 0:
                continue
            CASES.append({"dep": dep, "alt": alt, "raz": raz, "baselineSqm": 21.8})


def build_driver(src):
    parts = ['"use strict";',
             "let currentTemperatureC = 10;", "let currentPressureHPa = 1010;"]
    for c in CONSTS:
        parts.append(extract_const(src, c))
    for f in FUNCS:
        parts.append(extract_function(src, f))
    parts.append("const CASES = " + json.dumps(CASES) + ";")
    parts.append(r"""
function sunAltAz(dep){ return {alt: -dep, az: 0}; }
const out = CASES.map(c => {
  // production: target true altitude c.alt, azimuth c.raz (relative to sun az 0)
  const sTrueAlt = c.alt, sAz = c.raz;
  const sun = sunAltAz(c.dep);
  const starAppAlt = apparentAltitude(sTrueAlt, {pressureHPa:1010,temperatureC:10}) ?? sTrueAlt;
  const sunSep = angularSeparation(sTrueAlt, sAz, sun.alt, sun.az); // GEOMETRIC
  const comp = localSkyBrightnessComponents({
    sqmZenith: c.baselineSqm, baselineSqm: c.baselineSqm,
    baselineIsDirectional: false, manualLowAltApplied: false, kV: 0.28,
    skyBrightnessMode: "physical", liveTotalSqm: null, twilightCalibrationRows: null,
    sunDepressionDeg: c.dep, sunStarSeparationDeg: sunSep,
    starAppAltDeg: starAppAlt, moonAltDeg: -90, moonIllumination: 0,
    moonStarSeparationDeg: 180
  });
  const nelm = limitingMagnitudeFromSkyBrightness({
    skyBrightnessMagArcsec2: comp.skyBrightnessMagArcsec2, starAppAltDeg: starAppAlt
  });
  return {dep: c.dep, geometricAlt: sTrueAlt, apparentAlt: starAppAlt, raz: c.raz,
          baselineSqm: c.baselineSqm, sunStarSeparationDeg: sunSep,
          twilightAddedNL: comp.twilightAddedNL, baseSkyNL: comp.baseSkyNL,
          totalSkyMag: comp.skyBrightnessMagArcsec2, nelm: nelm};
});
process.stdout.write(JSON.stringify(out, null, 1));
""")
    return "\n".join(parts)


def main():
    src = INDEX.read_text()
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(build_driver(src))
        jsfile = f.name
    proc = subprocess.run(["node", jsfile], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("node failed:\n" + proc.stderr)
    data = json.loads(proc.stdout)
    FIXTURES.mkdir(exist_ok=True)
    out = FIXTURES / "js_e2e_fixtures.json"
    out.write_text(json.dumps({
        "source": "index.html production JS via node (full chain)",
        "chain": "localSkyBrightnessComponents (Btwi, total sky) + "
                 "limitingMagnitudeFromSkyBrightness (NELM); moonless, "
                 "zenith-referenced baseline SQM 21.8, kV 0.28",
        "geometryContract": "sunStarSeparation from GEOMETRIC target altitude; "
                            "directionalFactor + airmass + horizon brightening "
                            "from APPARENT altitude",
        "cases": data}, indent=1))
    print(f"wrote {out} with {len(data)} end-to-end cases")


if __name__ == "__main__":
    main()
