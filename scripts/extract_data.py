#!/usr/bin/env python3
"""Extract embedded datasets from born_lottery.html / events.js into data/."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "born_lottery.html"
EVENTS_JS = ROOT / "events.js"
OUT = ROOT / "data"


def _slice_balanced(text: str, start: int, open_ch: str, close_ch: str) -> str:
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise SystemExit("unbalanced structure")


def js_obj_to_py(raw: str):
    """Parse a JS object/array literal that is JSON-like (possibly bare keys)."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    fixed = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', raw)
    fixed = re.sub(r"([{,]\s*)(\d+)\s*:", r'\1"\2":', fixed)
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
    return json.loads(fixed)


def extract_const_json(text: str, name: str):
    m = re.search(rf"const {name}\s*=\s*(\{{)", text)
    if not m:
        raise SystemExit(f"const {name} not found")
    return js_obj_to_py(_slice_balanced(text, m.start(1), "{", "}"))


def extract_const_array(text: str, name: str):
    m = re.search(rf"const {name}\s*=\s*(\[)", text)
    if not m:
        raise SystemExit(f"const {name} not found")
    return js_obj_to_py(_slice_balanced(text, m.start(1), "[", "]"))


def extract_events(js: str):
    global_events = extract_const_array(js, "GLOBAL_EVENTS")
    m = re.search(r"const EVENTS\s*=\s*(\{)", js)
    if not m:
        raise SystemExit("EVENTS not found")
    return global_events, js_obj_to_py(_slice_balanced(js, m.start(1), "{", "}"))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    html = HTML.read_text(encoding="utf-8")

    world = extract_const_json(html, "WORLD_DATA")
    names = extract_const_json(html, "NAMES")
    icons = extract_const_json(html, "ICONS")
    lookup = extract_const_json(html, "LOOKUP")
    flags = extract_const_json(html, "FLAGS")
    poles = extract_const_json(html, "POLES")

    extras = {}
    for name in ("MICRO", "SEXR", "ETH", "CITIES", "CAPS"):
        try:
            extras[name.lower()] = extract_const_json(html, name)
        except Exception as e:
            print(f"skip {name}: {e}")
    m = re.search(r"const SEXR_DEFAULT\s*=\s*([0-9.]+)", html)
    if m:
        extras["sexr_default"] = float(m.group(1))

    events_js = EVENTS_JS.read_text(encoding="utf-8")
    global_events, events = extract_events(events_js)

    (OUT / "world.json").write_text(
        json.dumps(world, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (OUT / "names.json").write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "manifests.json").write_text(
        json.dumps(
            {"icons": icons, "lookup": lookup, "flags": flags, "poles": poles},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT / "meta.json").write_text(json.dumps(extras, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "events.json").write_text(
        json.dumps({"global": global_events, "countries": events}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    y = 2020
    i = y - world["Y0"]
    ranked = sorted(world["births"].items(), key=lambda kv: kv[1][i], reverse=True)
    top10 = [iso for iso, _ in ranked[:10]]
    (OUT / "top10.json").write_text(
        json.dumps(
            {
                "year_basis": y,
                "countries": top10,
                "note": "Offline backup kit countries. Art masters stay out of public/.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"wrote data/ ({', '.join(sorted(p.name for p in OUT.glob('*.json')))})")
    print("top10:", ", ".join(top10))


if __name__ == "__main__":
    main()
