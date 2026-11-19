"""Korean place descriptions (tasks/prd-random-jeju-merge.md US-041).

Writes data/seed/places_ko.csv: id, status, src, description_ko.
- status "reviewed": a hand-checked translation from frontend/lib/content/descriptions.ko.ts, used only when its
  hash still matches the place's current description_en (the same FNV-1a hash as frontend/lib/text-hash.ts).
- status "machine": translated once by the LLM in backend/.env (Gemini or Claude), checked for Hangul and length.
- src: the hash of the English text it was made from. When description_en changes, the row is redone.
Resumable: rows already in the CSV with a matching src are kept, so a stopped run continues where it was.

    backend/.venv/Scripts/python.exe backend/scripts/translate_places.py --limit 20   # try a few first
    backend/.venv/Scripts/python.exe backend/scripts/translate_places.py              # all the rest
Then: build_places.py (puts description_ko into app/data/places.json) and seed_supabase.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app import config  # noqa: E402

OUT = ROOT / "data" / "seed" / "places_ko.csv"
REVIEWED_TS = ROOT / "frontend" / "lib" / "content" / "descriptions.ko.ts"
HANGUL = re.compile("[가-힣]")
BATCH = 20
PROMPT = """Translate each Jeju place description from English into natural, polite Korean (해요체 or 합니다체,
the way a Korean travel guide would write it). Rules:
- Keep every fact; add nothing, drop nothing, no comments.
- When the description names the place itself, use its Korean name from "name_ko".
- Other proper nouns: use the usual Korean name when there is one.
- Numbers, hours and prices stay as they are.
Return JSON only: {"items":[{"id":<id>,"ko":"<Korean text>"}]} with one item per input, same ids."""


def text_hash(s: str) -> str:
    """FNV-1a, 32-bit, over UTF-16 code units, base 36 (frontend/lib/text-hash.ts)."""
    h = 0x811C9DC5
    data = s.encode("utf-16-le")
    for i in range(0, len(data), 2):
        h ^= data[i] | (data[i + 1] << 8)
        h = (h * 0x01000193) & 0xFFFFFFFF
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while True:
        h, r = divmod(h, 36)
        out = digits[r] + out
        if h == 0:
            return out


def reviewed_translations() -> dict[int, tuple[str, str]]:
    """{id: (src hash, text)} from the frontend's reviewed table."""
    src = REVIEWED_TS.read_text(encoding="utf-8")
    pat = re.compile(r'^\s*(\d+):\s*\{\s*src:\s*"([0-9a-z]+)",\s*text:\s*"((?:[^"\\]|\\.)*)"\s*\}', re.M)
    return {int(m.group(1)): (m.group(2), json.loads('"' + m.group(3) + '"')) for m in pat.finditer(src)}


def looks_korean(en: str, ko: str) -> bool:
    if not ko or len(ko) > 3 * len(en) + 40:
        return False
    letters = [c for c in ko if c.isalpha()]
    return bool(letters) and sum(bool(HANGUL.match(c)) for c in letters) / len(letters) >= 0.5 and len(ko) >= 0.15 * len(en)


def call_llm(batch: list[dict]) -> dict[int, str]:
    payload = json.dumps([{"id": p["id"], "name_ko": p["name_ko"], "name_en": p["name_en"],
                           "description_en": p["description_en"]} for p in batch], ensure_ascii=False)
    if config.LLM_PROVIDER == "claude":
        import anthropic
        client = anthropic.Anthropic(api_key=config.LLM_API_KEY)
        msg = client.messages.create(model=config.LLM_MODEL, max_tokens=8000, system=PROMPT,
                                     messages=[{"role": "user", "content": payload}])
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        text = text[text.index("{"): text.rindex("}") + 1]
    else:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=config.LLM_API_KEY)
        schema = {"type": "object", "properties": {"items": {"type": "array", "items": {
            "type": "object", "properties": {"id": {"type": "integer"}, "ko": {"type": "string"}},
            "required": ["id", "ko"]}}}, "required": ["items"]}
        r = client.models.generate_content(
            model=config.LLM_MODEL, contents=payload,
            config=types.GenerateContentConfig(system_instruction=PROMPT, temperature=0.2,
                                               response_mime_type="application/json", response_json_schema=schema))
        text = r.text
    return {int(i["id"]): str(i["ko"]).strip() for i in json.loads(text)["items"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="translate at most N places this run")
    ap.add_argument("--pause", type=float, default=4.0, help="seconds between LLM calls (rate limit)")
    args = ap.parse_args()
    if not config.USE_LLM:
        print("LLM_API_KEY is empty in backend/.env")
        return 1

    places = json.loads((config.SEED_DATA_DIR / "places.json").read_text(encoding="utf-8"))
    rows: dict[int, dict] = {}
    if OUT.exists():
        with OUT.open(encoding="utf-8", newline="") as f:
            rows = {int(r["id"]): r for r in csv.DictReader(f)}
    reviewed = reviewed_translations()

    todo = []
    for p in places:
        en = (p.get("description_en") or "").strip()
        h = text_hash(en)
        rev = reviewed.get(p["id"])
        if rev and rev[0] == h:
            rows[p["id"]] = {"id": p["id"], "status": "reviewed", "src": h, "description_ko": rev[1]}
        elif en and not (p["id"] in rows and rows[p["id"]]["src"] == h):
            rows.pop(p["id"], None)
            todo.append({**p, "description_en": en})
    if args.limit is not None:
        todo = todo[: args.limit]
    print(f"places {len(places)}  reviewed {sum(r['status'] == 'reviewed' for r in rows.values())}  "
          f"already machine {sum(r['status'] == 'machine' for r in rows.values())}  to translate {len(todo)}")

    def save() -> None:
        with OUT.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id", "status", "src", "description_ko"])
            w.writeheader()
            for pid in sorted(rows):
                w.writerow(rows[pid])

    bad: list[int] = []
    for n in range(0, len(todo), BATCH):
        batch = todo[n: n + BATCH]
        for attempt in (1, 2):
            try:
                got = call_llm(batch)
                break
            except Exception as e:                        # rate limit, bad JSON: wait and try once more
                print(f"  batch {n // BATCH + 1}: {type(e).__name__}: {str(e)[:120]}")
                got = {}
                time.sleep(args.pause * 5)
        for p in batch:
            ko = got.get(p["id"], "")
            if looks_korean(p["description_en"], ko):
                rows[p["id"]] = {"id": p["id"], "status": "machine", "src": text_hash(p["description_en"]),
                                 "description_ko": ko}
            else:
                bad.append(p["id"])
        save()
        print(f"  {min(n + BATCH, len(todo))}/{len(todo)} done, {len(bad)} rejected")
        time.sleep(args.pause)
    save()
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rows; rejected ids (left in English): {bad[:30]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
