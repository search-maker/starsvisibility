#!/usr/bin/env python3
"""Run feasibility cases through real uvspec (MYSTIC 1D spherical, backward).

Restartable: completed cases (status ok in meta.json) are skipped.
Use --overwrite to force regeneration; raw output is never silently replaced.
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from lrt_common import (CASES_DIR, RAW_DIR, find_data_dir, find_uvspec,
                        run_case)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(CASES_DIR / "feasibility_cases.json"))
    ap.add_argument("--group", default=None, help="only run this case group")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--max-cases", type=int, default=None)
    ap.add_argument("--jobs", type=int, default=4,
                    help="parallel uvspec processes (each case is independent)")
    args = ap.parse_args()

    uvspec = find_uvspec()
    data_dir = find_data_dir(uvspec)
    cases = json.loads(open(args.cases).read())
    if args.group:
        cases = [c for c in cases if c["group"] == args.group]
    if args.max_cases:
        cases = cases[: args.max_cases]
    RAW_DIR.mkdir(exist_ok=True)
    results, failed, done = [], 0, 0
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for r in ex.map(lambda c: run_case(c, uvspec, data_dir,
                                           overwrite=args.overwrite), cases):
            done += 1
            results.append(r)
            ok = r["status"] in ("ok", "skipped-complete")
            failed += 0 if ok else 1
            rt = r.get("runtimeSeconds")
            print(f"[{done}/{len(cases)}] {r['caseId']}: {r['status']}"
                  + (f" ({rt:.1f}s)" if rt is not None else ""), flush=True)
    print(f"done: {len(results) - failed} ok / {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
