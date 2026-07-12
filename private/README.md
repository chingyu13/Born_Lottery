# Private media

This folder documents **non-public** art and masters for **Born Lottery**.

**Live site (frontend):** [https://bornlottery.chingyu.site/](https://bornlottery.chingyu.site/) — Netlify (or similar) publishes **`public/` only**. That build includes the small backup kit; full portraits/flags stay off the CDN.

The public app only ships a **backup kit** (top‑10 countries). The full portrait/flag library and sprite masters stay private so paid / licensed assets are not dumped on Netlify or a public GitHub repo.

## GitHub

When you push this project:

| Commit? | Path | Why |
|---------|------|-----|
| **No** | `assests/icons/`, `assests/flags/`, `assests/original_images/` | Full / licensed art — **gitignored** |
| **No** | `private/icons/`, `private/flags/`, `private/original_images/` | Optional private copies — **gitignored** |
| **No** | `.env`, `.env.*` | API keys, S3 credentials |
| **Yes** | `public/assets/backup/` | Tiny offline fallback kit |
| **Yes** | `public/`, `server/`, `data/`, `scripts/`, docs | App code & public data |

Keep the full library on your machine and in a **private S3 bucket**. The API returns short‑lived signed URLs (or `/api/media/…` locally).

If icons/flags were committed in the past, they are removed from the index via `.gitignore` + `git rm --cached` — files remain on disk.

## What belongs where

| Path | What | Public? |
|------|------|---------|
| `assests/icons/` | Full WebP portraits | **No** — API / S3 signed URLs only |
| `assests/flags/` | Full flag set | **No** — same |
| `assests/original_images/` | Sprite sheet masters | **No** — gitignored |
| `private/original_images/` | Optional move target for masters | **No** |
| `public/assets/backup/` | ~20 icons + 10 flags | **Yes** — offline fallback on [bornlottery.chingyu.site](https://bornlottery.chingyu.site/) |

Today the API (`server/app.py`) reads the full library from `../assests/`. You can later relocate to:

```
private/
  original_images/   # masters
  icons/             # full web-sized set
  flags/
```

…and point `MEDIA` in the server at `private/`.

## Deploy rule of thumb

- **Live UI** → [bornlottery.chingyu.site](https://bornlottery.chingyu.site/) from `public/` only  
- **AWS S3 (private)** → full `icons/` + `flags/`  
- **API** → `/api/spin` returns one signed asset URL per result  

Never upload `assests/original_images/` or the full icon tree to a public bucket with list/read for everyone.

## Related

- Main project docs: [`../README.md`](../README.md)  
- Rebuild backup kit: `python3 scripts/build_backup_kit.py`
