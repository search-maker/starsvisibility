#!/usr/bin/env python3
"""Migrate legacy flat raw-output/<caseId>/ into the immutable
raw-output/<caseId>/attempt-000/ + active.json layout, backfilling
configurationHash from the stored meta. Idempotent; never deletes data.

The legacy Milestone-2 runs are expensive real MYSTIC output; this preserves
them under the reproducible scheme instead of re-running.
"""
import json
import shutil
from lrt_common import (RAW_DIR, configuration_hash, canonical_config,
                        data_provenance, find_uvspec, find_data_dir,
                        uvspec_version)

RUN_FILES = ("case.inp", "wavelengths.dat", "mc.rad.spc", "mc.rad.std.spc",
             "mc.flx.spc", "mc.flx.std.spc", "stdout.txt", "stderr.txt",
             "randomseed", "meta.json")
RUN_PREFIXES = ("mc",)   # mc0.rad etc.


def migrate():
    uvspec_ver = uvspec_version(find_uvspec())
    prov = data_provenance(find_data_dir())
    migrated = skipped = 0
    for cdir in sorted(RAW_DIR.iterdir()):
        if not cdir.is_dir():
            continue
        if (cdir / "active.json").exists():
            skipped += 1
            continue
        legacy_meta = cdir / "meta.json"
        if not legacy_meta.exists():
            continue
        meta = json.loads(legacy_meta.read_text())
        adir = cdir / "attempt-000"
        adir.mkdir(exist_ok=True)
        for f in cdir.iterdir():
            if f.is_dir():
                continue
            if f.name in RUN_FILES or any(f.name.startswith(p) for p in RUN_PREFIXES):
                shutil.move(str(f), str(adir / f.name))
        # backfill configurationHash into the moved meta
        cfg = canonical_config(meta)
        cfg_hash = configuration_hash(meta, uvspec_ver, prov)
        meta["configurationHash"] = cfg_hash
        meta["canonicalConfig"] = cfg
        meta["dataProvenance"] = prov
        meta.setdefault("attempt", "attempt-000")
        meta.setdefault("uvspecVersion", uvspec_ver)
        (adir / "meta.json").write_text(json.dumps(meta, indent=1))
        (cdir / "active.json").write_text(json.dumps({
            "caseId": cdir.name, "selectedAttempt": "attempt-000",
            "configurationHash": cfg_hash, "status": meta.get("status"),
            "latestAttempt": "attempt-000", "totalAttempts": 1,
            "migratedFromLegacyFlatLayout": True,
        }, indent=1))
        migrated += 1
    print(f"migrated {migrated} legacy case(s), skipped {skipped} already-migrated")


if __name__ == "__main__":
    migrate()
