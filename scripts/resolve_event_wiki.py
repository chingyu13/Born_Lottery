#!/usr/bin/env python3
"""
Resolve Wikipedia pages for Born Lottery events.

Writes:  data/event_wiki.csv
Updates: data/events.json  (3rd field = wiki title when found; omitted when none)

Usage:
  python3 scripts/resolve_event_wiki.py
  python3 scripts/resolve_event_wiki.py --limit 20   # dry sample
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS_JSON = ROOT / "data" / "events.json"
NAMES_JSON = ROOT / "data" / "names.json"
OUT_CSV = ROOT / "data" / "event_wiki.csv"
UA = "BornLotteryBot/1.0 (https://bornlottery.chingyu.site/; event wiki resolver)"

API = "https://en.wikipedia.org/w/api.php"


def api_get(params: dict) -> dict:
    q = urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def clean_text(text: str) -> str:
    return re.sub(r"^the\s+", "", text or "", flags=re.I).strip()


def search_titles(query: str, limit: int = 5) -> list[str]:
    if not query:
        return []
    # Full-text search ranks acronyms (e.g. NAFTA) much better than opensearch
    data = api_get(
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "srnamespace": 0,
        }
    )
    hits = data.get("query", {}).get("search") or []
    titles = [h["title"] for h in hits if h.get("title")]
    if titles:
        return titles
    data = api_get(
        {
            "action": "opensearch",
            "search": query,
            "limit": limit,
            "namespace": 0,
            "redirects": "resolve",
        }
    )
    return list(data[1]) if isinstance(data, list) and len(data) > 1 else []


def page_exists(title: str) -> tuple[bool, str | None, str | None]:
    """Return (ok, canonical_title, full_url)."""
    data = api_get(
        {
            "action": "query",
            "titles": title,
            "redirects": 1,
            "prop": "info",
            "inprop": "url",
        }
    )
    pages = data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        if int(pid) < 0 or page.get("missing") is not None:
            return False, None, None
        title_out = page.get("title") or ""
        if "disambiguation" in title_out.lower():
            return False, None, None
        return True, title_out, page.get("fullurl")
    return False, None, None


def score_candidate(title: str, query: str, country: str | None) -> float:
    t = title.lower()
    q = query.lower().strip()
    if not q:
        return 0.0
    # Acronym / short all-caps token: require whole-word (or parenthetical) match
    if query.isupper() and 2 <= len(query) <= 8:
        if re.search(rf"(?<![a-z]){re.escape(q)}(?![a-z])", t):
            return 1.2
        # Title is the expansion people mean (e.g. North American Free Trade Agreement)
        # Keep weak score only if all letters of acronym appear in order in title words
        words = re.findall(r"[a-z]+", t)
        initials = "".join(w[0] for w in words if w not in {"of", "the", "and", "for", "in", "on", "a", "an"})
        if q == initials[: len(q)] or q in initials:
            return 0.9
        return -1.0

    tokens = [w for w in re.split(r"\W+", q) if len(w) > 2]
    if not tokens:
        return 0.0
    hit = sum(1 for w in tokens if re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", t))
    score = hit / len(tokens)
    if "disambiguation" in t:
        score -= 0.5
    if country and country.lower() in t:
        score += 0.15
    if t == q or t.replace(",", "") == q:
        score += 0.4
    return score


VAGUE = {
    "independence",
    "protests",
    "the protests",
    "civil war",
    "the civil war",
    "coup",
    "the coup",
    "military coup",
    "the military coup",
    "election",
    "the election",
    "revolution",
    "the revolution",
    "referendum",
    "the referendum",
    "constitution",
    "the constitution",
    "peace",
    "the peace",
    "uprising",
    "the uprising",
}

NEEDS_COUNTRY_RE = re.compile(
    r"\b(civil war|invasion|occupation|collapse|coup|independence|protests?|"
    r"uprising|election|revolution|referendum|transfer of power|fall of communism|"
    r"economic|founding|occupation|world cup|olympics?)\b",
    re.I,
)


def resolve_event(text: str, country: str | None) -> tuple[str | None, str | None]:
    """Return (wiki_title, wiki_url) or (None, None)."""
    q = clean_text(text)
    if not q:
        return None, None
    is_acronym = q.isupper() and 2 <= len(q) <= 8
    vague = q.lower() in VAGUE or (len(q.split()) <= 1 and not is_acronym)
    needs_country = bool(country) and (vague or bool(NEEDS_COUNTRY_RE.search(q)))

    def accept(canon: str | None, url: str | None) -> tuple[str, str] | None:
        if not canon or not url:
            return None
        if "disambiguation" in canon.lower():
            return None
        if needs_country:
            cl = country.lower()
            tl = canon.lower()
            stem = cl[:5] if len(cl) >= 5 else cl
            # Match "Mexico" to "Mexican …", "Spain" to "Spanish …", etc.
            if cl not in tl and stem not in tl and not any(
                p in tl for p in cl.split() if len(p) > 3
            ):
                return None
        return canon, url

    # Acronyms: prefer the canonical redirect target (NAFTA → North American Free Trade Agreement)
    if q.isupper() and 2 <= len(q) <= 8:
        try:
            ok, canon, url = page_exists(q)
            time.sleep(0.04)
            if ok:
                hit = accept(canon, url)
                if hit:
                    return hit
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            pass

    # 1) Direct title / redirect hits
    direct_tries = []
    if not vague:
        direct_tries.append(q)
    if country:
        direct_tries += [f"{country} {q}", f"{q} ({country})"]
        if q.lower() == "independence":
            direct_tries = [f"Independence of {country}", f"{country} independence"] + direct_tries
    for title in direct_tries:
        try:
            ok, canon, url = page_exists(title)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            continue
        time.sleep(0.04)
        if ok:
            hit = accept(canon, url)
            if hit:
                return hit

    # 2) Search
    queries = []
    if country:
        queries.append(f"{country} {q}")
    if not vague:
        queries.append(q)
    if q.isupper() and 2 <= len(q) <= 8:
        queries += [f'"{q}"', f"{q} agreement", f"{q} treaty"]

    seen: set[str] = set()
    candidates: list[tuple[float, str]] = []
    for query in queries:
        try:
            titles = search_titles(query, limit=5)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(0.4)
            continue
        for title in titles:
            if title in seen:
                continue
            seen.add(title)
            candidates.append((score_candidate(title, q, country), title))
        time.sleep(0.05)

    candidates.sort(key=lambda x: -x[0])
    for score, title in candidates[:8]:
        if score < 0.45:
            continue
        try:
            ok, canon, url = page_exists(title)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            continue
        time.sleep(0.05)
        if ok:
            hit = accept(canon, url)
            if hit:
                return hit
    return None, None


def iter_events(events: dict):
    for e in events.get("global") or []:
        yield "GLOBAL", e[0], e[1], e[2] if len(e) > 2 else None
    for iso3, arr in (events.get("countries") or {}).items():
        for e in arr:
            yield iso3, e[0], e[1], e[2] if len(e) > 2 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Only first N events (0=all)")
    ap.add_argument("--resume", action="store_true", help="Reuse existing CSV hits")
    ap.add_argument(
        "--only-missing",
        action="store_true",
        help="With --resume, only re-resolve rows that have no wiki_url",
    )
    args = ap.parse_args()

    events = json.loads(EVENTS_JSON.read_text(encoding="utf-8"))
    names = json.loads(NAMES_JSON.read_text(encoding="utf-8"))

    prior: dict[tuple[str, int, str], dict] = {}
    if (args.resume or args.only_missing) and OUT_CSV.exists():
        with OUT_CSV.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = (row["iso3"], int(row["year"]), row["event_text"])
                prior[key] = row

    rows = []
    items = list(iter_events(events))
    if args.limit:
        items = items[: args.limit]

    found = 0
    for i, (iso3, year, text, existing) in enumerate(items, 1):
        country = None if iso3 == "GLOBAL" else (names.get(iso3) or [iso3])[0]
        key = (iso3, int(year), text)
        wiki_title = wiki_url = None
        status = "missing"

        if existing and isinstance(existing, str) and existing.startswith("http"):
            wiki_url = existing
            wiki_title = existing.rsplit("/", 1)[-1].replace("_", " ")
            status = "curated_url"
        elif existing and isinstance(existing, str):
            ok, canon, url = page_exists(existing)
            if ok:
                wiki_title, wiki_url, status = canon, url, "curated_title"
            else:
                status = "curated_invalid"

        cached = prior.get(key)
        if status in ("missing", "curated_invalid"):
            if cached and cached.get("wiki_url"):
                wiki_title = cached.get("wiki_title") or None
                wiki_url = cached.get("wiki_url") or None
                status = cached.get("status") or "cached"
            else:
                wiki_title, wiki_url = resolve_event(text, country)
                status = "resolved" if wiki_url else "none"

        if wiki_url:
            found += 1
        rows.append(
            {
                "iso3": iso3,
                "year": year,
                "event_text": text,
                "country": country or "",
                "wiki_title": wiki_title or "",
                "wiki_url": wiki_url or "",
                "status": status,
            }
        )
        print(f"[{i}/{len(items)}] {iso3} {year} {text[:40]!r} → {wiki_title or '(none)'}")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["iso3", "year", "event_text", "country", "wiki_title", "wiki_url", "status"],
        )
        w.writeheader()
        w.writerows(rows)

    # Bake into events.json: keep [year, text] or [year, text, wiki_title]
    by_key = {(r["iso3"], int(r["year"]), r["event_text"]): r for r in rows}

    def bake(iso_key: str, arr: list) -> list:
        out = []
        for e in arr:
            year, text = e[0], e[1]
            r = by_key.get((iso_key, int(year), text))
            if r and r["wiki_title"]:
                out.append([year, text, r["wiki_title"]])
            else:
                out.append([year, text])
        return out

    events["global"] = bake("GLOBAL", events.get("global") or [])
    events["countries"] = {
        iso: bake(iso, arr) for iso, arr in (events.get("countries") or {}).items()
    }
    EVENTS_JSON.write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\nWrote {OUT_CSV} ({found}/{len(rows)} with wiki)")
    print(f"Updated {EVENTS_JSON}")


if __name__ == "__main__":
    main()
