# GTA 6 Twitch CCU Forecast

[![make.fun](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/sururarip/gta6-twitch-ccu-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/sururarip/gta6-twitch-ccu-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)

Forecasts the Twitch viewers in the **Grand Theft Auto VI** category, hour by
hour, for hours 2–24 of release day (19 November 2026, UTC), from the hour-1
print. Entry for the
[make.fun bounty](https://make.fun/bounty/gta6-twitch-ccu-forecast-01).

## How it works

`main.py` (Python 3.13, standard library only) fits a fresh model at run time
from the case file's own comparables — past big game launches' hourly Twitch
curves — so the same program works for a practice case and for the final:

1. **Rolling-unlock filter.** Keep only launches that look like a rolling
   midnight unlock: a full 24 hours, a positive hour-1 print, and a day
   peak no more than 15× hour 1. This drops simultaneous global unlocks
   (near-zero hour 1, then a 100–2000× explosion), which follow a
   different shape.
2. **Closest analogues weigh more.** The four big console-exclusive
   practice launches — Marvel's Wolverine, Red Dead Redemption 2, God of
   War Ragnarök, Marvel's Spider-Man 2 — get weight 3; every other launch
   weighs 1. They are the closest analogues to GTA VI: console-only,
   rolling midnight unlock, huge single-player hype.
3. **Ratio curve.** For each hour, the centre forecast is the weighted
   geometric mean of the launches' ratios `curve[h] / curve[1]`, anchored
   on this case's hour-1 print. Across past launches the curve dips after
   hour 1 (UTC night), jumps at hour 5 (US Eastern midnight unlock), sags
   midday, then climbs to a US-evening peak around hours 18–22.
4. **Widening spread.** Each hour's spread is the weighted log-standard-
   deviation of those ratios, floored by the random-walk spread
   `0.15 * sqrt(h - 1)` and capped at 0.8. Quantiles:
   `q = p1 * ratio(h) * exp(z * spread(h))`.

On the four practice launches this scores a mean pinball loss of **0.277**
against the house baseline's **0.387** (a 28% improvement), measured on the
launches' real release-day curves.

## Run it

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `<id>.in` in the input directory and writes `<id>.out` to the
output directory: `{"hours": [{"hour": 2, "q": [q05, q25, q50, q75, q95]}, ...]}`
for hours 2–24. Deterministic, no network, well under the 8-second limit.

## License

MIT — see [LICENSE](LICENSE).
