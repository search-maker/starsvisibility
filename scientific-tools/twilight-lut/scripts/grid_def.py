#!/usr/bin/env python3
"""Single source of truth for the LUT grid geometry and its derived costs.

Every node count, per-depression count, photon budget, repeat count,
validation-run count, CPU/wall-time projection and storage estimate in the
reports is DERIVED from this module. No such figure may be hand-written
elsewhere (a test enforces the key ones).

Key structural rules encoded here:
- At target altitude 90 deg (zenith) relative azimuth is physically degenerate:
  exactly ONE zenith node per (depression, AOD), never one per azimuth.
- Angular separation is NOT an axis (it is derived from dep, alt, relAz).
- The AOD axis represents ONE Shettle rural aerosol family + vertical profile.
- Photon budget scales with depression (measured 1/sqrt(N) convergence).
"""
from dataclasses import dataclass, field, asdict

# Runtime model calibrated from Milestone 2 timings (uvspec 2.0.6-MYSTIC,
# 41-wavelength spectral case, single core): seconds ~= photons / RATE.
PHOTONS_PER_SEC = 200_000        # ~1.0 s at 2e5 photons (measured)

PHOTONS_BY_DEPRESSION = {0: 2_000_000, 2: 2_000_000, 4: 8_000_000,
                         6: 20_000_000, 8: 40_000_000, 10: 100_000_000}

# Raw output measured at ~2.2 MB/case (41-wl fine grid + std). Processed node
# record ~ 6 kB/case in the consolidated JSON.
RAW_MB_PER_CASE = 2.2
PROCESSED_KB_PER_CASE = 6.0


@dataclass
class GridDefinition:
    """The canonical proof-of-concept grid. `core` is the fully-supported
    0-8 deg block; `extension` (9-10 deg) is gated on pre-grid hardening."""
    depressions_core: tuple = (0, 2, 4, 6, 8)
    depressions_ext: tuple = ()          # filled only if hardening supports it
    altitudes: tuple = (10, 15, 30, 45, 60, 90)
    relative_azimuths: tuple = (0, 30, 60, 90, 120, 150, 180)
    aods: tuple = (0.05, 0.15, 0.30)
    zenith_altitude: int = 90
    # Monte Carlo repeat policy: a stratified sample, not every node.
    repeat_seed_count: int = 5
    # fraction of unique nodes that get independent-seed repeats
    repeat_fraction: float = 0.12
    # independent non-grid interpolation-validation simulations
    validation_run_count: int = 60
    jobs: int = 4

    @property
    def depressions(self):
        return tuple(sorted(set(self.depressions_core) | set(self.depressions_ext)))

    def unique_nodes(self):
        """List of (dep, alt, relAz, aod) with zenith azimuth deduplicated."""
        nodes = []
        for dep in self.depressions:
            for aod in self.aods:
                for alt in self.altitudes:
                    if alt == self.zenith_altitude:
                        nodes.append((dep, alt, 0, aod))   # single zenith node
                    else:
                        for raz in self.relative_azimuths:
                            nodes.append((dep, alt, raz, aod))
        return nodes

    def counts(self):
        nodes = self.unique_nodes()
        by_dep, by_photons = {}, {}
        for dep, alt, raz, aod in nodes:
            by_dep[dep] = by_dep.get(dep, 0) + 1
            ph = PHOTONS_BY_DEPRESSION[dep]
            by_photons[ph] = by_photons.get(ph, 0) + 1
        n = len(nodes)
        n_repeat_nodes = round(n * self.repeat_fraction)
        n_repeat_runs = n_repeat_nodes * self.repeat_seed_count
        # CPU seconds: one production run per node + repeats + validation runs.
        cpu = sum(PHOTONS_BY_DEPRESSION[d] for d, _, _, _ in nodes) / PHOTONS_PER_SEC
        # repeats use the same per-node photon budget (stratified ~ mean node)
        mean_node_ph = sum(PHOTONS_BY_DEPRESSION[d] for d, _, _, _ in nodes) / n
        cpu += n_repeat_runs * mean_node_ph / PHOTONS_PER_SEC
        cpu += self.validation_run_count * mean_node_ph / PHOTONS_PER_SEC
        total_runs = n + n_repeat_runs + self.validation_run_count
        return {
            "uniqueNodeCount": n,
            "nodesByDepression": by_dep,
            "nodesByPhotonBudget": by_photons,
            "zenithNodesPerDepAod": 1,
            "repeatNodeCount": n_repeat_nodes,
            "repeatSeedCount": self.repeat_seed_count,
            "repeatRunCount": n_repeat_runs,
            "validationRunCount": self.validation_run_count,
            "totalSimulationRuns": total_runs,
            "projectedCpuHours": round(cpu / 3600, 2),
            "projectedWallHoursAtJobs": round(cpu / 3600 / self.jobs, 2),
            "jobs": self.jobs,
            "projectedRawMB": round(total_runs * RAW_MB_PER_CASE, 1),
            "projectedProcessedMB": round(total_runs * PROCESSED_KB_PER_CASE / 1024, 2),
            "photonsByDepression": PHOTONS_BY_DEPRESSION,
        }

    def describe(self):
        return {"axes": {
            "depressions": list(self.depressions),
            "depressionsCore": list(self.depressions_core),
            "depressionsExtension": list(self.depressions_ext),
            "altitudes": list(self.altitudes),
            "relativeAzimuths": list(self.relative_azimuths),
            "aod550": list(self.aods),
        }, "counts": self.counts()}


DEFAULT_GRID = GridDefinition()


if __name__ == "__main__":
    import json
    print(json.dumps(DEFAULT_GRID.describe(), indent=1))
