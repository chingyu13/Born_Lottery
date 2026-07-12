/* Born Lottery client — API-full mode with top-10 backup fallback */
(function () {
  const CFG = window.BL_CONFIG || {};
  const $ = (id) => document.getElementById(id);

  let mode = "backup"; // 'full' | 'backup'
  let WORLD = null;
  let NAMES = {};
  let MICRO = {};
  let BACKUP = window.BACKUP_DATA || null;
  let Y0 = 1900, Y1 = 2026;
  let curYear = null, spinning = false, chosenIso = null;

  // ---------- map ----------
  const svg = $("map");
  const W = 1000, LAT_TOP = 83.7, LAT_BOT = -56;
  const H = Math.round((LAT_TOP - LAT_BOT) * W / 360);
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  // Cover the full screen — crop edge = screen edge (tiny coastal countries may clip)
  svg.setAttribute("preserveAspectRatio", "xMidYMid slice");

  function layoutMap() {
    mapwrap.style.width = "100%";
    mapwrap.style.height = "100%";
  }
  const px = (lon) => (lon + 180) * W / 360;
  const py = (lat) => (LAT_TOP - lat) * W / 360;
  const els = {}, bbox = {};
  // Each country may have 3 path/circle copies (west / main / east) for seamless loop
  const elsAll = {};

  function pathFrom(t, c) {
    let dstr = "", x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    const polys = t === "Polygon" ? [c] : c;
    for (const poly of polys) for (const ring of poly) {
      dstr += "M";
      ring.forEach((pt, i) => {
        const x = px(pt[0]), y = py(pt[1]);
        if (x < x0) x0 = x; if (y < y0) y0 = y; if (x > x1) x1 = x; if (y > y1) y1 = y;
        dstr += (i ? "L" : "") + x.toFixed(1) + " " + y.toFixed(1);
      });
      dstr += "Z";
    }
    return [dstr, [x0, y0, x1, y1]];
  }

  function forCountry(iso, fn) {
    const list = elsAll[iso] || (els[iso] ? [els[iso]] : []);
    list.forEach(fn);
  }

  function buildMap() {
    // Three copies side-by-side so panning across the date line is seamless
    const offsets = [-W, 0, W];
    const groups = offsets.map((ox) => {
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("transform", `translate(${ox},0)`);
      g.dataset.wrap = String(ox);
      svg.appendChild(g);
      return g;
    });

    for (const f of WORLD.features) {
      const [dstr, bb] = pathFrom(f.t, f.c);
      const copies = [];
      groups.forEach((g, gi) => {
        const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
        p.setAttribute("d", dstr);
        p.setAttribute("class", "country");
        p.setAttribute("fill", "#FFFFFF");
        p.dataset.iso = f.id;
        g.appendChild(p);
        copies.push(p);
        if (gi === 1 && WORLD.births[f.id]) {
          els[f.id] = p;
          bbox[f.id] = bb;
        }
      });
      if (WORLD.births[f.id]) elsAll[f.id] = copies;
    }
    for (const [iso, ll] of Object.entries(MICRO)) {
      if (!WORLD.births[iso]) continue;
      const x = px(ll[0]), y = py(ll[1]);
      const copies = [];
      groups.forEach((g, gi) => {
        const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        c.setAttribute("cx", x); c.setAttribute("cy", y); c.setAttribute("r", 2.2);
        c.setAttribute("class", "micro");
        c.setAttribute("fill", "#FFFFFF");
        c.dataset.iso = iso;
        g.appendChild(c);
        copies.push(c);
        if (gi === 1) {
          els[iso] = c;
          bbox[iso] = [x - 8, y - 8, x + 8, y + 8];
        }
      });
      elsAll[iso] = copies;
    }
  }

  function spinPool() {
    if (mode === "backup") return Object.keys(BACKUP.countries).filter((k) => els[k]);
    return Object.keys(WORLD.births).filter((k) => els[k] && NAMES[k]);
  }

  function distFor(year) {
    const i = year - Y0;
    const items = []; let acc = 0;
    for (const k of spinPool()) {
      const series = mode === "backup" ? BACKUP.countries[k].births : WORLD.births[k];
      acc += series[i];
      items.push([k, acc]);
    }
    return { items, tot: acc };
  }

  function pick(dist) {
    const r = Math.random() * dist.tot;
    let lo = 0, hi = dist.items.length - 1;
    while (lo < hi) {
      const m = (lo + hi) >> 1;
      (dist.items[m][1] < r) ? lo = m + 1 : hi = m;
    }
    return dist.items[lo][0];
  }

  const pct = (x) => x >= 0.1 ? x.toFixed(1) + "%" : x >= 0.01 ? x.toFixed(2) + "%" : x.toFixed(3) + "%";
  const randColor = () => `hsl(${Math.floor(Math.random() * 360)}, 82%, 58%)`;

  function paintChoropleth(year) {
    const i = year - Y0;
    let max = 0;
    const keys = Object.keys(els).filter((k) => WORLD.births[k]);
    for (const k of keys) if (WORLD.births[k][i] > max) max = WORLD.births[k][i];
    for (const k of keys) {
      const t = Math.pow(WORLD.births[k][i] / max, 0.35);
      const c = Math.round(255 - t * (255 - 198));
      const fill = `rgb(${c},${Math.min(255, c + 2)},${Math.min(255, c + 6)})`;
      els[k].dataset.baseFill = fill;
      forCountry(k, (el) => {
        el.dataset.baseFill = fill;
        el.setAttribute("fill", fill);
        el.removeAttribute("stroke");
      });
    }
  }

  let vbCur = [0, 0, W, H], vbAnim = null;
  function animateVB(target, ms) {
    cancelAnimationFrame(vbAnim);
    // Pick the nearest wrapped target x so zoom doesn't spin across the whole globe
    let tx = target[0];
    const alternates = [tx - W, tx, tx + W];
    tx = alternates.reduce((best, v) =>
      Math.abs(v - vbCur[0]) < Math.abs(best - vbCur[0]) ? v : best, tx);
    const to = [tx, target[1], target[2], target[3]];
    const from = [...vbCur], t0 = performance.now();
    const ease = (t) => 1 - Math.pow(1 - t, 3);
    (function step(now) {
      const t = Math.min(1, (now - t0) / ms), e = ease(t);
      const next = from.map((v, i) => v + (to[i] - v) * e);
      applyVB(next);
      if (t < 1) vbAnim = requestAnimationFrame(step);
    })(t0);
  }
  let cardSide = "left"; // left|right (desktop) or top|bottom (mobile)
  function isMobileLayout() {
    return window.matchMedia("(max-width: 700px)").matches;
  }
  function zoomTo(iso, forResult) {
    if (!bbox[iso]) return;
    const [x0, y0, x1, y1] = bbox[iso];
    const mobile = isMobileLayout();
    // Mobile result: zoom out more so small countries stay recognizable with neighbors
    const pad = forResult ? (mobile ? 5.2 : 2.6) : 3.2;
    const minW = forResult ? (mobile ? 260 : 160) : 120;
    let w = (x1 - x0) * pad, h = (y1 - y0) * pad;
    w = Math.max(w, minW); h = Math.max(h, minW * H / W);
    if (w / h > W / H) h = w * H / W; else w = h * W / H;
    const mid = (x0 + x1) / 2;
    const midY = (y0 + y1) / 2;
    let cx = mid, cy = midY;
    if (forResult) {
      if (mobile) {
        // Country northern on map → card bottom; southern → card top
        cardSide = midY < H * 0.5 ? "bottom" : "top";
        // Keep country inside the viewBox, just bias it into the open half
        // (fraction of viewBox height — NOT of full map, or it flies off-screen)
        const bias = h * 0.22;
        cy = midY + (cardSide === "bottom" ? bias : -bias);
      } else {
        cardSide = mid < W * 0.33 ? "right" : "left";
        cx = mid + (cardSide === "left" ? -1 : 1) * w * 0.22;
      }
    }
    animateVB([cx - w / 2, cy - h / 2, w, h], forResult ? 950 : 500);
  }
  function placeCardFor(iso) {
    if (!bbox[iso]) { cardSide = isMobileLayout() ? "top" : "left"; return; }
    if (isMobileLayout()) {
      const midY = (bbox[iso][1] + bbox[iso][3]) / 2;
      cardSide = midY < H * 0.5 ? "bottom" : "top";
    } else {
      const mid = (bbox[iso][0] + bbox[iso][2]) / 2;
      cardSide = mid < W * 0.45 ? "right" : "left";
    }
  }
  const resetVB = () => animateVB([0, 0, W, H], 700);

  // ---------- explore (chance map) ----------
  let exploreMode = false, pinnedIso = null, hoverIso = null;
  let mapPanning = false, panMoved = false, panLast = null, panStart = null;
  const HIGHLIGHT = "#5BA3FF";
  const mapwrap = $("mapwrap"), maptip = $("maptip");

  function chanceOf(iso, year) {
    const dist = distFor(year);
    const i = year - Y0;
    const series = mode === "backup" && BACKUP.countries[iso]
      ? BACKUP.countries[iso].births
      : WORLD.births[iso];
    const births = series ? series[i] : 0;
    return dist.tot > 0 ? births / dist.tot : 0;
  }
  function showTip(iso, clientX, clientY) {
    if (!iso || !NAMES[iso] || !curYear) { maptip.classList.remove("show"); return; }
    const p = chanceOf(iso, curYear);
    $("tip-name").textContent = NAMES[iso][0];
    $("tip-pct").textContent = pct(p * 100);
    $("tip-sub").textContent = mode === "backup" && !BACKUP.countries[iso]
      ? `(map only · backup spins top ${Object.keys(BACKUP.countries).length})`
      : `of births in ${curYear}`;
    const rect = mapwrap.getBoundingClientRect();
    let left = clientX - rect.left, top = clientY - rect.top;
    left = Math.max(70, Math.min(rect.width - 70, left));
    top = Math.max(50, Math.min(rect.height - 20, top));
    maptip.style.left = left + "px";
    maptip.style.top = top + "px";
    maptip.classList.add("show");
  }
  function hideTip() { if (!pinnedIso) maptip.classList.remove("show"); }
  function baseFillOf(iso) { return els[iso]?.dataset?.baseFill || "#FFFFFF"; }
  function paintActiveFill() {
    const focus = pinnedIso || hoverIso;
    for (const k in els) {
      const fill = k === focus ? HIGHLIGHT : baseFillOf(k);
      forCountry(k, (el) => {
        el.classList.toggle("is-active", k === focus);
        el.setAttribute("fill", fill);
        if (k === focus) el.setAttribute("stroke", "#1F3B61");
        else el.removeAttribute("stroke");
      });
    }
  }
  function enableExplore() {
    exploreMode = true; pinnedIso = null; hoverIso = null;
    document.body.classList.add("explore");
    hideTip(); paintActiveFill();
    syncMapNavClass();
  }
  function disableExplore() {
    exploreMode = false; pinnedIso = null; hoverIso = null;
    document.body.classList.remove("explore");
    mapwrap.classList.remove("panning");
    hideTip(); maptip.classList.remove("show");
    for (const k in els) {
      forCountry(k, (el) => {
        el.classList.remove("is-active");
        el.removeAttribute("stroke");
      });
    }
    syncMapNavClass();
  }
  function isoFromEventTarget(t) {
    if (!t) return null;
    const iso = t.dataset && t.dataset.iso;
    return iso && els[iso] ? iso : null;
  }
  function wrapX(x) {
    return ((x % W) + W) % W;
  }
  function clampVB(vb) {
    let [x, y, w, h] = vb;
    const minW = W * 0.08;
    w = Math.min(W, Math.max(minW, w));
    h = w * H / W;
    // Horizontal: wrap forever (Pacific loop). Vertical: stay in bounds.
    x = wrapX(x);
    y = Math.min(H - h, Math.max(0, y));
    return [x, y, w, h];
  }
  function applyVB(vb) {
    vbCur = clampVB(vb);
    svg.setAttribute("viewBox", vbCur.join(" "));
  }

  // Slow leftward drift when the window is narrower than the map aspect (sides are cropped)
  let autoScrollRaf = null, autoScrollLast = 0;
  function windowCropsMapHorizontally() {
    return window.innerWidth / window.innerHeight < (W / H) * 0.98;
  }
  function stopAutoScroll() {
    if (autoScrollRaf) cancelAnimationFrame(autoScrollRaf);
    autoScrollRaf = null;
  }
  function tickAutoScroll(now) {
    autoScrollRaf = requestAnimationFrame(tickAutoScroll);
    if (mapPanning || document.hidden) { autoScrollLast = now; return; }
    if (!windowCropsMapHorizontally()) { autoScrollLast = now; return; }

    const onLanding = document.body.classList.contains("landing");
    // Drift on landing, and during the spin (before result zoom). Never after result.
    const allowDrift = onLanding || spinning;
    if (!allowDrift) { autoScrollLast = now; return; }
    // Once zoomed into a country (result), stop — even if spinning is still true briefly
    if (vbCur[2] < W * 0.88) { autoScrollLast = now; return; }

    if (!autoScrollLast) autoScrollLast = now;
    const dt = Math.min(0.05, (now - autoScrollLast) / 1000);
    autoScrollLast = now;
    // Spin a bit slower than the landing drift
    const speed = spinning ? W * 0.011 : W * 0.018;
    applyVB([vbCur[0] + speed * dt, vbCur[1], vbCur[2], vbCur[3]]);
  }
  function startAutoScroll() {
    stopAutoScroll();
    autoScrollLast = 0;
    autoScrollRaf = requestAnimationFrame(tickAutoScroll);
  }

  svg.addEventListener("pointermove", (e) => {
    if (!exploreMode || mapPanning || panMoved) return;
    const iso = isoFromEventTarget(e.target);
    if (pinnedIso) { if (iso === pinnedIso) showTip(iso, e.clientX, e.clientY); return; }
    if (iso) { hoverIso = iso; paintActiveFill(); showTip(iso, e.clientX, e.clientY); }
    else { hoverIso = null; paintActiveFill(); hideTip(); }
  });
  svg.addEventListener("pointerleave", () => {
    if (!exploreMode) return;
    if (!pinnedIso) { hoverIso = null; paintActiveFill(); hideTip(); }
  });
  svg.addEventListener("click", (e) => {
    if (!exploreMode || spinning || panMoved) return;
    const iso = isoFromEventTarget(e.target);
    if (!iso) { pinnedIso = null; hoverIso = null; paintActiveFill(); hideTip(); maptip.classList.remove("show"); return; }
    pinnedIso = hoverIso = iso; paintActiveFill(); showTip(iso, e.clientX, e.clientY);
    zoomTo(iso);
  });
  function mapNavOn() {
    return !document.body.classList.contains("landing") && !spinning;
  }
  function syncMapNavClass() {
    document.body.classList.toggle("map-nav", mapNavOn());
  }

  mapwrap.addEventListener("wheel", (e) => {
    if (!mapNavOn()) return;
    e.preventDefault();
    const rect = svg.getBoundingClientRect();
    const mx = (e.clientX - rect.left) / rect.width;
    const my = (e.clientY - rect.top) / rect.height;
    const [x, y, w, h] = vbCur;
    const factor = e.deltaY > 0 ? 1.12 : 1 / 1.12;
    const nw = w * factor, nh = h * factor;
    cancelAnimationFrame(vbAnim);
    applyVB([x + mx * w - mx * nw, y + my * h - my * nh, nw, nh]);
  }, { passive: false });

  mapwrap.addEventListener("pointerdown", (e) => {
    if (!mapNavOn()) return;
    if (e.target.closest && (e.target.closest("#backbtn") || e.target.closest("#result") || e.target.closest("#intro"))) return;
    mapPanning = true; panMoved = false;
    panStart = panLast = { x: e.clientX, y: e.clientY };
    mapwrap.setPointerCapture?.(e.pointerId);
  });
  mapwrap.addEventListener("pointermove", (e) => {
    if (!mapPanning || !mapNavOn()) return;
    const dist = Math.hypot(e.clientX - panStart.x, e.clientY - panStart.y);
    if (!panMoved && dist < 6) return;
    if (!panMoved) {
      panMoved = true;
      mapwrap.classList.add("panning");
    }
    const rect = svg.getBoundingClientRect();
    const [x, y, w, h] = vbCur;
    const dx = (e.clientX - panLast.x) / rect.width * w;
    const dy = (e.clientY - panLast.y) / rect.height * h;
    panLast = { x: e.clientX, y: e.clientY };
    cancelAnimationFrame(vbAnim);
    // Horizontal drag wraps (Japan ↔ Pacific ↔ Americas)
    applyVB([x - dx, y - dy, w, h]);
  });
  function endPan(e) {
    if (!mapPanning) return;
    mapPanning = false; mapwrap.classList.remove("panning");
    try { mapwrap.releasePointerCapture?.(e.pointerId); } catch (_) {}
    setTimeout(() => { panMoved = false; }, 0);
  }
  mapwrap.addEventListener("pointerup", endPan);
  mapwrap.addEventListener("pointercancel", endPan);

  // ---------- figures ----------
  function preloadAssets(assets) {
    if (!assets) return Promise.resolve();
    const urls = [assets.icon, assets.flag, assets.pole].filter(Boolean);
    return Promise.all(urls.map((url) => new Promise((resolve) => {
      const img = new Image();
      img.onload = img.onerror = () => resolve();
      img.src = url;
    })));
  }

  function setFigureFromAssets(assets) {
    const img = $("avatar"), stack = $("flagstack"), fo = $("flagover"), fp = $("flagpole");
    if (assets?.icon) {
      img.classList.remove("emoji");
      img.src = assets.icon;
      img.style.display = "block";
      img.alt = "";
    } else {
      img.removeAttribute("src");
      img.classList.add("emoji");
      img.alt = "👶";
      img.style.display = "flex";
      img.textContent = "👶";
    }
    if (assets?.flag) {
      stack.classList.remove("hide");
      stack.dataset.pole = assets.pole_key || "3x2";
      fo.src = assets.flag; fo.style.display = "block";
      if (assets.pole) { fp.src = assets.pole; fp.style.display = "block"; }
      else { fp.removeAttribute("src"); fp.style.display = "none"; }
    } else {
      stack.classList.add("hide");
      fo.removeAttribute("src"); fp.removeAttribute("src");
    }
  }

  function pickEventBackup(iso3, year) {
    const life = 85;
    const age = (e) => e[0] - year;
    let pool = (BACKUP.countries[iso3]?.events || []).filter((e) => e[0] >= year && age(e) <= life);
    if (!pool.length) pool = (BACKUP.global_events || []).filter((e) => e[0] >= year && age(e) <= life);
    if (!pool.length) return null;
    const t1 = pool.filter((e) => age(e) >= 20 && age(e) <= 40);
    const t2 = pool.filter((e) => age(e) > 10);
    const chosen = t1.length ? t1 : t2.length ? t2 : pool;
    return chosen[Math.floor(Math.random() * chosen.length)];
  }

  function backupRevealPayload(iso, year, dist, color) {
    const c = BACKUP.countries[iso];
    const i = year - Y0;
    const pCountry = c.births[i] / dist.tot;
    const sr = BACKUP.sexr_default || 105;
    const pMale = sr / (sr + 100);
    const male = Math.random() < pMale;
    const pSex = male ? pMale : 1 - pMale;
    const mIcons = c.icons.m || [], fIcons = c.icons.f || [];
    let iconFile = male ? (mIcons[0] || fIcons[0]) : (fIcons[0] || mIcons[0]);
    if (male && mIcons.length) iconFile = mIcons[Math.floor(Math.random() * mIcons.length)];
    if (!male && fIcons.length) iconFile = fIcons[Math.floor(Math.random() * fIcons.length)];
    const poleKey = c.pole || "3x2";
    const ev = pickEventBackup(iso, year);
    return {
      mode: "backup",
      year,
      iso3: iso,
      name: c.name,
      male,
      sex_label: male ? "Male" : "Female",
      ethnicity: null,
      city_line: "somewhere nearby",
      probs: {
        country: pct(pCountry * 100),
        sex: pct(pSex * 100),
        ethnicity: null,
        combo: pct(pCountry * pSex * 100),
      },
      event: ev ? { year: ev[0], text: ev[1], age: ev[0] - year } : null,
      assets: {
        icon: iconFile ? `assets/backup/icons/${iconFile}` : null,
        flag: c.flag ? `assets/backup/flags/${c.flag}` : null,
        pole: poleKey === "special" ? null : `assets/poles/flagpole_${poleKey}.svg`,
        pole_key: poleKey,
      },
      source: year < 1950 ? "Historical estimate" : "UN estimate",
      _color: color,
    };
  }

  function showResult(payload) {
    chosenIso = payload.iso3;
    if (els[payload.iso3] && payload._color) {
      forCountry(payload.iso3, (el) => {
        el.setAttribute("fill", payload._color);
        el.setAttribute("stroke", "#2B5AA8");
      });
    }
    zoomTo(payload.iso3, true);
    const res = $("result");
    res.classList.remove("right", "top", "bottom");
    if (isMobileLayout()) {
      res.classList.add(cardSide === "bottom" ? "bottom" : "top");
    } else {
      res.classList.toggle("right", cardSide === "right");
    }
    $("flashname").innerHTML = "";
    setFigureFromAssets(payload.assets);
    $("res-title").textContent = `born in ${payload.year}…`;
    $("srcbadge").textContent = payload.source || "UN estimate";
    $("cityline").textContent = payload.city_line || "";
    $("k-country").textContent = payload.name;
    $("v-country").textContent = payload.probs.country;
    $("k-sex").textContent = payload.sex_label;
    $("v-sex").textContent = payload.probs.sex;
    if (payload.ethnicity && payload.probs.ethnicity) {
      $("row-eth").style.display = "flex";
      $("k-eth").textContent = payload.ethnicity;
      $("v-eth").textContent = payload.probs.ethnicity;
    } else $("row-eth").style.display = "none";
    $("v-total").textContent = payload.probs.combo;
    const evEl = $("eventline");
    if (payload.event) {
      const age = payload.event.age;
      const when = age === 0 ? "in the year you’re born" : `when you’re ${age} years old`;
      evEl.innerHTML = `You might experience <b>${payload.event.text}</b> ${when}.`;
    } else {
      evEl.innerHTML = `You might live a <b>peaceful life</b>.`;
    }
    setTimeout(() => { $("result").classList.add("show"); spinning = false; syncMapNavClass(); }, 700);
  }

  async function spin(year) {
    spinning = true;
    syncMapNavClass();
    paintChoropleth(year);
    const flashEl = $("flashname");
    const steps = 32 + Math.floor(Math.random() * 8);
    let n = 0, prev = null, prevFill = null;
    let target = null;
    let revealPayload = null;
    let assetsReady = Promise.resolve();

    if (mode === "full") {
      try {
        const res = await fetch(`${CFG.apiBase}${CFG.spinPath}?year=${year}`, { cache: "no-store" });
        if (!res.ok) throw new Error("spin failed");
        revealPayload = await res.json();
        if (revealPayload.error) throw new Error(revealPayload.error);
        target = revealPayload.iso3;
      } catch (err) {
        console.warn("API spin failed, using backup", err);
        enterBackupMode("api spin failed");
        revealPayload = null;
        target = pick(distFor(year));
      }
    } else {
      target = pick(distFor(year));
    }

    const animDist = distFor(year);
    // Build backup payload now (locks gender/icon) so we can prefetch during the spin
    if (!revealPayload) {
      revealPayload = backupRevealPayload(target, year, animDist, null);
    }
    // Warm icon/flag/pole while the roulette animation runs
    assetsReady = preloadAssets(revealPayload.assets);

    (function tick() {
      if (prev && els[prev]) forCountry(prev, (el) => el.setAttribute("fill", prevFill));
      n++;
      const last = n >= steps;
      let iso = last ? target : pick(animDist);
      if (!els[iso]) iso = target;
      prev = iso;
      prevFill = els[iso].getAttribute("fill");
      const col = randColor();
      forCountry(iso, (el) => el.setAttribute("fill", col));
      flashEl.innerHTML = `<span class="yr">born in ${year} in…</span>${(NAMES[iso] && NAMES[iso][0]) || iso}`;
      if (!last) {
        const t = n / steps;
        setTimeout(tick, 28 + 400 * t * t * t);
      } else {
        setTimeout(async () => {
          revealPayload._color = col;
          // Prefer showing with images ready; don't hang forever on a dead link
          await Promise.race([
            assetsReady,
            new Promise((r) => setTimeout(r, 1200)),
          ]);
          showResult(revealPayload);
        }, 400);
      }
    })();
  }

  // ---------- intro slider ----------
  const yearin = $("yearin"), sfill = $("sfill"), sknob = $("sknob"), slider = $("slider");
  function setSlider(y) {
    const t = (y - Y0) / (Y1 - Y0);
    sfill.style.width = (t * 100) + "%";
    sknob.style.left = (t * 100) + "%";
  }
  function sliderFromEvent(e) {
    const r = slider.getBoundingClientRect();
    const cx = (e.touches ? e.touches[0].clientX : e.clientX);
    let t = (cx - r.left) / r.width; t = Math.max(0, Math.min(1, t));
    const y = Math.round(Y0 + t * (Y1 - Y0));
    yearin.value = y; setSlider(y);
  }
  let dragging = false;
  slider.addEventListener("mousedown", (e) => { dragging = true; sliderFromEvent(e); });
  window.addEventListener("mousemove", (e) => { if (dragging) sliderFromEvent(e); });
  window.addEventListener("mouseup", () => { dragging = false; });
  slider.addEventListener("touchstart", (e) => { dragging = true; sliderFromEvent(e); }, { passive: true });
  window.addEventListener("touchmove", (e) => { if (dragging) sliderFromEvent(e); }, { passive: true });
  yearin.addEventListener("input", () => {
    let y = parseInt(yearin.value, 10);
    if (y >= Y0 && y <= Y1) setSlider(y);
  });
  $("yrup").onclick = () => {
    let y = Math.min(Y1, (parseInt(yearin.value, 10) || Y0) + 1);
    yearin.value = y; setSlider(y);
  };
  $("yrdn").onclick = () => {
    let y = Math.max(Y0, (parseInt(yearin.value, 10) || Y0) - 1);
    yearin.value = y; setSlider(y);
  };

  function hideResult() {
    $("result").classList.remove("show");
    if (chosenIso && curYear != null) paintChoropleth(curYear);
    resetVB();
  }
  function backToLanding() {
    hideResult(); disableExplore(); resetVB();
    for (const k in els) {
      forCountry(k, (el) => {
        el.setAttribute("fill", "#FFFFFF");
        el.removeAttribute("stroke");
        el.classList.remove("is-active");
      });
    }
    document.body.classList.add("landing");
    $("flashname").innerHTML = "";
    $("backbtn").style.display = "none";
    $("intro").style.display = "flex";
    syncMapNavClass();
    yearin.focus();
  }
  function start() {
    const y = parseInt(yearin.value, 10);
    if (!(y >= Y0 && y <= Y1)) { $("err").textContent = `Enter a year between ${Y0} and ${Y1}`; return; }
    $("err").textContent = "";
    curYear = y;
    document.body.classList.remove("landing");
    disableExplore();
    $("backbtn").style.display = "none";
    $("intro").style.display = "none";
    syncMapNavClass();
    spin(y);
  }

  $("startbtn").onclick = start;
  $("again").onclick = () => { if (!spinning) { hideResult(); setTimeout(() => spin(curYear), 400); } };
  $("newyear").onclick = backToLanding;
  $("backbtn").onclick = backToLanding;
  $("viewchance").onclick = () => {
    const y = parseInt(yearin.value, 10);
    if (!(y >= Y0 && y <= Y1)) { $("err").textContent = `Enter a year between ${Y0} and ${Y1}`; return; }
    $("err").textContent = "";
    curYear = y;
    document.body.classList.remove("landing");
    $("intro").style.display = "none";
    paintChoropleth(y);
    $("flashname").innerHTML = `<span class="yr">where babies were born in</span>${y}`;
    $("backbtn").style.display = "block";
    enableExplore();
    syncMapNavClass();
    resetVB();
  };
  yearin.addEventListener("keydown", (e) => { if (e.key === "Enter") start(); });

  function setModeBanner() {
    let el = $("modebanner");
    if (!el) {
      el = document.createElement("div");
      el.id = "modebanner";
      $("mapwrap").appendChild(el);
    }
    if (mode === "full") {
      el.classList.remove("show");
      el.textContent = "";
      return;
    }
    el.textContent = "limited · top " + Object.keys(BACKUP.countries).length;
    el.classList.add("show");
  }

  function enterBackupMode(reason) {
    mode = "backup";
    console.info("[BornLottery] backup mode:", reason);
    setModeBanner();
  }

  async function probeHealth() {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), CFG.healthTimeoutMs || 2500);
    try {
      const res = await fetch(`${CFG.apiBase}${CFG.healthPath}`, { signal: ctrl.signal, cache: "no-store" });
      clearTimeout(t);
      if (!res.ok) throw new Error("bad status");
      const j = await res.json();
      if (!j.ok) throw new Error("not ok");
      mode = "full";
      setModeBanner();
      return true;
    } catch (e) {
      clearTimeout(t);
      enterBackupMode(e.message || "health failed");
      return false;
    }
  }

  async function boot() {
    document.body.classList.add("landing");
    const [world, names] = await Promise.all([
      fetch(CFG.worldPath || "data/world.json").then((r) => r.json()),
      fetch(CFG.namesPath || "data/names.json").then((r) => r.json()),
    ]);
    WORLD = world;
    NAMES = names;
    Y0 = world.Y0; Y1 = world.Y1;
    yearin.min = Y0; yearin.max = Y1;
    if (!BACKUP) {
      BACKUP = await fetch("data/backup.json").then((r) => r.json());
    }
    // names for backup countries always present in NAMES from world extract
    await probeHealth();
    // microdots only matter for map; try public meta-backup then ignore
    try {
      const mb = await fetch("data/meta-backup.json").then((r) => r.json());
      MICRO = mb.micro || {};
    } catch (_) { MICRO = {}; }

    buildMap();
    layoutMap();
    startAutoScroll();
    window.addEventListener("resize", () => { layoutMap(); });
    setSlider(parseInt(yearin.value, 10) || 1990);
    syncMapNavClass();
    yearin.focus();
  }

  boot().catch((err) => {
    console.error(err);
    $("err").textContent = "Failed to load data. Check public/data files.";
  });
})();
