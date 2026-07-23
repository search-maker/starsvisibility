# Monte Carlo uncertainty from independent seeds

## dep 4 deg, alt 30 deg, relAz 90 deg, AOD 0.15

- seeds: 6, photons/case: 8,000,000
- luminance mean 8.636 cd/m2, empirical std 0.072 (0.8%)
- mean reported std 0.086 -> empirical/reported ratio 0.83
- values: 8.564, 8.576, 8.6, 8.629, 8.716, 8.732

## dep 8 deg, alt 10 deg, relAz 90 deg, AOD 0.15

- seeds: 6, photons/case: 40,000,000
- luminance mean 0.1732 cd/m2, empirical std 0.0037 (2.1%)
- mean reported std 0.0053 -> empirical/reported ratio 0.69
- values: 0.1692, 0.1701, 0.1713, 0.1744, 0.1756, 0.1789

## Verdict

Worst empirical/reported ratio: 0.83. Ratios well above 1 mean the reported standard errors underestimate the true scatter (heavy-tailed VROOM estimator); LUT-node uncertainties must then be taken from repeats, not from the reported std alone.
