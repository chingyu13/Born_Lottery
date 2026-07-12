# Where does the API URL come from? Where do I paste it?

## Short answer

| Question | Answer |
|----------|--------|
| What is the API URL? | The **https address AWS gives you** after you deploy the backend (App Runner). |
| Where do I paste it? | File **`public/js/config.js`**, field **`apiBase`**. Then **redeploy Netlify**. |

Example after you get the URL from AWS:

```js
// public/js/config.js
window.BL_CONFIG = {
  apiBase: "https://xxxxx.ap-southeast-2.awsapprunner.com",  // ← paste HERE
  healthTimeoutMs: 2500,
  healthPath: "/api/health",
  spinPath: "/api/spin",
  worldPath: "data/world.json",
  namesPath: "data/names.json",
};
```

- Locally, `apiBase: ""` means “same computer” (`http://127.0.0.1:8765`).
- On Netlify, the site cannot see your laptop, so it needs the AWS https URL.

---

## Do this in order (App Runner)

### A. Push your code to GitHub
Include: `Dockerfile`, `server/`, `data/`, `public/`.

### B. Create App Runner (this CREATES the API URL)

1. AWS Console → search **App Runner**
2. **Create service**
3. Source: **Container registry** → **Amazon ECR**  
   (First you build/push the Docker image — or use “Source code repository” if you connect GitHub and the Dockerfile at repo root.)
4. Simpler path for many people: **Source code repository** → connect GitHub → select this repo → deploy  
   - Build: Dockerfile at repository root  
   - Port: **8765**
5. Environment variables (add these):

| Name | Value |
|------|--------|
| `S3_BUCKET` | `bornlottery-884408162415-ap-southeast-2-an` |
| `S3_REGION` | `ap-southeast-2` |
| `FRONTEND_ORIGIN` | `https://YOUR-SITE.netlify.app` (your real Netlify URL) |
| `PORT` | `8765` |

6. Instance role / access role: allow **`s3:GetObject`** on that bucket.
7. Create → wait until status is **Running**.
8. On the service page, copy **Default domain**  
   → looks like `https://……ap-southeast-2.awsapprunner.com`  
   **That string IS your API.**

### C. Test the API in the browser
Open:

`https://YOUR-APPRUNNER-DOMAIN/api/health`

You should see JSON with `"ok": true`.

### D. Paste into the frontend (Phase 4)
1. Open `public/js/config.js` on your computer
2. Set `apiBase` to that App Runner https URL (**no** trailing `/`)
3. Commit / push (or drag-drop `public/` again)
4. Netlify redeploys
5. Open your Netlify site → “limited” tag should **disappear** → full mode

---

## If App Runner feels hard

You can pause on full mode: Netlify + backup (top 10) already works.  
Come back to App Runner when ready — the only “magic” is: **AWS shows a URL → you paste it into `apiBase`**.
