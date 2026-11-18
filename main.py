"""Forecast Twitch viewers in the "Grand Theft Auto VI" category, hours 2..24
of release day (2026-11-19 UTC), from the hour-1 print and the comparables
in the case file.

Method (fit fresh at run time from the case's own comparables, so the same
program works for a practice case and for the final):
  1. Take every comparable launch's release-day hourly curve (hours 1..24).
  2. Keep only launches that look like a rolling midnight unlock: a full
     24 hours, a positive hour-1 print, and a day peak no more than 15x
     hour 1. This drops simultaneous global unlocks (near-zero hour 1,
     then a 100-2000x explosion), which follow a different shape.
  3. Weight the four big console-exclusive practice launches (Wolverine,
     Red Dead Redemption 2, God of War Ragnarok, Spider-Man 2) x3: they
     are the closest analogues to GTA VI (console-only, rolling midnight,
     huge single-player hype). Every other launch weighs 1.
  4. For each hour h, the centre forecast is the weighted geometric mean
     of the launches' ratios curve[h] / curve[1], anchored on this case's
     hour-1 print p1. The spread is the weighted log-standard-deviation
     of those ratios, floored by the house baseline's random-walk spread
     0.15 * sqrt(h - 1) (so early hours, where launches agree, still get
     a sane minimum width) and capped at 0.8.
  5. Quantiles: q_tau(h) = p1 * ratio(h) * exp(z_tau * spread(h)).

Why this shape: across past big launches the median curve dips after
hour 1 (UTC night, only New Zealand / Australia / Europe awake), jumps
at hour 5 (US Eastern midnight unlock), sags midday, then climbs to a
US-evening peak around hours 18-22 before easing off. Anchoring on the
case's own hour-1 print carries the launch's size; the ratio curve
carries the shape; the widening spread carries the growing uncertainty.

Stdlib only, no network, deterministic: same input bytes give the same
output bytes. Reads every <id>.in in MAKEFUN_INPUT_DIR (default /input),
writes <id>.out to MAKEFUN_OUTPUT_DIR (default /output).
"""

import json
import math
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

# The grader's -P leaves the program directory off sys.path; nothing to
# import from beside this file, but keep the line harmless.
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

# Random-walk spread per sqrt-hour (the house baseline's figure); used as
# the floor for each hour's spread.
SIGMA = 0.15
# Widest log-spread any hour is allowed (keeps the 5% / 95% quantiles
# inside a sane band even for the most uncertain late hours).
SPREAD_CAP = 0.8
# A launch counts as a rolling midnight unlock when its day peak is at
# most this many times its hour-1 print.
ROLLING_PEAK_RATIO = 15.0
# Extra weight for the four closest analogue launches.
PRACTICE_WEIGHT = 3.0

# The four big console-exclusive practice launches, by normalised name.
# Normalisation (lowercase, accents stripped, non-alphanumerics dropped)
# is applied to both sides, so "God of War Ragnarok" matches with or
# without the o-umlaut.
PRACTICE_LAUNCHES = {
    "marvelswolverine",
    "reddeadredemption2",
    "godofwarragnarok",
    "marvelsspiderman2",
}


def normalise_name(name):
    """Lowercase, strip accents, drop every non-alphanumeric character."""
    folded = unicodedata.normalize("NFKD", str(name))
    ascii_only = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", ascii_only.lower())


def round2(x):
    """Round to 2 decimals, half up (the starter's convention). A whole
    number comes back as an int so the JSON writes 1240, not 1240.0."""
    scaled = x * 100.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100.0
    return int(value) if value.is_integer() else value


def parse_ts(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


def release_day_curve(comp):
    """A comparable's release-day curve as {hour: viewers} for hours 1..24,
    or an empty dict when the day is incomplete."""
    try:
        start = parse_ts(comp["day_start"])
    except (KeyError, TypeError, ValueError):
        return {}
    curve = {}
    for row in comp.get("hourly") or []:
        try:
            when = parse_ts(row["from"])
            viewers = row["viewers"]
        except (KeyError, TypeError, ValueError):
            continue
        if viewers is None or viewers <= 0:
            continue
        hour = int((when - start).total_seconds() // 3600) + 1
        if 1 <= hour <= 24:
            curve[hour] = float(viewers)
    return curve


def launch_weight(name):
    """3.0 for the four closest analogue launches, else 1.0."""
    return PRACTICE_WEIGHT if normalise_name(name) in PRACTICE_LAUNCHES else 1.0


def fit_model(comparables):
    """Fit the ratio curve and per-hour log-spread from the comparables.

    Returns (ratio, spread): dicts keyed by hour 2..24, or (None, None)
    when nothing usable was found (caller falls back to persistence).
    """
    curves = []
    for comp in comparables or []:
        curve = release_day_curve(comp)
        if len(curve) < 24 or curve.get(1, 0) <= 0:
            continue
        peak = max(curve.values())
        if peak / curve[1] > ROLLING_PEAK_RATIO:
            continue  # simultaneous global unlock: a different shape
        curves.append((curve, launch_weight(comp.get("name", ""))))
    if len(curves) < 5:
        # Too few rolling launches: relax the peak filter once, then give
        # up on the filter entirely rather than forecasting blind.
        relaxed = []
        for comp in comparables or []:
            curve = release_day_curve(comp)
            if len(curve) < 24 or curve.get(1, 0) <= 0:
                continue
            peak = max(curve.values())
            if peak / curve[1] <= 30.0:
                relaxed.append((curve, launch_weight(comp.get("name", ""))))
        if len(relaxed) >= 5:
            curves = relaxed
        else:
            unfiltered = []
            for comp in comparables or []:
                curve = release_day_curve(comp)
                if len(curve) < 24 or curve.get(1, 0) <= 0:
                    continue
                unfiltered.append((curve, launch_weight(comp.get("name", ""))))
            if len(unfiltered) >= 5:
                curves = unfiltered
    if not curves:
        return None, None

    ratio, spread = {}, {}
    for hour in range(2, 25):
        # Weighted geometric mean of the ratios, and the weighted
        # log-standard-deviation around it. Only launches that actually
        # have this hour contribute to it.
        logs = []
        for curve, weight in curves:
            if hour in curve and 1 in curve:
                logs.append((math.log(curve[hour] / curve[1]), weight))
        if not logs:
            continue
        total_weight = sum(w for _, w in logs)
        centre = sum(v * w for v, w in logs) / total_weight
        variance = sum(w * (v - centre) ** 2 for v, w in logs) / total_weight
        ratio[hour] = math.exp(centre)
        empirical = math.sqrt(variance)
        floor = SIGMA * math.sqrt(hour - 1)
        spread[hour] = min(max(empirical, floor), SPREAD_CAP)
    if not ratio:
        return None, None
    return ratio, spread


def hour_quantiles(p1, hour, ratio, spread):
    """The five quantiles for one hour, from the fitted ratio and spread."""
    centre = p1 * ratio[hour]
    return [round2(max(1.0, centre * math.exp(z * spread[hour]))) for z in Z]


def baseline_quantiles(p1, hour):
    """The house baseline (persistence + random-walk spread), used only
    when the case carries no usable comparable to fit from."""
    return [round2(max(1.0, p1 * math.exp(z * SIGMA * math.sqrt(hour - 1))))
            for z in Z]


def forecast_case(case, name):
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name} asks for levels {case.get('levels')}, not {LEVELS}")
    first = next((k for k in case.get("known") or [] if k.get("hour") == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))
    ratio, spread = fit_model(case.get("comparables"))
    hours = []
    for row in case.get("forecast") or []:
        hour = row["hour"]
        if ratio is not None and hour in ratio:
            quantiles = hour_quantiles(p1, hour, ratio, spread)
        else:
            quantiles = baseline_quantiles(p1, hour)
        hours.append({"hour": hour, "q": quantiles})
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
