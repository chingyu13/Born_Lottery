// API + backup mode config
//
// apiBase = address of your backend (the "API").
//   ""  = local (python3 server/app.py on same machine)
//   "https://xxxx.awsapprunner.com" = paste the URL AWS App Runner shows you
//
// After changing apiBase, redeploy the Netlify `public/` folder.
window.BL_CONFIG = {
  apiBase: "",
  healthTimeoutMs: 2500,
  healthPath: "/api/health",
  spinPath: "/api/spin",
  worldPath: "data/world.json",
  namesPath: "data/names.json",
};
