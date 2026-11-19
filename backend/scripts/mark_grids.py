"""Mark the grid cells random points must not come from (tasks/prd-random-jeju-merge.md FR-0).

A cell is skipped when it is less than half land, when its land point is in an area that is not ready
(today Udo and Chuja), or when no dense place (a hub-sized cluster) is within GRID_REACH_KM.
Run after supabase/migrations/0003_random_point.sql, and again after seed_supabase.py changes places:
    backend/.venv/Scripts/python.exe backend/scripts/mark_grids.py            # write to Supabase
    backend/.venv/Scripts/python.exe backend/scripts/mark_grids.py --dry-run  # only print
Also writes app/data/grids.json (usable cells' land points), which scripts/eval_planner.py --random reads.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app import areas, config, random_spots  # noqa: E402
from app.store import get_store  # noqa: E402

PAGE = 1000
OUT = config.SEED_DATA_DIR / "grids.json"


def read_cells(sb) -> list[dict]:
    rows: list[dict] = []
    while True:
        page = (sb.table("grids").select("id, adm_nm, land_share, land_lat, land_lng")
                .order("id").range(len(rows), len(rows) + PAGE - 1).execute().data)
        rows.extend(page)
        if len(page) < PAGE:
            return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the counts, change nothing")
    args = ap.parse_args()

    store = get_store()
    places = store.list_places()
    selectable = random_spots.selectable_areas(store.list_areas(), places)
    dense = random_spots.dense_places(places, selectable)
    cells = read_cells(store._sb)  # noqa: SLF001 (one-off script)
    if not cells or cells[0].get("land_share") is None:
        print("ERROR: grids has no land_share: run supabase/migrations/0003_random_point.sql first")
        return 1

    reasons = {c["id"]: random_spots.skip_reason(c, dense, selectable) for c in cells}
    skip = sorted(i for i, r in reasons.items() if r)
    usable = [c for c in cells if not reasons[c["id"]]]
    print(f"selectable areas: {len(selectable)}  dense places: {len(dense)}")
    print(f"cells: {len(cells)}  usable: {len(usable)}  skipped: {len(skip)}  {dict(Counter(r for r in reasons.values() if r))}")
    by_adm = Counter((c["adm_nm"] or "").split()[-1] for c in usable)
    print("usable cells by eup/myeon/dong (fewest first):", sorted(by_adm.items(), key=lambda x: x[1])[:8])

    OUT.write_text(json.dumps(
        [{"id": c["id"], "lat": round(c["land_lat"], 6), "lng": round(c["land_lng"], 6),
          "area_id": areas.area_of_point(c["land_lat"], c["land_lng"])} for c in usable],
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(BACKEND)} ({len(usable)} cells)")

    if args.dry_run:
        print("dry run: Supabase not changed")
        return 0
    marked = store._sb.rpc("mark_grids", {"skip_ids": skip}).execute().data  # noqa: SLF001
    print(f"grids.blacklist set on {marked} cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
