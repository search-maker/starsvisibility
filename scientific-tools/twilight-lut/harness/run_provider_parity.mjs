// FC-6 (step 1): prove that the solar-twilight provider seam, with the
// legacy-provider, reproduces the UNMODIFIED production localSkyBrightness
// components EXACTLY, across a grid of geometries and observer/sky settings,
// including the total sky magnitude and the downstream limiting magnitude.
//
// This drives the REAL production index.html physics in a real (headless)
// Chromium; it never edits the production file. Usage:
//   node harness/run_provider_parity.mjs [path/to/index.html]
import { chromium } from 'playwright';
import { INJECT_SRC, LEGACY_PROVIDER_SRC } from './twilight_provider.mjs';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';
import { writeFileSync, mkdirSync } from 'fs';

const HERE = dirname(fileURLToPath(import.meta.url));
const INDEX = process.argv[2] || resolve(HERE, '../../../index.html');
const CHROME = process.env.PW_CHROME
  || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

function grid() {
  const cases = [];
  const deps = [0, 2, 4, 6, 8, 10, 12];
  const alts = [3, 10, 30, 60, 90];
  const seps = [0, 30, 90, 150, 180];
  const bases = [21.8, 19.0];
  for (const d of deps) for (const a of alts) for (const s of seps) for (const b of bases)
    cases.push({ sunDepressionDeg: d, starAppAltDeg: a, sunStarSeparationDeg: s,
                 relativeAzimuthDeg: s, baselineSqm: b });
  // a few Moon-on cases too
  for (const d of [4, 8]) for (const a of [10, 60])
    cases.push({ sunDepressionDeg: d, starAppAltDeg: a, sunStarSeparationDeg: 45,
                 relativeAzimuthDeg: 45, baselineSqm: 21.8,
                 moonAltDeg: 40, moonIllumination: 0.9, moonStarSeparationDeg: 60 });
  return cases;
}

const browser = await chromium.launch({ executablePath: CHROME });
const page = await browser.newPage();
const pageErrors = [];
page.on('pageerror', e => pageErrors.push(String(e)));
await page.goto('file://' + INDEX, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(400);
await page.evaluate(INJECT_SRC);

const result = await page.evaluate(({ cases, legacySrc }) => {
  const rows = [];
  const call = (p) => localSkyBrightnessComponents(Object.assign({
    sqmZenith: p.baselineSqm, baselineIsDirectional: false,
    manualLowAltApplied: false, kV: 0.28, skyBrightnessMode: "physical",
    liveTotalSqm: null, twilightCalibrationRows: null,
    moonAltDeg: -90, moonIllumination: 0, moonStarSeparationDeg: 180,
    aod550: 0.15
  }, p));
  const nelm = (sb) => limitingMagnitudeFromSkyBrightness({ skyBrightnessMagArcsec2: sb });

  for (const c of cases) {
    window.uninstallTwilightProvider();
    const base = call(c);
    // eslint-disable-next-line no-eval
    eval(legacySrc);                    // installs legacy-provider
    const prov = call(c);
    window.uninstallTwilightProvider();
    const dTwi = Math.abs(base.twilightAddedNL - prov.twilightAddedNL);
    const dMag = Math.abs(base.skyBrightnessMagArcsec2 - prov.skyBrightnessMagArcsec2);
    const dNelm = Math.abs(nelm(base.skyBrightnessMagArcsec2) - nelm(prov.skyBrightnessMagArcsec2));
    rows.push({ c, dTwi, dMag, dNelm });
  }
  const maxTwi = Math.max(...rows.map(r => r.dTwi));
  const maxMag = Math.max(...rows.map(r => r.dMag));
  const maxNelm = Math.max(...rows.map(r => r.dNelm));
  return { n: rows.length, maxTwi, maxMag, maxNelm,
           exact: (maxTwi === 0 && maxMag === 0 && maxNelm === 0) };
}, { cases: grid(), legacySrc: LEGACY_PROVIDER_SRC });

result.pageErrors = pageErrors.length;
result.pass = result.exact && pageErrors.length === 0;
mkdirSync(resolve(HERE, '../reports'), { recursive: true });
writeFileSync(resolve(HERE, '../reports/provider-parity.json'),
              JSON.stringify(result, null, 1));
console.log(JSON.stringify(result, null, 1));
await browser.close();
process.exit(result.pass ? 0 : 1);
