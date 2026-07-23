#!/usr/bin/env python3
"""Collect raw MYSTIC outputs into processed-output/spectral_results.json.

Distinguishes real output (meta.json: outputIsReal) and records per-case
status. Detects incomplete/malformed files instead of hiding them.
"""
import json
from pathlib import Path
from lrt_common import RAW_DIR, PROCESSED_DIR, WAVELENGTH_NM, parse_spc


def collect_case(cdir: Path):
    meta_file = cdir / "meta.json"
    if not meta_file.exists():
        return {"caseId": cdir.name, "status": "no-meta"}
    meta = json.loads(meta_file.read_text())
    rec = {**meta}
    rad_f, std_f = cdir / "mc.rad.spc", cdir / "mc.rad.std.spc"
    if meta.get("status") != "ok":
        return rec
    try:
        rad = parse_spc(rad_f)
        std = parse_spc(std_f) if std_f.exists() else {}
    except (OSError, ValueError) as e:
        rec["status"] = f"parse-error: {e}"
        return rec
    wl = sorted(rad)
    missing = [w for w in WAVELENGTH_NM if not any(abs(w - x) < 0.5 for x in wl)]
    if missing:
        rec["status"] = f"incomplete-spectrum-missing-{len(missing)}"
        rec["missingWavelengths"] = missing
        return rec
    rec["wavelengthNm"] = wl
    rec["radiance_mW_m2_nm_sr"] = [rad[w] for w in wl]
    rec["radianceStd_mW_m2_nm_sr"] = [std.get(w) for w in wl]
    return rec


def main():
    PROCESSED_DIR.mkdir(exist_ok=True)
    records = [collect_case(d) for d in sorted(RAW_DIR.iterdir()) if d.is_dir()]
    out = PROCESSED_DIR / "spectral_results.json"
    out.write_text(json.dumps(records, indent=1))
    ok = sum(1 for r in records if r.get("status") == "ok")
    print(f"collected {len(records)} cases ({ok} ok) -> {out}")


if __name__ == "__main__":
    main()
