# Born Lottery

**What are the odds you were born where you were?**

Pick a year, spin the globe, and get a weighted random birth country based on historical birth counts — plus gender, a portrait, flag, and a life-event you might live through.

**Live:** [https://bornlottery.chingyu.site/](https://bornlottery.chingyu.site/) (`public/` on Netlify) · AWS for the full-country API & private art.

---

## Features

- Interactive world map (choropleth by birth volume)
- Weighted country lottery (UN / Gapminder birth data, 1900–2026)
- Result card: odds, avatar, flag, historical event (prefers ages 20–40)
- **Full mode** — all countries when the API is up  
- **Backup mode** — top‑10 country kit when the API is down (offline / static host)
- Pan & zoom the map after spin or in “view chance” explore mode

## Quick start (local)

```bash
python3 scripts/build_all.py   # refresh data + backup kit
python3 server/app.py          # http://127.0.0.1:8765
```

| Mode | How |
|------|-----|
| Full | Open via `server/app.py` (API + static) |
| Backup only | Serve `public/` alone (e.g. Netlify) |

## Project layout

```
public/          Frontend (safe to deploy to Netlify / CDN)
  assets/backup/   Top‑10 portraits & flags (~offline kit)
  js/ data/ …

server/          Backend (API: /api/health, /api/spin, /api/media/…)
data/            Pipeline JSON (world, events, manifests)
assests/         Full art library — server-only, not for CDN
private/         Notes + optional home for masters (see private/README.md)
scripts/         extract_data.py · build_backup_kit.py · build_all.py
```

## Deploy recommendation (Netlify + AWS)

**Frontend → Netlify**  
Publish the `public/` folder. Set API base URL to your AWS endpoint (see `public/js/config.js`).

**Backend → AWS (recommended with your setup)**  
Keep paid / full art off Netlify.

| Piece | Suggestion |
|-------|------------|
| API | **API Gateway + Lambda** (port `server/app.py` spin logic) or a small **App Runner / ECS** container running the Python server |
| Private art | **S3 private bucket** (`icons/`, `flags/`) — spin returns short‑lived **signed URLs** |
| CDN (optional) | CloudFront in front of API / signed assets |

**Why not Netlify Functions for everything?** Fine for `/api/spin` JSON, awkward for hundreds of private images (size, cold start, no real file server). Use Netlify for UI + backup kit; AWS for full library.

**Static-only (Netlify without AWS)** still works: backup mode, top‑10 countries only.

## Pipeline

```bash
# after editing events.js or art
python3 scripts/extract_data.py
python3 scripts/build_backup_kit.py
# or
python3 scripts/build_all.py

# resolve / refresh Wikipedia links for events (writes data/event_wiki.csv)
python3 scripts/resolve_event_wiki.py
```

Top‑10 backup countries: `data/top10.json` (by 2020 births). Event Wikipedia URLs live in [`data/event_wiki.csv`](data/event_wiki.csv) — only events with a real page get a hyperlink.

## Data sources

- UN World Population Prospects (1950–2026)
- Gapminder historical estimates (1900–1949)

## License / art

Portrait & flag assets may be **licensed / paid**. Full `assests/icons|flags|original_images` and `.env*` are **gitignored** — do not push them to a public GitHub repo or Netlify. See [`private/README.md`](private/README.md).

## Legacy

`born_lottery.html` at the repo root is an older single-file draft. Prefer `public/` + `server/`.
