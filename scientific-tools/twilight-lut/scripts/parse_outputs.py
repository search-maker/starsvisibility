#!/usr/bin/env python3
"""Collect raw MYSTIC outputs into processed-output/spectral_results.json.

uvspec computes the radiative transfer at the 41 nodes of wavelengths.dat and
outputs radiance on the fine (~0.05 nm) grid of the atlas_plus_modtran solar
spectrum (transmittance interpolation between RT nodes). We therefore store
BOTH views per case:
- fine-grid radiance, downsampled to 1 nm bin means, for accurate V(lambda)
  integration (keeps Fraunhofer-line structure at far better than V-curve
  resolution);
- the 41 RT-node values and standard errors (nearest fine sample), because MC
  noise is coherent within each RT node's neighbourhood — uncertainty must be
  propagated from nodes, not from the fine grid.
Malformed or incomplete outputs are flagged, never silently accepted.
"""
import json
from pathlib import Path
from lrt_common import (RAW_DIR, PROCESSED_DIR, WAVELENGTH_NM, parse_spc,
                        selected_attempt_dir)


def bin_1nm(pairs):
    """pairs: sorted (wavelength, value). Returns (centers, means)."""
    centers, means = [], []
    lo = int(pairs[0][0])
    cur_c, cur_sum, cur_n = lo, 0.0, 0
    for w, v in pairs:
        c = int(round(w))
        if c != cur_c:
            if cur_n:
                centers.append(cur_c)
                means.append(cur_sum / cur_n)
            cur_c, cur_sum, cur_n = c, 0.0, 0
        cur_sum += v
        cur_n += 1
    if cur_n:
        centers.append(cur_c)
        means.append(cur_sum / cur_n)
    return centers, means


def nearest(pairs_dict, target):
    w = min(pairs_dict, key=lambda x: abs(x - target))
    if abs(w - target) > 1.0:
        return None
    return pairs_dict[w]


def resolve_run_dir(cdir: Path):
    """Return the directory holding the run files. New layout: the selected
    attempt under active.json. Legacy flat layout: the case dir itself."""
    sel = selected_attempt_dir(cdir)
    if sel is not None:
        return sel
    if (cdir / "meta.json").exists():   # legacy flat M2 layout
        return cdir
    return None


def collect_case(case_dir: Path):
    cdir = resolve_run_dir(case_dir)
    if cdir is None:
        return {"caseId": case_dir.name, "status": "no-meta"}
    meta_file = cdir / "meta.json"
    if not meta_file.exists():
        return {"caseId": case_dir.name, "status": "no-meta"}
    rec = json.loads(meta_file.read_text())
    if rec.get("status") != "ok":
        return rec
    rad_f, std_f = cdir / "mc.rad.spc", cdir / "mc.rad.std.spc"
    try:
        rad = parse_spc(rad_f)
        std = parse_spc(std_f) if std_f.exists() else {}
    except (OSError, ValueError) as e:
        rec["status"] = f"parse-error: {e}"
        return rec
    if not rad:
        rec["status"] = "empty-radiance"
        return rec
    node_rad, node_std = [], []
    missing = []
    for w in WAVELENGTH_NM:
        v = nearest(rad, w)
        if v is None:
            missing.append(w)
            continue
        node_rad.append(v)
        node_std.append(nearest(std, w) if std else None)
    if missing:
        rec["status"] = f"incomplete-spectrum-missing-{len(missing)}"
        rec["missingWavelengths"] = missing
        return rec
    pairs = sorted(rad.items())
    centers, means = bin_1nm(pairs)
    rec["fineGridPoints"] = len(pairs)
    rec["binnedWavelengthNm"] = centers
    rec["binnedRadiance_mW_m2_nm_sr"] = means
    rec["nodeWavelengthNm"] = WAVELENGTH_NM
    rec["nodeRadiance_mW_m2_nm_sr"] = node_rad
    rec["nodeRadianceStd_mW_m2_nm_sr"] = node_std
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
