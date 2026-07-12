#!/usr/bin/env python3
"""
Born Lottery API + static host.

  python server/app.py
  → http://127.0.0.1:8765

Public files:   ../public/
Private media:  ../assests/icons|flags  (not listed in public/)
Data:           ../data/
"""
from __future__ import annotations

import json
import mimetypes
import os
import random
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
DATA = ROOT / "data"
MEDIA = ROOT / "assests"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8765"))

# Production (AWS): set these so icons/flags come from private S3 signed URLs
S3_BUCKET = os.environ.get("S3_BUCKET", "").strip()
S3_REGION = os.environ.get("S3_REGION", "ap-southeast-2").strip()
# Your Netlify site origin, e.g. https://born-lottery.netlify.app (for pole SVGs)
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "").rstrip("/")

_s3 = None
if S3_BUCKET:
    try:
        import boto3

        _s3 = boto3.client("s3", region_name=S3_REGION)
        print(f"[server] S3 media: s3://{S3_BUCKET} ({S3_REGION})")
    except Exception as e:
        print(f"[server] S3 requested but boto3 failed: {e}")
        S3_BUCKET = ""


def signed_media_url(key: str, expires: int = 600) -> str:
    """Temporary https link to a private S3 object."""
    return _s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )


def icon_url_for(filename: str | None) -> str | None:
    if not filename:
        return None
    if S3_BUCKET and _s3:
        return signed_media_url(f"icons/{filename}")
    return f"/api/media/icons/{filename}"


def flag_url_for(filename: str | None) -> str | None:
    if not filename:
        return None
    if S3_BUCKET and _s3:
        return signed_media_url(f"flags/{filename}")
    return f"/api/media/flags/{filename}"


def pole_url_for(pole_key: str) -> str | None:
    if pole_key == "special":
        return None
    path = f"/assets/poles/flagpole_{pole_key}.svg"
    if FRONTEND_ORIGIN:
        return FRONTEND_ORIGIN + path
    return path


def load_json(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


WORLD = load_json("world.json")
NAMES = load_json("names.json")
MANIFESTS = load_json("manifests.json")
EVENTS = load_json("events.json")
META = load_json("meta.json")
TOP10 = load_json("top10.json")["countries"]

ICONS = MANIFESTS["icons"]
LOOKUP = MANIFESTS["lookup"]
FLAGS = MANIFESTS["flags"]
POLES = MANIFESTS["poles"]
SEXR = META.get("sexr") or {}
SEXR_DEFAULT = META.get("sexr_default", 1.05)
ETH = META.get("eth") or {}
CITIES = META.get("cities") or {}
CAPS = META.get("caps") or {}
Y0, Y1 = WORLD["Y0"], WORLD["Y1"]


def iso2_of(iso3: str) -> str:
    return NAMES[iso3][1].lower()


def dist_for(year: int, countries=None):
    i = year - Y0
    items, acc = [], 0
    keys = countries if countries is not None else [k for k in WORLD["births"] if k in NAMES]
    for k in keys:
        if k not in WORLD["births"]:
            continue
        acc += WORLD["births"][k][i]
        items.append([k, acc])
    return items, acc


def pick_weighted(items, tot):
    r = random.random() * tot
    lo, hi = 0, len(items) - 1
    while lo < hi:
        m = (lo + hi) // 2
        if items[m][1] < r:
            lo = m + 1
        else:
            hi = m
    return items[lo][0]


def sex_ratio(iso3: str, year: int) -> float:
    a = SEXR.get(iso3)
    if not a:
        return SEXR_DEFAULT
    # keys may be str years after JSON
    ys = sorted(int(k) for k in a.keys())
    if year <= ys[0]:
        return float(a[str(ys[0])] if str(ys[0]) in a else a[ys[0]])
    if year >= ys[-1]:
        k = str(ys[-1])
        return float(a[k] if k in a else a[ys[-1]])
    for i in range(len(ys) - 1):
        if ys[i] <= year <= ys[i + 1]:
            t = (year - ys[i]) / (ys[i + 1] - ys[i])
            v0 = float(a[str(ys[i])] if str(ys[i]) in a else a[ys[i]])
            v1 = float(a[str(ys[i + 1])] if str(ys[i + 1]) in a else a[ys[i + 1]])
            return v0 + t * (v1 - v0)
    return SEXR_DEFAULT


def wpick(pairs):
    tot = sum(p[1] for p in pairs)
    r = random.random() * tot
    for p in pairs:
        r -= p[1]
        if r <= 0:
            return p
    return pairs[-1]


def pick_avatar(iso3: str, male: bool):
    i2 = iso2_of(iso3)
    entry = ICONS.get(i2)
    if not entry:
        i2 = LOOKUP.get(i2, i2)
        entry = ICONS.get(i2) or {"m": [], "f": []}
    arr = entry.get("m" if male else "f") or []
    if not arr:
        arr = entry.get("f" if male else "m") or []
    if not arr:
        return None, None
    fn = random.choice(arr)
    return fn, icon_url_for(fn)


def pick_event(iso3: str, year: int):
    life = 85
    pool = [
        e
        for e in (EVENTS["countries"].get(iso3) or [])
        if e[0] >= year and e[0] - year <= life
    ]
    if not pool:
        pool = [e for e in EVENTS["global"] if e[0] >= year and e[0] - year <= life]
    if not pool:
        return None
    def age(e):
        return e[0] - year
    t1 = [e for e in pool if 20 <= age(e) <= 40]
    t2 = [e for e in pool if age(e) > 10]
    chosen = t1 or t2 or pool
    return random.choice(chosen)


def pct(x: float) -> str:
    if x >= 0.1:
        return f"{x:.1f}%"
    if x >= 0.01:
        return f"{x:.2f}%"
    return f"{x:.3f}%"


def build_spin(year: int):
    if not (Y0 <= year <= Y1):
        raise ValueError(f"year must be {Y0}–{Y1}")
    items, tot = dist_for(year)
    iso3 = pick_weighted(items, tot)
    i = year - Y0
    country_p = WORLD["births"][iso3][i] / tot

    sr = sex_ratio(iso3, year)
    male_p = sr / (sr + 100)
    male = random.random() < male_p
    sex_p = male_p if male else 1 - male_p

    eth_list = ETH.get(iso3) or [["other", 1]]
    eth_name, eth_w = wpick([[e[0], e[1]] for e in eth_list])
    eth_tot = sum(e[1] for e in eth_list)
    eth_p = eth_w / eth_tot

    city_list = CITIES.get(iso3)
    if city_list:
        city_name, city_w = wpick([[c[0], c[1]] for c in city_list])
        city_line = f"in {city_name}" if city_name != "rural" else "in a smaller town"
    else:
        city_line = f"near {CAPS[iso3]}" if iso3 in CAPS else "somewhere nearby"
        city_w, city_tot = 1, 1
    if city_list:
        city_tot = sum(c[1] for c in city_list)

    icon_file, icon_url = pick_avatar(iso3, male)
    i2 = iso2_of(iso3)
    flag_file = FLAGS.get(i2)
    pole_key = POLES.get(i2, "3x2")
    ev = pick_event(iso3, year)

    return {
        "mode": "full",
        "year": year,
        "iso3": iso3,
        "name": NAMES[iso3][0],
        "iso2": i2,
        "male": male,
        "sex_label": "Male" if male else "Female",
        "ethnicity": eth_name,
        "city_line": city_line,
        "probs": {
            "country": pct(country_p * 100),
            "sex": pct(sex_p * 100),
            "ethnicity": pct(eth_p * 100),
            "combo": pct(country_p * sex_p * eth_p * 100),
        },
        "event": {"year": ev[0], "text": ev[1], "age": ev[0] - year} if ev else None,
        "assets": {
            "icon": icon_url,
            "flag": flag_url_for(flag_file),
            "pole": pole_url_for(pole_key),
            "pole_key": pole_key,
        },
        "source": "UN estimate" if year >= 1950 else "Gapminder estimate",
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def log_message(self, fmt, *args):
        print(f"[server] {self.address_string()} {fmt % args}")

    def _send_json(self, obj, status=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def _send_file(self, path: Path, cache="public, max-age=86400"):
        if not path.is_file():
            self.send_error(404, "Not found")
            return
        data = path.read_bytes()
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        qs = parse_qs(parsed.query)

        if path == "/api/health":
            return self._send_json(
                {"ok": True, "mode": "full", "Y0": Y0, "Y1": Y1, "top10": TOP10}
            )

        if path == "/api/bootstrap":
            # Map stats are public; icon manifests are NOT included.
            return self._send_json(
                {
                    "Y0": Y0,
                    "Y1": Y1,
                    "names": NAMES,
                    "micro": META.get("micro") or {},
                    "top10": TOP10,
                }
            )

        if path == "/api/spin":
            try:
                year = int(qs.get("year", [None])[0])
            except (TypeError, ValueError):
                return self._send_json({"error": "year required"}, 400)
            try:
                return self._send_json(build_spin(year))
            except ValueError as e:
                return self._send_json({"error": str(e)}, 400)

        if path.startswith("/api/media/icons/"):
            fn = path.split("/api/media/icons/", 1)[1]
            if not re.fullmatch(r"[A-Za-z0-9_\-.]+\.webp", fn):
                return self.send_error(400, "bad name")
            return self._send_file(MEDIA / "icons" / fn, cache="private, max-age=3600")

        if path.startswith("/api/media/flags/"):
            fn = path.split("/api/media/flags/", 1)[1]
            if ".." in fn or "/" in fn or "\\" in fn:
                return self.send_error(400, "bad name")
            return self._send_file(MEDIA / "flags" / fn, cache="private, max-age=3600")

        # default: static from public/
        if path == "/":
            self.path = "/index.html"
        return SimpleHTTPRequestHandler.do_GET(self)


def main():
    print(f"Born Lottery → http://{HOST}:{PORT}")
    print(f"  public: {PUBLIC}")
    print(f"  media:  {MEDIA} (private, via /api/media)")
    print(f"  data:   {DATA}")
    try:
        httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        if getattr(e, "errno", None) in (48, 98):  # macOS / Linux address in use
            print(f"\nPort {PORT} is already in use.")
            print(f"  Kill it:  lsof -ti :{PORT} | xargs kill")
            print(f"  Or open:  http://{HOST}:{PORT}")
            raise SystemExit(1) from e
        raise
    httpd.allow_reuse_address = True
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
