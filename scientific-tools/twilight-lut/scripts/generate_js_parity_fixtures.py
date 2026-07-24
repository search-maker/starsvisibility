#!/usr/bin/env python3
"""RH-5: generate current-model parity fixtures from the REAL production
JavaScript in index.html (run via node), so the Python port is validated
against the actual implementation — not against the same Python formulas.

Extracts the exact source of the needed functions/constants from index.html by
brace matching, wraps them in a node driver with the production global defaults
(currentTemperatureC=10, currentPressureHPa=1010), evaluates a fixed input set,
and writes fixtures/js_parity_fixtures.json.
"""
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent            # repo root containing index.html
INDEX = REPO / "index.html"
FIXTURES = ROOT / "fixtures"

# Named JS declarations to extract verbatim (functions and const arrays/scalars).
FUNCS = ["toRad", "toDeg", "refractionDeg", "apparentAltitude", "airMass",
         "nLFromMag", "magFromNL", "smoothstep01", "lerp",
         "legacyTwilightExcessNL", "defaultTwilightAddedNLAfter6",
         "twilightExcessNL", "directionalTwilightFactor",
         "limitingMagnitudeFromSkyBrightness", "angularSeparation"]
CONSTS = ["TWILIGHT_ANCHORS", "TWILIGHT_POST6_SLOPE_MAG_PER_DEG",
          "TWILIGHT_FAST_SEGMENT_END_DEG", "TWILIGHT_NIGHT_BLEND_END_DEG",
          "OLD_TWILIGHT_LOG_NL_AT_6", "OLD_TWILIGHT_NL_AT_6", "TWILIGHT_SQM_AT_6"]


def extract_function(src, name):
    m = re.search(r"\n\s*function\s+" + re.escape(name) + r"\s*\(", src)
    if not m:
        raise ValueError(f"function {name} not found")
    i = src.index("{", m.end() - 1)
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return src[m.start():j + 1].strip()


def extract_const(src, name):
    m = re.search(r"\n\s*const\s+" + re.escape(name) + r"\s*=", src)
    if not m:
        raise ValueError(f"const {name} not found")
    # capture to the terminating semicolon at brace/paren depth 0
    i = m.end()
    depth, j = 0, i
    while j < len(src):
        c = src[j]
        if c in "[{(":
            depth += 1
        elif c in "]})":
            depth -= 1
        elif c == ";" and depth == 0:
            break
        j += 1
    return src[m.start():j + 1].strip()


INPUTS = {
    "refraction_apparent": [
        {"hTrue": h} for h in (-1, 0, 5, 10, 15, 30, 45, 60, 90)],
    "airmass": [{"hApp": h} for h in (5, 10, 30, 60, 90)],
    "twilightExcessNL": [{"dep": d, "base": 21.8}
                         for d in (0, 2, 4, 6, 8, 10, 12, 16)],
    "directionalFactor": [{"sep": s, "h": h}
                          for s in (0, 30, 90, 180) for h in (10, 30, 90)],
    "nlmag": [{"sb": sb} for sb in (15.0, 18.0, 21.0, 21.8)],
    "nelm": [{"sb": sb} for sb in (12.0, 16.0, 19.0, 21.8)],
    "separation": [{"a1": 30, "z1": 0, "a2": 10, "z2": 90},
                   {"a1": 90, "z1": 0, "a2": 10, "z2": 180}],
}


def build_driver(src):
    parts = ["\"use strict\";",
             "let currentTemperatureC = 10;", "let currentPressureHPa = 1010;"]
    for c in CONSTS:
        parts.append(extract_const(src, c))
    for f in FUNCS:
        parts.append(extract_function(src, f))
    parts.append("const INPUTS = " + json.dumps(INPUTS) + ";")
    parts.append(r"""
const out = {};
out.refraction_apparent = INPUTS.refraction_apparent.map(x => ({
  hTrue: x.hTrue, refractionDeg: refractionDeg(x.hTrue),
  apparentAltitude: apparentAltitude(x.hTrue)}));
out.airmass = INPUTS.airmass.map(x => ({hApp: x.hApp, airMass: airMass(x.hApp)}));
out.twilightExcessNL = INPUTS.twilightExcessNL.map(x => ({
  dep: x.dep, base: x.base, nl: twilightExcessNL(x.dep, x.base)}));
out.directionalFactor = INPUTS.directionalFactor.map(x => ({
  sep: x.sep, h: x.h, factor: directionalTwilightFactor({sunStarSeparationDeg:x.sep, starAppAltDeg:x.h})}));
out.nlmag = INPUTS.nlmag.map(x => ({sb: x.sb, nl: nLFromMag(x.sb), back: magFromNL(nLFromMag(x.sb))}));
out.nelm = INPUTS.nelm.map(x => ({sb: x.sb, nelm: limitingMagnitudeFromSkyBrightness({skyBrightnessMagArcsec2:x.sb})}));
out.separation = INPUTS.separation.map(x => ({...x, sep: angularSeparation(x.a1,x.z1,x.a2,x.z2)}));
process.stdout.write(JSON.stringify(out, null, 1));
""")
    return "\n".join(parts)


def main():
    src = INDEX.read_text()
    driver = build_driver(src)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(driver)
        jsfile = f.name
    proc = subprocess.run(["node", jsfile], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("node failed:\n" + proc.stderr)
    data = json.loads(proc.stdout)
    FIXTURES.mkdir(exist_ok=True)
    out = FIXTURES / "js_parity_fixtures.json"
    out.write_text(json.dumps({
        "source": "index.html production JavaScript via node",
        "globals": {"currentTemperatureC": 10, "currentPressureHPa": 1010},
        "note": "Generated by generate_js_parity_fixtures.py; the Python port is "
                "tested against THESE values, not against its own formulas.",
        "fixtures": data}, indent=1))
    print(f"wrote {out} with {sum(len(v) for v in data.values())} fixture rows")


if __name__ == "__main__":
    main()
