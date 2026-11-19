"""Random-course eval (tasks/prd-random-jeju-merge.md US-015, the snap_km and quality rows of 9장).

Draws N points from the usable grid cells (app/data/grids.json, written by scripts/mark_grids.py) and builds a
random course from each with planner.random_course, cycling through the 20 profiles and 5 time windows of
scripts/eval_planner.py. Prints the planner-rule violations, how far the course moved from the point
(snap_km), how varied the hubs are, and eval_planner's meal and route metrics.

    backend/.venv/Scripts/python.exe backend/scripts/eval_random.py              # 300 points -> eval/random-rules.json
    backend/.venv/Scripts/python.exe backend/scripts/eval_random.py --n 1000 --seed 2

Rule planner only (no LLM calls). Places from app/data/places.json; Supabase is never used. A point is drawn by
picking a usable cell uniformly and using its land point (the DB function draws a uniform point inside the
cell's land part; the difference is at most a few hundred metres).
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Optional

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from app import areas, config, planner, random_spots  # noqa: E402
from app.errors import ApiError  # noqa: E402
import eval_planner as ep  # noqa: E402


def profiles() -> list[dict]:
    """The 20 profiles of eval_planner FR-1."""
    return [{"interests": list(i), "condition_today": c, "diet": d, **ep.FIXED}
            for i in ep.INTERESTS for c in ep.CONDITIONS for d in ep.DIETS]


def pct(xs: list[float], q: float) -> Optional[float]:
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="points to draw (default 300)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--weekday", default="wed", choices=planner.WEEKDAYS)
    ap.add_argument("--out", default=str(BACKEND / "eval" / "random-rules.json"))
    args = ap.parse_args(argv)

    config.USE_LLM = False
    planner.today_kst_dow = lambda: args.weekday
    places = json.loads((config.SEED_DATA_DIR / "places.json").read_text(encoding="utf-8"))
    grids = json.loads((config.SEED_DATA_DIR / "grids.json").read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in places}
    selectable = random_spots.selectable_areas(areas.load_seed_areas(), places)
    rng = random.Random(args.seed)
    profs = profiles()

    runs: list[ep.Run] = []
    snaps, hubs, picked_areas, point_areas = [], Counter(), Counter(), Counter()
    move_over, hours_bad, window_bad, errors = 0, 0, 0, Counter()
    t0 = time.monotonic()
    for i in range(args.n):
        cell = rng.choice(grids)
        profile = profs[i % len(profs)]
        start, end = ep.WINDOWS[(i // len(profs)) % len(ep.WINDOWS)]
        point_areas[cell["area_id"]] += 1
        try:
            course, items, picked = planner.random_course(places, profile, start, end, cell, selectable,
                                                          seed=args.seed * 100000 + i)
        except ApiError as e:
            errors[e.detail["code"]] += 1
            runs.append(ep.Run(ep.Scenario(cell["area_id"], profile, start, end), error=e.detail["code"]))
            continue
        snaps.append(picked.km)
        hubs[picked.hub.place["id"]] += 1
        picked_areas[picked.area_id] += 1
        s0, s1 = planner.to_min(start), planner.to_min(end)
        for it in items:
            move_over += (it["move_min"] or 0) > config.MAX_MOVE_MIN
            b = planner.to_min(it["start_time"])
            hours_bad += not planner.fits_hours(by_id[it["place_id"]], b, it["stay_min"])
            window_bad += b < s0 or b + it["stay_min"] > s1
        runs.append(ep.Run(ep.Scenario(picked.area_id, profile, start, end), items=items,
                           meal_gaps=course["meal_gaps"]))

    used_areas = sorted(picked_areas)
    area_places = {a: planner.in_area(places, a) for a in used_areas}
    quality = ep.metrics(runs, by_id, area_places)
    ok = [r for r in runs if r.items is not None]
    top_hub_share = (hubs.most_common(1)[0][1] / len(ok)) if ok else None
    result = {
        "date": date.today().isoformat(),
        "commit": ep.git_commit(),
        "label": "random-rules",
        "planner": "rules",
        "weekday": args.weekday,
        "seed": args.seed,
        "points": args.n,
        "usable_cells": len(grids),
        "seconds": round(time.monotonic() - t0, 1),
        "summary": {
            "success_rate": round(len(ok) / len(runs), 4) if runs else None,
            "errors": dict(errors),
            "move_over_limit": move_over,
            "outside_opening_hours": hours_bad,
            "outside_trip_window": window_bad,
            "meal_miss_rate": quality["meal_miss_rate"],
            "snap_km_median": round(statistics.median(snaps), 2) if snaps else None,
            "snap_km_p90": round(pct(snaps, 0.9), 2) if snaps else None,
            "snap_km_max": round(max(snaps), 2) if snaps else None,
            "snap_over_2km_rate": round(sum(s > 2 for s in snaps) / len(snaps), 4) if snaps else None,
            "distinct_hubs": len(hubs),
            "top_hub_share": round(top_hub_share, 4) if top_hub_share is not None else None,
        },
        "point_areas": dict(sorted(point_areas.items())),
        "course_areas": dict(sorted(picked_areas.items())),
        "quality": quality,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    s = result["summary"]
    print(f"{args.n} points, {len(ok)} courses in {result['seconds']} s")
    for k, v in s.items():
        print(f"  {k:24} {v}")
    print(f"  {'lunch / dinner rate':24} {quality['lunch_rate']} / {quality['dinner_rate']}")
    print(f"  {'max_leg_min':24} {quality['max_leg_min']}")
    print(f"wrote {Path(args.out).relative_to(BACKEND)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
