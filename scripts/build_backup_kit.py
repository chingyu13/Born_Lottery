#!/usr/bin/env python3
"""Build public offline backup kit: top-10 countries, ~20 icons, 10 flags, events."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MEDIA = ROOT / "assests"  # full library (private media root)
PUBLIC = ROOT / "public"
BACKUP = PUBLIC / "assets" / "backup"


def pick_two_icons(entry: dict) -> list[str]:
    """Prefer 1 male + 1 female; otherwise up to 2 available."""
    m = list(entry.get("m") or [])
    f = list(entry.get("f") or [])
    out = []
    if m:
        out.append(m[0])
    if f:
        out.append(f[0])
    if len(out) < 2 and len(m) > 1:
        out.append(m[1])
    if len(out) < 2 and len(f) > 1:
        out.append(f[1])
    return out[:2]


def main():
    world = json.loads((DATA / "world.json").read_text(encoding="utf-8"))
    names = json.loads((DATA / "names.json").read_text(encoding="utf-8"))
    manifests = json.loads((DATA / "manifests.json").read_text(encoding="utf-8"))
    events = json.loads((DATA / "events.json").read_text(encoding="utf-8"))
    top10 = json.loads((DATA / "top10.json").read_text(encoding="utf-8"))["countries"]
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))

    icons_m = manifests["icons"]
    flags_m = manifests["flags"]
    poles_m = manifests["poles"]
    lookup = manifests["lookup"]

    BACKUP.mkdir(parents=True, exist_ok=True)
    (BACKUP / "icons").mkdir(exist_ok=True)
    (BACKUP / "flags").mkdir(exist_ok=True)
    poles_dst = PUBLIC / "assets" / "poles"
    poles_dst.mkdir(parents=True, exist_ok=True)
    fonts_dst = PUBLIC / "assets" / "fonts"
    fonts_dst.mkdir(parents=True, exist_ok=True)

    # shared poles + fonts + mascot
    for p in (MEDIA / "tool" / "flagpoles").glob("flagpole_*.svg"):
        shutil.copy2(p, poles_dst / p.name)
    for p in (MEDIA / "fonts").glob("*"):
        if p.is_file():
            shutil.copy2(p, fonts_dst / p.name)
    if (MEDIA / "earth_ppl.gif").exists():
        shutil.copy2(MEDIA / "earth_ppl.gif", PUBLIC / "assets" / "earth_ppl.gif")

    countries = {}
    copied_icons = []
    copied_flags = []

    for iso3 in top10:
        name, iso2u = names[iso3]
        iso2 = iso2u.lower()
        icon_key = iso2 if iso2 in icons_m else lookup.get(iso2, iso2)
        entry = icons_m.get(icon_key) or {"m": [], "f": []}
        files = pick_two_icons(entry)
        # split back into m/f for backup manifest
        m_files, f_files = [], []
        for fn in files:
            src = MEDIA / "icons" / fn
            if not src.exists():
                print("missing icon", src)
                continue
            shutil.copy2(src, BACKUP / "icons" / fn)
            copied_icons.append(fn)
            if "_male_" in fn or fn.startswith(f"{icon_key}_male"):
                m_files.append(fn)
            else:
                f_files.append(fn)

        flag_file = flags_m.get(iso2)
        if flag_file:
            src = MEDIA / "flags" / flag_file
            if src.exists():
                shutil.copy2(src, BACKUP / "flags" / flag_file)
                copied_flags.append(flag_file)
            else:
                print("missing flag", src)
                flag_file = None

        # births series for this country only (for weighted backup spin)
        births = world["births"][iso3]
        ev = events["countries"].get(iso3, [])[:4]
        if len(ev) < 2:
            # pad from global with country-flavored? keep as-is; global fallback in client
            pass

        countries[iso3] = {
            "name": name,
            "iso2": iso2,
            "births": births,
            "icons": {"m": m_files, "f": f_files},
            "flag": flag_file,
            "pole": poles_m.get(iso2, "3x2"),
            "events": ev,
        }

    backup = {
        "mode": "backup",
        "Y0": world["Y0"],
        "Y1": world["Y1"],
        "countries": countries,
        "global_events": events["global"],
        "sexr_default": meta.get("sexr_default", 1.05),
        "note": "Shipped offline kit. Used when /api/health fails.",
    }

    # public copies of world (stats/map OK to ship) + names for explore map
    shutil.copy2(DATA / "world.json", PUBLIC / "data" / "world.json")
    shutil.copy2(DATA / "names.json", PUBLIC / "data" / "names.json")
    # slim meta for map microdots / sex ratios used in backup reveal
    slim_meta = {
        "micro": meta.get("micro", {}),
        "sexr_default": meta.get("sexr_default", 105),
    }
    (PUBLIC / "data" / "meta-backup.json").write_text(
        json.dumps(slim_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (PUBLIC / "data" / "backup.json").write_text(
        json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # also JS module-less global for file:// friendliness optional
    (PUBLIC / "js" / "backup-data.js").write_text(
        "window.BACKUP_DATA = " + json.dumps(backup, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )

    # record kit inventory in data/
    (DATA / "backup_inventory.json").write_text(
        json.dumps(
            {
                "countries": top10,
                "icons": copied_icons,
                "flags": copied_flags,
                "icon_count": len(copied_icons),
                "flag_count": len(copied_flags),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"backup kit: {len(top10)} countries, {len(copied_icons)} icons, {len(copied_flags)} flags")
    for iso3 in top10:
        c = countries[iso3]
        print(
            f"  {iso3} icons={len(c['icons']['m'])+len(c['icons']['f'])} "
            f"events={len(c['events'])} flag={bool(c['flag'])}"
        )


if __name__ == "__main__":
    main()
