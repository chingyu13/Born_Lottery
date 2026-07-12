# Private media

This folder documents **non-public** art and masters for **Born Lottery**.

The public app (`public/`) only ships a small **backup kit** (top‑10 countries). The full portrait/flag library and sprite masters stay private so paid / licensed assets are not dumped on Netlify or GitHub Pages.

## What belongs here (or in `assests/`)

| Path | What | Public? |
|------|------|---------|
| `assests/icons/` | Full WebP portraits | **No** — serve via API / S3 signed URLs only |
| `assests/flags/` | Full flag set | **No** — same |
| `assests/original_images/` | Sprite sheet masters | **No** — gitignored |
| `private/original_images/` | Optional move target for masters | **No** |
| `public/assets/backup/` | ~20 icons + 10 flags | **Yes** — offline fallback |

Today the API (`server/app.py`) reads the full library from `../assests/`. You can later relocate to:

```
private/
  original_images/   # masters
  icons/             # full web-sized set
  flags/
```

…and point `MEDIA` in the server at `private/`.

## Deploy rule of thumb

- **Netlify / CDN** → deploy `public/` only  
- **AWS S3 (private)** → full `icons/` + `flags/`  
- **API** → `/api/spin` returns one signed asset URL per result  

Never upload `assests/original_images/` or the full icon tree to a public bucket with list/read for everyone.

## Related

- Main project docs: [`../README.md`](../README.md)  
- Rebuild backup kit: `python3 scripts/build_backup_kit.py`
