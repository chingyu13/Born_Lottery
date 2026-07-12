// apiBase = "" → browser calls same-origin /api/* , which Netlify's _redirects
// proxy forwards to the EB backend over HTTP (avoids HTTPS→HTTP mixed content).
// Do NOT put the http(s)://…elasticbeanstalk.com URL here directly: EB has no
// TLS listener, so an https URL times out and the app drops to backup mode.
window.BL_CONFIG = {
  apiBase: "",
  healthTimeoutMs: 2500,
  healthPath: "/api/health",
  spinPath: "/api/spin",
  worldPath: "data/world.json",
  namesPath: "data/names.json",
};
