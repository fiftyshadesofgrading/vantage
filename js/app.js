// app.js — map, list and detail for Vantage
import { dist, bearing, fmtDist, compass, cone } from "./geo.js";
import * as S from "./sensors.js";
import { prefs, savePrefs, calibrations, exportCalibrations } from "./store.js";
import { initAR, openAR, loadStill } from "./ar.js";
import { initViewer, openViewer } from "./viewer.js";

const L = window.L;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const params = new URLSearchParams(location.search);

let DATA, ITEMS = [], LOCAL = {}, SERVER_CALS = {}, GROUPS = [];
let REGIONS = {}, REGION = null;
let map, markerLayer, coneLayer, meMarker, meCircle;
let filter = "all";
let selected = null;
let firstFix = true;
const announced = new Set();

/* ── boot ─────────────────────────────────────────────────────── */
async function boot() {
  const [data, local, cals] = await Promise.all([
    fetch("data/artworks.json", { cache: "no-cache" }).then(r => r.json()),
    fetch("data/local.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : {})).catch(() => ({})),
    fetch("data/calibrations.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : {})).catch(() => ({})),
  ]);
  DATA = data;
  REGIONS = data.regions || { cape_ann: { label: "Cape Ann", declination: -14.4, ...data.region } };
  LOCAL = local.items || {};
  SERVER_CALS = cals.calibrations || {};
  ITEMS = data.items.map(it => ({ ...it, _remote: { ...it.image }, _orig: { ...it.vantage } }));
  const wantItem = ITEMS.find(i => i.id === params.get("item"));
  setRegion([wantItem?.region, params.get("region"), prefs.region].find(k => k && REGIONS[k]) || Object.keys(REGIONS)[0]);
  applyCalibrations();
  buildGroups();

  initMap();
  initViewer();
  initAR({
    artist, imageUrl, serverCals: () => SERVER_CALS, pickPhoto,
    onCalibrated: it => { applyCalibrations(); buildGroups(); drawMap(); if (selected?.id === it.id) renderDetail(it); },
  });
  bindUI();
  drawMap();
  renderList();

  S.on("fix", onFix);
  S.on("heading", () => { if (meMarker) updateMe(); });

  const sim = params.get("sim");
  if (sim) { const [la, lo] = sim.split(",").map(Number); if (isFinite(la) && isFinite(lo)) S.simulate(la, lo); }
  else if (window.isSecureContext) S.startGeo();
  if (!window.isSecureContext) showBanner();

  const want = params.get("item");
  if (want) { const it = ITEMS.find(i => i.id === want); if (it) select(it, { fly: true }); }
}

function applyCalibrations() {
  for (const it of ITEMS) {
    const cal = calibrations[it.id] || SERVER_CALS[it.id];
    it.vantage = { ...it._orig };
    it.calibrated = !!cal;
    if (!cal) continue;
    if (cal.lat != null) { it.vantage.lat = cal.lat; it.vantage.lon = cal.lon; }
    if (cal.heading != null) it.vantage.heading = cal.heading;
    if (cal.fov != null && it.vantage.fov != null) it.vantage.fov = cal.fov;
  }
}

/** items sharing (nearly) the same vantage become one pin */
function buildGroups() {
  GROUPS = [];
  for (const it of ITEMS) {
    const g = GROUPS.find(g => dist(g.at, it.vantage) < 15);
    if (g) g.items.push(it); else GROUPS.push({ at: { lat: it.vantage.lat, lon: it.vantage.lon }, items: [it] });
  }
  for (const it of ITEMS) it._group = GROUPS.find(g => g.items.includes(it));
}

export const artist = it => DATA.artists[it.artist] || { name: it.artist, color: "#555" };
function imageUrl(it, size) {
  const loc = LOCAL[it.id];
  if (loc && loc[size]) return loc[size];
  return it.image[size] || it.image.web;
}
/**
 * Thumbnail <img> honouring image.crop (stereo cards, postcard borders): the image is scaled and
 * offset inside a clipping box so the box shows a centred, box-shaped piece of the cropped picture.
 * aspect = box width / height. Without a crop, a plain <img> (object-fit: cover does the rest).
 */
function thumbImg(it, aspect, extra = "") {
  const src = `src="${esc(imageUrl(it, "thumb"))}" data-remote="${esc(it._remote.thumb)}" alt="" loading="lazy" onerror="vantageImgRetry(this)"`;
  const c = it.image.crop, W = it.image.width, H = it.image.height;
  if (!c || !c.some(Boolean) || !W || !H) return `<img ${src}${extra}>`;
  const [l, t, r, b] = c, cw = W * (1 - l - r), ch = H * (1 - t - b);
  let rw = cw, rh = ch;
  if (cw / ch > aspect) rw = ch * aspect; else rh = cw / aspect;
  const rx = W * l + (cw - rw) / 2, ry = H * t + (ch - rh) / 2, pc = v => `${(v * 100).toFixed(2)}%`;
  const st = `position:absolute;max-width:none;object-fit:fill;border-radius:0;width:${pc(W / rw)} !important;height:${pc(H / rh)} !important;left:${pc(-rx / rw)};top:${pc(-ry / rh)}`;
  return `<span class="tb">${`<img ${src} style="${st}"${extra}>`}</span>`;
}

const visible = it => filter === "all" || it.artist === filter;
/** list membership: the current region (items from regions without their own entry show under the first one) */
const inRegion = it => (REGIONS[it.region] ? it.region : Object.keys(REGIONS)[0]) === REGION;

/** switch the map/list region; also sets the compass declination for that area */
function setRegion(key, { fly = false } = {}) {
  if (!REGIONS[key]) return;
  REGION = key;
  const r = REGIONS[key];
  if (r.declination != null) prefs.declination = r.declination;
  prefs.region = key; savePrefs();
  const btn = $("#btnRegion");
  if (btn) btn.innerHTML = `${esc(r.label)}<span class="caret" aria-hidden="true">▾</span>`;
  document.title = `Vantage · ${r.label}`;
  if (fly && map) map.flyTo(r.center, r.zoom, { duration: 1.2 });
}
function nextRegion() {
  const keys = Object.keys(REGIONS);
  setRegion(keys[(keys.indexOf(REGION) + 1) % keys.length], { fly: true });
  filter = "all";
  renderList();
  toast(`${REGIONS[REGION].label}: ${ITEMS.filter(inRegion).length} pictures`, 2200);
}

/* ── map ──────────────────────────────────────────────────────── */
function initMap() {
  map = L.map("map", { zoomControl: false, attributionControl: true, tap: false }).setView(REGIONS[REGION].center, REGIONS[REGION].zoom);
  L.control.zoom({ position: "topright" }).addTo(map);
  const osm = () => L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  });
  const bases = {
    Engraving: osm().on("add", () => document.body.classList.add("engraving")).on("remove", () => document.body.classList.remove("engraving")),
    Streets: osm(),
    Satellite: L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 19, attribution: "Imagery &copy; Esri, Maxar, Earthstar Geographics",
    }),
  };
  const key = { engraving: "Engraving", streets: "Streets", satellite: "Satellite" }[prefs.tiles] || "Engraving";
  bases[key].addTo(map);
  document.body.classList.toggle("engraving", key === "Engraving");
  L.control.layers(bases, null, { position: "topright" }).addTo(map);
  map.on("baselayerchange", e => { prefs.tiles = e.name.toLowerCase(); savePrefs(); });
  coneLayer = L.layerGroup().addTo(map);
  markerLayer = L.layerGroup().addTo(map);
  map.on("zoomend", () => document.body.classList.toggle("far", map.getZoom() < 14));
  // long-press / right-click: pretend to stand here (desk testing, or to preview the guidance)
  map.on("contextmenu", e => {
    const { lat, lng } = e.latlng;
    L.popup({ className: "sim-pop" }).setLatLng(e.latlng)
      .setContent(`<button class="pill" id="simHere">Pretend I'm standing here</button>`).openOn(map);
    setTimeout(() => $("#simHere")?.addEventListener("click", () => { map.closePopup(); S.simulate(lat, lng); toast("Simulated location set — open any view to see the guidance.", 3500); }), 0);
  });
}

function drawMap() {
  coneLayer.clearLayers(); markerLayer.clearLayers();
  for (const it of ITEMS) {
    if (!visible(it) || it.vantage.heading == null) continue;
    const v = it.vantage, sel = selected?.id === it.id;
    L.polygon(cone(v, v.heading, Math.max(v.fov || 30, 6), Math.min(v.range || 600, sel ? 1600 : 700)), {
      color: artist(it).color, weight: sel ? 2 : 1, opacity: sel ? 0.9 : 0.35, fillOpacity: sel ? 0.18 : 0.06,
      dashArray: v.confidence === "general" ? "4 5" : null, interactive: false, className: "cone",
    }).addTo(coneLayer);
  }
  for (const g of GROUPS) {
    const items = g.items.filter(visible);
    if (!items.length) continue;
    const lead = items.find(i => i.id === selected?.id) || items[0];
    const conf = items.some(i => i.vantage.confidence === "documented") ? "documented" : items.some(i => i.vantage.confidence === "inferred") ? "inferred" : "general";
    const html = `<div class="pin conf-${conf}${lead.kind === "birdseye" ? " square" : ""}${items.some(i => i.id === selected?.id) ? " sel" : ""}" style="--c:${artist(lead).color}">
        ${thumbImg(lead, 1)}
        ${items.length > 1 ? `<b>${items.length}</b>` : ""}${lead.calibrated ? '<i title="field-calibrated">✓</i>' : ""}</div>`;
    L.marker([g.at.lat, g.at.lon], { icon: L.divIcon({ html, className: "pin-wrap", iconSize: [46, 46], iconAnchor: [23, 23] }), title: items.map(i => i.title).join(" / "), riseOnHover: true })
      .on("click", () => select(items.includes(selected) ? selected : lead, { fly: false }))
      .addTo(markerLayer);
  }
  if (S.state.fix) updateMe();
}

function onFix(fix) {
  if (fix) {
    updateMe();
    if (firstFix && !params.get("item")) {
      firstFix = false;
      const home = Object.entries(REGIONS).find(([, r]) => dist(fix, { lat: r.center[0], lon: r.center[1] }) < 30000);
      if (home && home[0] !== REGION) { setRegion(home[0]); filter = "all"; }
      const near = ITEMS.some(it => dist(fix, it.vantage) < 6000);
      if (near) map.setView([fix.lat, fix.lon], Math.max(map.getZoom(), 16));
    }
    proximity(fix);
  }
  if (!selected) renderList(); else refreshWhere();
  $("#btnLocate").classList.toggle("live", !!fix);
}

function updateMe() {
  const f = S.state.fix; if (!f) return;
  const ll = [f.lat, f.lon], h = S.state.heading;
  const html = `<div class="me${f.simulated ? " sim" : ""}"><span class="dot"></span>${h != null ? `<span class="beam" style="transform:rotate(${h}deg)"></span>` : ""}</div>`;
  if (!meMarker) {
    meCircle = L.circle(ll, { radius: f.acc || 10, color: "#2f5d62", weight: 1, fillOpacity: 0.08, interactive: false }).addTo(map);
    meMarker = L.marker(ll, { icon: L.divIcon({ html, className: "me-wrap", iconSize: [40, 40], iconAnchor: [20, 20] }), interactive: false, zIndexOffset: 1000 }).addTo(map);
  } else {
    meMarker.setLatLng(ll); meMarker.setIcon(L.divIcon({ html, className: "me-wrap", iconSize: [40, 40], iconAnchor: [20, 20] }));
    meCircle.setLatLng(ll); meCircle.setRadius(f.acc || 10);
  }
}

function proximity(fix) {
  if ((fix.acc || 0) > 60) return;
  for (const g of GROUPS) {
    const key = g.items.map(i => i.id).join("|");
    if (announced.has(key) || g.items[0].kind === "birdseye") continue;
    if (dist(fix, g.at) < 35) {
      announced.add(key);
      const it = g.items[0];
      if (navigator.userActivation?.hasBeenActive) navigator.vibrate?.([60, 40, 60]);
      toast(`You're at ${({ detroit: "the photographer", stereo: "the photographer", birdseye: "the artist" })[it.artist] || esc(artist(it).name.split(" ").pop())}'s spot: <b>${esc(it.title)}</b>${g.items.length > 1 ? ` (+${g.items.length - 1} more)` : ""}
        <button class="pill" data-open="${esc(it.id)}">Open ghost view</button>`, 9000);
      return;
    }
  }
}

function focusOn(v, zoom) {
  const z = Math.max(map.getZoom(), zoom || 16);
  const desktop = matchMedia("(min-width: 900px)").matches;
  const p = map.project([v.lat, v.lon], z);
  const sheet = $("#sheet");
  const off = desktop ? L.point(-sheet.offsetWidth / 2, 0) : L.point(0, Math.min(sheet.offsetHeight, innerHeight * 0.6) / 2);
  map.setView(map.unproject(p.add(off), z), z, { animate: true });
}

/* ── sheet: list ──────────────────────────────────────────────── */
function chips() {
  const counts = {};
  const here = ITEMS.filter(inRegion);
  here.forEach(i => (counts[i.artist] = (counts[i.artist] || 0) + 1));
  const keys = Object.keys(DATA.artists).filter(k => counts[k]);
  const label = k => ({ detroit: "Detroit Publishing", birdseye: "Bird's-eye", stereo: "Stereoviews", soule: "Great Fire 1866" }[k] || DATA.artists[k].name.split(" ").pop());
  return `<div class="chips" role="tablist">
    <button class="chip${filter === "all" ? " on" : ""}" data-filter="all">All <small>${here.length}</small></button>
    ${keys.map(k => `<button class="chip${filter === k ? " on" : ""}" data-filter="${k}" style="--c:${DATA.artists[k].color}">${esc(label(k))} <small>${counts[k]}</small></button>`).join("")}
  </div>`;
}

function renderList() {
  selected = null;
  const fix = S.state.fix;
  let rows = ITEMS.filter(it => visible(it) && inRegion(it)).map(it => ({ it, d: fix ? dist(fix, it.vantage) : null }));
  if (fix) rows.sort((a, b) => a.d - b.d);
  const intro = fix
    ? `<p class="lede">Nearest first. Walk to a pin, face the way its cone points, and open the ghost view.</p>`
    : `<p class="lede">Painters and photographers who stood here. Each pin is where the easel or camera was; the cone is what they saw.</p>`;
  $("#sheetBody").innerHTML = `
    <div class="sheet-head"><h1>${esc(REGIONS[REGION].label)}, as they saw it</h1>${intro}${chips()}</div>
    <ol class="list">${rows.map(({ it, d }) => `
      <li><button class="row" data-id="${esc(it.id)}">
        ${thumbImg(it, 68 / 50)}
        <span class="txt"><b>${esc(it.title)}</b><span class="by" style="--c:${artist(it).color}">${esc(artist(it).name)} · ${esc(it.date)}</span></span>
        <span class="side">${d != null ? `<em>${fmtDist(d)}</em>` : ""}<i class="cdot conf-${it.vantage.confidence}" title="${it.vantage.confidence} vantage"></i></span>
      </button></li>`).join("")}</ol>
    <p class="foot">Images: Wikimedia Commons (public domain). <button class="linkish" id="switchRegion2">Switch to ${esc(REGIONS[Object.keys(REGIONS)[(Object.keys(REGIONS).indexOf(REGION) + 1) % Object.keys(REGIONS).length]].label)}</button> Vantage points: see each entry for its basis. <button class="linkish" id="openHelp2">How this works</button></p>`;
  drawMap();
}

/* ── sheet: detail ────────────────────────────────────────────── */
function select(it, { fly = true } = {}) {
  selected = it;
  if (REGIONS[it.region] && it.region !== REGION) setRegion(it.region);
  renderDetail(it);
  setSheet(matchMedia("(min-width: 900px)").matches ? "full" : "peek");
  drawMap();
  if (fly) focusOn(it.vantage, it.kind === "birdseye" ? 15 : 16);
  history.replaceState(null, "", `?item=${encodeURIComponent(it.id)}${params.get("sim") ? `&sim=${params.get("sim")}` : ""}`);
}

const CONF = {
  documented: ["Documented vantage", "from a published viewpoint map or catalogue note"],
  inferred: ["Inferred vantage", "worked out from the title and the lie of the land — not yet field-checked"],
  general: ["General area", "the right neighbourhood; the exact spot is unknown"],
};

function renderDetail(it) {
  const a = artist(it), v = it.vantage, img = it.image, loc = LOCAL[it.id];
  const group = it._group.items.filter(x => x !== it);
  const [cl, cdesc] = CONF[v.confidence] || CONF.general;
  const res = loc?.width ? `${loc.width.toLocaleString()} px · local copy` : img.approx ? "full size at the source" : `${img.width.toLocaleString()} × ${img.height.toLocaleString()} px`;
  const dir = v.heading != null ? `faces <b>${compass(v.heading)}</b> (${Math.round(v.heading)}°)${v.fov ? ` · about ${Math.round(v.fov)}° wide` : ""}` : (it.kind === "birdseye" ? "bird's-eye — no single direction" : "direction not yet worked out");
  const walk = `https://www.google.com/maps/dir/?api=1&destination=${v.lat},${v.lon}&travelmode=walking`;
  $("#sheetBody").innerHTML = `
    <article class="detail" style="--c:${a.color}">
      <button class="back" id="back">← All views</button>
      <figure class="hero" id="hero"><img src="${esc(imageUrl(it, "web"))}" alt="${esc(it.title)}" onerror="if(this.src!=='${esc(it._remote.web)}')this.src='${esc(it._remote.web)}'"><figcaption>Tap to zoom · ${res}${img.photo === "gallery" ? " · photographed in the gallery" : ""}</figcaption></figure>
      <h2>${esc(it.title)}</h2>
      <p class="meta"><span class="artist">${esc(a.name)}</span> <span class="life">${esc(a.life)}</span><br>${esc(it.date)} · ${esc(it.medium)}<br><span class="coll">${esc(it.collection)}</span></p>
      <div class="actions">
        ${it.kind === "birdseye" ? "" : `<button class="btn primary" data-act="ghost">Ghost view</button><button class="btn" data-act="photo">Photo match</button>`}
        <a class="btn" href="${walk}" target="_blank" rel="noopener">Walk there</a>
        <button class="btn" data-act="zoom">High-res</button>
      </div>
      <p class="where" id="where"></p>
      <div class="conf-box conf-${v.confidence}"><b>${cl}</b>${it.calibrated ? ' <span class="cal">· field-calibrated ✓</span>' : ""}<br><span>${esc(cdesc)}.</span><br><small>Basis: ${esc(v.basis)}</small></div>
      <p class="note">${esc(v.note)}</p>
      <p class="dir">${dir}${v.access === "water" ? " · painted from the water" : v.access === "private-view" ? " · exact spot is private ground" : ""}</p>
      ${it.blurb ? `<p class="blurb">${esc(it.blurb)}</p>` : ""}
      ${group.length ? `<div class="stack"><h3>Also from this spot</h3>${group.map(g => `<button class="row mini" data-id="${esc(g.id)}">${thumbImg(g, 56 / 42)}<span class="txt"><b>${esc(g.title)}</b><span class="by" style="--c:${artist(g).color}">${esc(artist(g).name)} · ${esc(g.date)}</span></span></button>`).join("")}</div>` : ""}
      <dl class="facts">
        <dt>Rights</dt><dd>${esc(it.rights)}</dd>
        <dt>Image</dt><dd>${esc(img.commons)}${img.best ? ` <small>(fetch_art.py will try the ${esc(img.best.source.toUpperCase())} original first)</small>` : ""}</dd>
      </dl>
      <p class="links">${it.links.map(l => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)} ↗</a>`).join(" ")}</p>
    </article>`;
  refreshWhere();
  $("#sheetBody").scrollTop = 0;
}

function refreshWhere() {
  const el = $("#where"); if (!el || !selected) return;
  const f = S.state.fix;
  if (!f) { el.textContent = window.isSecureContext ? "" : ""; return; }
  const d = dist(f, selected.vantage);
  el.innerHTML = d < Math.max(12, f.acc || 0)
    ? `<b>You're on the spot.</b>`
    : `<b>${fmtDist(d)}</b> away, to the ${compass(bearing(f, selected.vantage))}${f.simulated ? " (simulated location)" : ""}`;
}

/* ── actions ──────────────────────────────────────────────────── */
async function startGhost(it) {
  const p = S.startCompass();   // must start inside the tap for iOS
  S.startGeo();
  await p;
  openAR(it);
}
let photoTarget = null, arOpenForPhoto = false;
function pickPhoto(it, useCamera) {
  photoTarget = it;
  arOpenForPhoto = !$("#ar").hidden;
  S.startCompass(); S.startGeo();
  (useCamera ? $("#fileCapture") : $("#fileChoose")).click();
}
function onPhotoChosen(e) {
  const file = e.target.files?.[0]; e.target.value = "";
  if (!file || !photoTarget) return;
  const url = URL.createObjectURL(file);
  if (arOpenForPhoto) loadStill(url); else openAR(photoTarget, { still: url });
}

function zoomImage(it) {
  const loc = LOCAL[it.id], a = artist(it);
  openViewer({
    src: imageUrl(it, "full"), fallback: it._remote.full,
    caption: `<b>${esc(it.title)}</b> — ${esc(a.name)}, ${esc(it.date)}`,
    original: loc?.original || it.image.original,
    originalLabel: loc?.original ? "Original (local)" : `Original ${it.image.commons ? "on Commons" : "at the museum"}${it.image.approx ? "" : ` (${it.image.width.toLocaleString()} px)`}`,
  });
}

/* ── chrome ───────────────────────────────────────────────────── */
function setSheet(state) { $("#sheet").dataset.state = state; document.body.dataset.sheet = state; setTimeout(() => map.invalidateSize(), 260); }

function bindUI() {
  $("#sheetBody").addEventListener("click", e => {
    const t = e.target;
    const chip = t.closest("[data-filter]");
    if (chip) { filter = chip.dataset.filter; renderList(); return; }
    const row = t.closest(".row[data-id]");
    if (row) { select(ITEMS.find(i => i.id === row.dataset.id)); return; }
    if (t.closest("#back")) { renderList(); history.replaceState(null, "", location.pathname + (params.get("sim") ? `?sim=${params.get("sim")}` : "")); return; }
    if (t.closest("#hero") || t.closest('[data-act="zoom"]')) { zoomImage(selected); return; }
    if (t.closest('[data-act="ghost"]')) { startGhost(selected); return; }
    if (t.closest('[data-act="photo"]')) { pickPhoto(selected, true); return; }
    if (t.closest("#openHelp2")) { $("#help").showModal(); }
    if (t.closest("#switchRegion2")) { nextRegion(); }
  });
  $("#grab").addEventListener("click", () => {
    const s = $("#sheet").dataset.state;
    setSheet(s === "peek" ? "full" : s === "full" ? "mini" : "peek");
  });
  let y0 = null;
  $("#grab").addEventListener("touchstart", e => (y0 = e.touches[0].clientY), { passive: true });
  $("#grab").addEventListener("touchend", e => {
    if (y0 == null) return; const dy = e.changedTouches[0].clientY - y0; y0 = null;
    const s = $("#sheet").dataset.state;
    if (dy < -40) setSheet(s === "mini" ? "peek" : "full");
    if (dy > 40) setSheet(s === "full" ? "peek" : "mini");
  });
  $("#btnRegion")?.addEventListener("click", nextRegion);
  $("#btnLocate").addEventListener("click", async () => {
    if (!window.isSecureContext && !S.state.simulated) { showBanner(true); return; }
    S.startGeo(); S.startCompass();
    const f = S.state.fix;
    if (f) map.setView([f.lat, f.lon], Math.max(map.getZoom(), 16));
    else toast(S.state.geoError || "Finding you…", 2500);
  });
  $("#btnHelp").addEventListener("click", () => $("#help").showModal());
  $("#helpClose").addEventListener("click", () => $("#help").close());
  $("#helpExport").addEventListener("click", () => { const n = exportCalibrations(SERVER_CALS); toast(`Exported ${n} calibration${n === 1 ? "" : "s"}`, 2500); });
  $("#fileCapture").addEventListener("change", onPhotoChosen);
  $("#fileChoose").addEventListener("change", onPhotoChosen);
  $("#toast").addEventListener("click", e => {
    const id = e.target.dataset?.open;
    if (id) { const it = ITEMS.find(i => i.id === id); $("#toast").hidden = true; select(it); startGhost(it); }
  });
}

function toast(html, ms = 4000) {
  const t = $("#toast"); t.innerHTML = html; t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), ms);
}
function showBanner(force) {
  const b = $("#banner");
  let dismissed = false;
  try { dismissed = sessionStorage.getItem("vantage.banner") === "1"; } catch { /* storage blocked */ }
  if (dismissed && !force) return;
  b.innerHTML = `<b>Plain HTTP:</b> the browser blocks the camera, GPS and compass on this address. <b>Photo match</b> and the map still work. For the live ghost view open the HTTPS address (see <i>How this works</i>), or long-press the map to simulate a location. <button class="x" aria-label="Dismiss">✕</button>`;
  b.hidden = false;
  b.querySelector(".x").onclick = () => { b.hidden = true; try { sessionStorage.setItem("vantage.banner", "1"); } catch { /* ignore */ } };
}

boot().catch(err => {
  console.error(err);
  document.body.insertAdjacentHTML("beforeend", `<div class="fatal">Couldn't load the catalogue: ${esc(err.message)}</div>`);
});

// thumbnails: retry once (Wikimedia can answer 429 when many load at once), then hide
window.vantageImgRetry = img => {
  const remote = img.dataset.remote;
  if (remote && !img.src.startsWith(remote.split("?")[0])) { img.src = remote; return; }   // local copy missing → Commons
  if (img.dataset.retry) { img.style.visibility = "hidden"; return; }
  img.dataset.retry = "1";
  setTimeout(() => { img.src = img.src + (img.src.includes("?") ? "&" : "?") + "retry=1"; }, 1200 + Math.random() * 1500);
};

// handy from the console while testing
window.vantage = { S, get items() { return ITEMS; }, select: id => select(ITEMS.find(i => i.id === id)) };
