"""Koomen, Lock, Packer, Scolnik, Tousey & Hulburt (1952) twilight brightness.

Primary source: JOSA 42, 353. DOI 10.1364/JOSA.42.000353.
Photopic directional twilight-brightness tables at Maryland (~30 m) and
Sacramento Peak (~2800 m), multiple sky directions and solar altitudes, plus
illumination on oriented surfaces (Table III).

>>> The paper PDF could not be downloaded in the build environment (DOI server
>>> HTTP 000). The numeric tables must be MANUALLY TRANSCRIBED from the primary
>>> paper into validation-data/koomen_tableN.csv before the directional-ratio
>>> comparison can run. This module provides the historical-unit machinery and
>>> the ratio-comparison framework so that transcription is the only missing
>>> step. Directional RATIOS within one table are unit-free and avoid the
>>> historical zero-point ambiguity, so they are the primary comparison.

Historical units:
- "candles per square foot" (cd/ft^2) is a luminance. 1 cd/ft^2 = 10.7639
  cd/m^2 (1 ft^2 = 0.09290304 m^2, so per-area luminance multiplies by 1/that).
- Compact decimal notation like "0.0_2 56" (a subscript count of intermediate
  zeros) means 0.00056: the subscript N inserts N zeros after the leading
  "0.0" before the given digits.
"""
import re

CD_M2_PER_CD_FT2 = 1.0 / 0.09290304    # 10.7639


def parse_compact_decimal(text):
    """Parse Koomen-style compact decimals.
    '0.0256'      -> 0.0256
    '0.0_2 56' or '0.0₂56' or '0.0(2)56' -> 0.00056
    The subscript/paren integer N after '0.0' inserts N extra zeros before the
    trailing significant digits."""
    s = str(text).strip().replace(" ", "")
    # normalise unicode subscripts 0-9 to (n)
    subs = {"₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
            "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9"}
    for k, v in subs.items():
        s = s.replace(k, f"({v})")
    m = re.match(r"^0\.0\((\d)\)(\d+)$", s)
    if m:
        n = int(m.group(1))
        digits = m.group(2)
        return float("0.0" + "0" * n + digits)
    m = re.match(r"^0\.0_(\d)(\d+)$", s)
    if m:
        n = int(m.group(1))
        return float("0.0" + "0" * n + m.group(2))
    return float(s)


def cd_ft2_to_cd_m2(value):
    return value * CD_M2_PER_CD_FT2


def directional_ratios(table_rows):
    """table_rows: list of dicts with keys 'targetAltitudeDeg',
    'relativeAzimuthDeg', 'luminance'. Returns sunward/antisolar ratio and a
    per-altitude ratio map for one solar-altitude table. Unit-free."""
    by = {}
    for r in table_rows:
        by[(r["targetAltitudeDeg"], r["relativeAzimuthDeg"])] = r["luminance"]
    out = {"pairs": {}}
    for (alt, raz), L in by.items():
        anti = by.get((alt, 180))
        if anti and anti > 0 and raz == 0:
            out["pairs"][alt] = L / anti
    return out


if __name__ == "__main__":
    for t in ("0.0256", "0.0₂56", "0.0_2 56", "0.0(3)7", "1.23"):
        print(f"{t!r:12} -> {parse_compact_decimal(t)}")
