// ar.js — "ghost" overlay of a painting on the live camera (or on a still photo)
import { angDiff, bearing, dist, fmtDist, compass } from "./geo.js";
import * as S from "./sensors.js";
import { prefs, savePrefs, calibrations, saveCalibration, clearCalibration, exportCalibrations } from "./store.js";

const $ = s => document.querySelector(s);
const rad = d => (d * Math.PI) / 180;
const deg = r => (r * 180) / Math.PI;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

let ctx = null;            // { imageUrl(item, size), serverCals, onCalibrated(item) }
let E = {};                // DOM refs
let item = null;
let mode = "ghost";        // ghost | swipe
let bg = "live";           // live | still
let stream = null;
let st = { cx: 0, cy: 0, w: 0.8, rot: 0 };   // overlay centre (fraction of W/H from screen centre), width (fraction of W), rotation
let split = 0.5;
let crop = [0, 0, 0, 0];
let unsub = [];
let raf = 0;
let stillUrl = null;
let stillFit = "cover";      // a frozen camera frame keeps the live framing; a chosen photo is shown whole

export function initAR(context) {
  ctx = context;
  E = {
    root: $("#ar"), video: $("#arVideo"), still: $("#arStill"), clip: $("#arClip"), ghost: $("#arGhost"), img: $("#arImg"),
    split: $("#arSplit"), title: $("#arTitle"), sub: $("#arSub"), dist: $("#arDist"), turn: $("#arTurn"), mark: $("#tapeMark"),
    arrow: $("#arArrow"), opacity: $("#arOpacity"), msg: $("#arMsg"), drawer: $("#arDrawer"), freeze: $("#arFreeze"),
    calStatus: $("#calStatus"), camFov: $("#camFov"), fovOut: $("#fovOut"), track: $("#track"), hint: $("#arHint"),
  };
  E.opacity.value = prefs.opacity;
  E.opacity.addEventListener("input", () => { prefs.opacity = +E.opacity.value; savePrefs(); render(); });
  $("#arClose").addEventListener("click", closeAR);
  $("#arMode").addEventListener("click", e => {
    const b = e.target.closest("button[data-mode]"); if (!b) return;
    mode = b.dataset.mode;
    $("#arMode").querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b));
    render();
  });
  $("#arFit").addEventListener("click", () => { fitDefault(); render(); });
  E.freeze.addEventListener("click", toggleFreeze);
  $("#arShutter").addEventListener("click", capture);
  $("#arCal").addEventListener("click", () => { E.drawer.hidden = !E.drawer.hidden; updateCalStatus(); });
  $("#calClose").addEventListener("click", () => (E.drawer.hidden = true));
  E.camFov.value = prefs.camFov; E.fovOut.textContent = `${prefs.camFov}°`;
  E.camFov.addEventListener("input", () => { prefs.camFov = +E.camFov.value; E.fovOut.textContent = `${prefs.camFov}°`; savePrefs(); render(); });
  E.track.checked = prefs.track;
  E.track.addEventListener("change", () => { prefs.track = E.track.checked; savePrefs(); render(); });
  document.querySelectorAll("#cropRow input").forEach((inp, i) =>
    inp.addEventListener("input", () => { crop[i] = +inp.value / 100; render(); }));
  $("#calSave").addEventListener("click", saveCal);
  $("#calReset").addEventListener("click", () => {
    clearCalibration(item.id); crop = [...(item.image.crop || [0, 0, 0, 0])]; syncCropInputs(); fitDefault(); render(); updateCalStatus("Calibration cleared for this view.");
    ctx.onCalibrated?.(item);
  });
  $("#calExport").addEventListener("click", () => {
    const n = exportCalibrations(ctx.serverCals());
    updateCalStatus(`Exported ${n} calibration${n === 1 ? "" : "s"} → calibrations.json`);
  });
  $("#arPhoto").addEventListener("click", () => ctx.pickPhoto?.(item, true));
  bindSplit();
  bindGestures();
  addEventListener("resize", () => { if (!E.root.hidden) render(); });
}

/* ── open / close ──────────────────────────────────────────────── */
export async function openAR(it, { still = null } = {}) {
  item = it;
  E.root.hidden = false;
  document.body.classList.add("ar-open");
  E.drawer.hidden = true;
  E.msg.hidden = true;
  E.title.textContent = it.title;
  const a = ctx.artist(it);
  E.sub.textContent = `${a.name} · ${it.date}`;
  const cal = calibrations[it.id] || ctx.serverCals()[it.id];
  crop = [...(cal?.crop || it.image.crop || [0, 0, 0, 0])];
  syncCropInputs();
  E.img.crossOrigin = "anonymous";
  E.img.onload = () => { if (!cal?.overlay) fitDefault(); render(); };
  E.img.onerror = () => { if (E.img.dataset.fallback !== "1" && it._remote?.web && E.img.src !== it._remote.web) { E.img.dataset.fallback = "1"; E.img.src = it._remote.web; } };
  E.img.dataset.fallback = "0";
  E.img.src = ctx.imageUrl(it, "web");
  st = cal?.overlay ? { ...cal.overlay } : { cx: 0, cy: 0, w: 0.8, rot: 0 };
  if (still) setStill(still, "contain"); else await startCamera();
  unsub.push(S.on("heading", schedule), S.on("fix", schedule));
  schedule();
}

export function closeAR() {
  stopCamera();
  unsub.forEach(f => f()); unsub = [];
  E.root.hidden = true;
  document.body.classList.remove("ar-open");
  if (stillUrl) { URL.revokeObjectURL(stillUrl); stillUrl = null; }
  E.still.removeAttribute("src");
}

async function startCamera() {
  bg = "live";
  E.still.hidden = true; E.video.hidden = false;
  E.freeze.textContent = "Hold";
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    return showMsg("The live camera needs this page served over HTTPS. Use <b>Photo match</b> instead — snap a picture and line the painting up on it.", true);
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } } });
    const refit = () => { if (!calibrations[item?.id]?.overlay && !ctx.serverCals()[item?.id]?.overlay) fitDefault(); render(); };
    E.video.onloadedmetadata = refit;
    E.video.srcObject = stream;
    await E.video.play().catch(() => {});
    if (E.video.videoWidth) refit();
  } catch (err) {
    showMsg(`Camera unavailable (${err.name || err.message}). Try <b>Photo match</b> instead.`, true);
  }
}
function stopCamera() {
  if (stream) stream.getTracks().forEach(t => t.stop());
  stream = null; E.video.srcObject = null;
}
function setStill(url, fit = "cover") {
  bg = "still";
  stillFit = fit;
  E.still.classList.toggle("contain", fit === "contain");
  stopCamera();
  E.video.hidden = true; E.still.hidden = false;
  if (stillUrl && stillUrl !== url) URL.revokeObjectURL(stillUrl);
  stillUrl = url.startsWith("blob:") ? url : null;
  E.still.onload = () => { if (!calibrations[item?.id]?.overlay && !ctx.serverCals()[item?.id]?.overlay) fitDefault(); render(); };
  E.still.src = url;
  E.freeze.textContent = stream === null && E.video.srcObject === null && window.isSecureContext ? "Live" : "Hold";
}
function toggleFreeze() {
  if (bg === "live") {
    if (!E.video.videoWidth) return;
    const c = document.createElement("canvas");
    c.width = E.video.videoWidth; c.height = E.video.videoHeight;
    c.getContext("2d").drawImage(E.video, 0, 0);
    c.toBlob(b => { setStill(URL.createObjectURL(b), "cover"); E.freeze.textContent = "Live"; }, "image/jpeg", 0.92);
  } else {
    startCamera();
  }
}
function showMsg(html, withPhoto) {
  E.msg.innerHTML = `<p>${html}</p>${withPhoto ? '<button class="pill" data-act="photo">Take a photo</button> <button class="pill ghost" data-act="choose">Choose a photo</button>' : ""}`;
  E.msg.hidden = false;
  E.msg.onclick = e => {
    const act = e.target.dataset.act;
    if (act === "photo") ctx.pickPhoto?.(item, true);
    if (act === "choose") ctx.pickPhoto?.(item, false);
  };
}
export function loadStill(url) { E.msg.hidden = true; setStill(url, "contain"); }

/* ── geometry ──────────────────────────────────────────────────── */
function source() {
  if (bg === "live" && E.video.videoWidth) return { el: E.video, w: E.video.videoWidth, h: E.video.videoHeight };
  if (bg === "still" && E.still.naturalWidth) return { el: E.still, w: E.still.naturalWidth, h: E.still.naturalHeight, contain: stillFit === "contain" };
  const W = innerWidth, H = innerHeight;   // guess a 4:3 sensor in the screen's orientation
  return W >= H ? { el: null, w: 4, h: 3 } : { el: null, w: 3, h: 4 };
}
/** horizontal field of view actually visible on screen (deg) */
function visHFov() {
  const W = innerWidth, H = innerHeight, s = source();
  const long = rad(prefs.camFov);
  const hv = s.w >= s.h ? long : 2 * Math.atan(Math.tan(long / 2) * (s.w / s.h));
  const scale = s.contain ? Math.min(W / s.w, H / s.h) : Math.max(W / s.w, H / s.h);   // object-fit
  const visibleW = W / scale;
  return deg(2 * Math.atan(Math.tan(hv / 2) * (visibleW / s.w)));
}
function aspect() {
  const n = E.img.naturalWidth ? E.img : null;
  const w = n ? n.naturalWidth : item.image.width, h = n ? n.naturalHeight : item.image.height;
  return (h * (1 - crop[1] - crop[3])) / (w * (1 - crop[0] - crop[2]));
}
function fitDefault() {
  const fov = item?.vantage?.fov;
  const vis = visHFov();
  const w = fov ? Math.tan(rad(Math.min(fov, 170) / 2)) / Math.tan(rad(vis / 2)) : 0.9;
  st.w = clamp(w, 0.2, 8);
  st.cx = 0; st.rot = 0;
  // put the picture's horizon on the real horizon (screen centre when the phone is level)
  const horizon = item.vantage.horizon ?? (item.kind === "photograph" ? 0.5 : 0.62);
  const hPx = st.w * innerWidth * aspect();
  st.cy = -((horizon - 0.5) * hPx) / innerHeight;
  E.hint.textContent = st.w > 1.6 ? "Wide view — turn your phone sideways or step back" : "";
}
function trackOffset() {
  if (!prefs.track || S.state.heading == null || item?.vantage?.heading == null) return { x: 0, y: 0 };
  const vis = rad(visHFov());
  const diff = clamp(angDiff(S.state.heading, item.vantage.heading), -75, 75);
  const x = (0.5 * Math.tan(rad(diff))) / Math.tan(vis / 2);
  let y = 0;
  if (S.state.pitch != null) {
    const visV = 2 * Math.atan(Math.tan(vis / 2) * (innerHeight / innerWidth));
    y = (0.5 * Math.tan(rad(clamp(S.state.pitch, -60, 60)))) / Math.tan(visV / 2);
  }
  return { x, y };
}
function displayed() {
  const W = innerWidth, H = innerHeight, tr = trackOffset();
  const w = st.w * W, h = w * aspect();
  return { x: W / 2 + (st.cx + tr.x) * W, y: H / 2 + (st.cy + tr.y) * H, w, h, rot: st.rot };
}

/* ── render ────────────────────────────────────────────────────── */
function schedule() { if (!raf) raf = requestAnimationFrame(() => { raf = 0; render(); }); }
function render() {
  if (!item || E.root.hidden) return;
  const d = displayed();
  E.ghost.style.width = `${d.w}px`;
  E.ghost.style.height = `${d.h}px`;
  E.ghost.style.transform = `translate(${d.x - d.w / 2}px, ${d.y - d.h / 2}px) rotate(${d.rot}deg)`;
  const [l, t, r, b] = crop;
  const iw = d.w / (1 - l - r), ih = d.h / (1 - t - b);
  E.img.style.width = `${iw}px`; E.img.style.height = `${ih}px`;
  E.img.style.transform = `translate(${-l * iw}px, ${-t * ih}px)`;
  E.ghost.style.opacity = mode === "swipe" ? 1 : prefs.opacity / 100;
  E.clip.style.clipPath = mode === "swipe" ? `inset(0 ${(1 - split) * 100}% 0 0)` : "none";
  E.split.hidden = mode !== "swipe";
  E.split.style.left = `${split * 100}%`;
  E.opacity.disabled = mode === "swipe";
  guide();
}

function guide() {
  const v = item.vantage, fix = S.state.fix, hdg = S.state.heading;
  // distance to the easel spot
  if (fix) {
    const d = dist(fix, v), b = bearing(fix, v);
    if (d <= Math.max(10, fix.acc || 0)) { E.dist.textContent = "You're on the spot"; E.arrow.style.visibility = "hidden"; }
    else {
      E.dist.textContent = `${fmtDist(d)} to the spot · ${compass(b)}`;
      E.arrow.style.visibility = hdg == null ? "hidden" : "visible";
      if (hdg != null) E.arrow.style.transform = `rotate(${angDiff(hdg, b)}deg)`;
    }
  } else {
    E.dist.textContent = S.state.geoError ? "No GPS fix" : "Finding you…";
    E.arrow.style.visibility = "hidden";
  }
  // which way to face
  if (v.heading == null) { E.turn.textContent = item.kind === "birdseye" ? "Aerial view — no single direction" : "Direction not known yet — find it and save a calibration"; E.mark.style.left = "50%"; return; }
  if (hdg == null) {
    E.turn.textContent = `Face ${compass(v.heading)} (${Math.round(v.heading)}°)`;
    E.mark.style.left = "50%"; E.mark.classList.add("idle");
  } else {
    const diff = angDiff(hdg, v.heading), a = Math.abs(Math.round(diff));
    const who = item.kind === "photograph" ? "the photographer" : ctx.artist(item).name.split(" ").pop();
    E.turn.textContent = a <= 4 ? `Facing ${who}'s view ✓` : `Turn ${a}° ${diff > 0 ? "right" : "left"}`;
    E.mark.classList.remove("idle");
    E.mark.style.left = `${50 + (clamp(diff, -60, 60) / 60) * 46}%`;
  }
}

/* ── gestures ──────────────────────────────────────────────────── */
function bindGestures() {
  const pts = new Map();
  let base = null;
  // tap tracking: only a quick, still, single-finger touch counts toward a double-tap reset.
  // (Lifting two fingers after a pinch sends two pointerups a few ms apart — that is NOT a double-tap.)
  let touch = null, lastTap = null;
  const rebase = () => {
    const arr = [...pts.values()];
    base = { st: { ...st }, arr: arr.map(p => ({ ...p })), center: displayed() };
  };
  E.root.addEventListener("pointerdown", e => {
    if (e.target.closest(".ar-ui") || e.target === E.split || E.split.contains(e.target)) return;
    E.root.setPointerCapture(e.pointerId);
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pts.size === 1) touch = { t: Date.now(), x: e.clientX, y: e.clientY, moved: 0, multi: false };
    else if (touch) touch.multi = true;
    rebase();
  });
  const up = e => {
    if (!pts.delete(e.pointerId)) return;
    rebase();
    if (pts.size || !touch) return;
    const g = touch; touch = null;
    const isTap = e.type === "pointerup" && !g.multi && g.moved < 12 && Date.now() - g.t < 300;
    if (!isTap) { lastTap = null; return; }
    if (lastTap && Date.now() - lastTap.t < 350 && Math.hypot(e.clientX - lastTap.x, e.clientY - lastTap.y) < 40) {
      lastTap = null; fitDefault(); schedule();
    } else lastTap = { t: Date.now(), x: e.clientX, y: e.clientY };
  };
  E.root.addEventListener("pointerup", up);
  E.root.addEventListener("pointercancel", up);
  E.root.addEventListener("pointermove", e => {
    if (!pts.has(e.pointerId) || !base) return;
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (touch) touch.moved = Math.max(touch.moved, Math.hypot(e.clientX - touch.x, e.clientY - touch.y));
    const W = innerWidth, H = innerHeight, now = [...pts.values()];
    if (now.length === 1 || base.arr.length === 1) {
      const p = now[0], p0 = base.arr[0];
      st.cx = base.st.cx + (p.x - p0.x) / W;
      st.cy = base.st.cy + (p.y - p0.y) / H;
    } else {
      const [a0, b0] = base.arr, [a, b] = now;
      const d0 = Math.hypot(b0.x - a0.x, b0.y - a0.y) || 1, d1 = Math.hypot(b.x - a.x, b.y - a.y);
      const s = d1 / d0;
      const ang = Math.atan2(b.y - a.y, b.x - a.x) - Math.atan2(b0.y - a0.y, b0.x - a0.x);
      const m0 = { x: (a0.x + b0.x) / 2, y: (a0.y + b0.y) / 2 }, m = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      const c0 = base.center, vx = (c0.x - m0.x) * s, vy = (c0.y - m0.y) * s;
      const nx = m.x + vx * Math.cos(ang) - vy * Math.sin(ang), ny = m.y + vx * Math.sin(ang) + vy * Math.cos(ang);
      st.w = clamp(base.st.w * s, 0.05, 12);
      st.rot = base.st.rot + deg(ang);
      st.cx = base.st.cx + (nx - c0.x) / W;
      st.cy = base.st.cy + (ny - c0.y) / H;
    }
    schedule();
  });
  // mouse wheel = zoom (desk testing), shift+wheel = rotate
  E.root.addEventListener("wheel", e => {
    if (e.target.closest(".ar-ui")) return;
    e.preventDefault();
    if (e.shiftKey) st.rot += e.deltaY > 0 ? 0.5 : -0.5;
    else st.w = clamp(st.w * (e.deltaY > 0 ? 0.97 : 1.03), 0.05, 12);
    schedule();
  }, { passive: false });
  // iOS Safari: stop its own pinch-zoom/rotate gestures from fighting ours
  ["gesturestart", "gesturechange", "gestureend"].forEach(t => E.root.addEventListener(t, e => e.preventDefault()));
}
function bindSplit() {
  let dragging = false;
  E.split.addEventListener("pointerdown", e => { dragging = true; E.split.setPointerCapture(e.pointerId); e.stopPropagation(); });
  E.split.addEventListener("pointermove", e => { if (dragging) { split = clamp(e.clientX / innerWidth, 0, 1); schedule(); } });
  const end = () => (dragging = false);
  E.split.addEventListener("pointerup", end);
  E.split.addEventListener("pointercancel", end);
}

/* ── calibration ───────────────────────────────────────────────── */
function syncCropInputs() {
  document.querySelectorAll("#cropRow input").forEach((inp, i) => (inp.value = Math.round((crop[i] || 0) * 100)));
}
function updateCalStatus(extra = "") {
  const fix = S.state.fix, hdg = S.state.heading, cal = calibrations[item.id];
  const parts = [];
  parts.push(fix ? `GPS ${fix.lat.toFixed(5)}, ${fix.lon.toFixed(5)} ±${Math.round(fix.acc || 0)} m${fix.simulated ? " (simulated)" : ""}` : "No GPS fix yet");
  parts.push(hdg != null ? `heading ${Math.round(hdg)}° true` : "no compass");
  if (cal) parts.push(`saved ${new Date(cal.updated).toLocaleString()}`);
  E.calStatus.innerHTML = parts.join(" · ") + (extra ? `<br><b>${extra}</b>` : "");
}
function saveCal() {
  const fix = S.state.fix, hdg = S.state.heading, vis = visHFov();
  const d = displayed(), W = innerWidth;
  const cal = { overlay: { ...st }, crop: [...crop], camFov: prefs.camFov, screen: [innerWidth, innerHeight] };
  if (fix) Object.assign(cal, { lat: +fix.lat.toFixed(6), lon: +fix.lon.toFixed(6), acc: Math.round(fix.acc || 0) });
  // the painting's measured angular width and centre bearing, from how it lines up on screen
  cal.fov = Math.round(2 * deg(Math.atan(st.w * Math.tan(rad(vis / 2)))) * 10) / 10;
  if (hdg != null) {
    const off = deg(Math.atan(((d.x - W / 2) / (W / 2)) * Math.tan(rad(vis / 2))));
    cal.heading = Math.round(((hdg + off) % 360 + 360) % 360);
    // with compass tracking on, the horizontal position is now carried by the saved bearing
    if (prefs.track) cal.overlay.cx = 0;
  }
  saveCalibration(item.id, cal);
  ctx.onCalibrated?.(item);
  updateCalStatus(`Saved. ${fix ? "Spot" : "Alignment"}${hdg != null ? ", bearing" : ""} and ${cal.fov}° width recorded.`);
}

/* ── capture ───────────────────────────────────────────────────── */
async function capture() {
  const W = innerWidth, H = innerHeight, dpr = Math.min(2, devicePixelRatio || 1);
  const c = document.createElement("canvas");
  c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
  const g = c.getContext("2d");
  g.scale(dpr, dpr);
  g.fillStyle = "#111"; g.fillRect(0, 0, W, H);
  const s = source();
  if (s.el) {
    const k = s.contain ? Math.min(W / s.w, H / s.h) : Math.max(W / s.w, H / s.h), dw = s.w * k, dh = s.h * k;
    g.drawImage(s.el, (W - dw) / 2, (H - dh) / 2, dw, dh);
  }
  if (E.img.naturalWidth) {
    const d = displayed(), iw = E.img.naturalWidth, ih = E.img.naturalHeight, [l, t, r, b] = crop;
    g.save();
    if (mode === "swipe") { g.beginPath(); g.rect(0, 0, split * W, H); g.clip(); }
    g.globalAlpha = mode === "swipe" ? 1 : prefs.opacity / 100;
    g.translate(d.x, d.y); g.rotate(rad(d.rot));
    g.drawImage(E.img, l * iw, t * ih, iw * (1 - l - r), ih * (1 - t - b), -d.w / 2, -d.h / 2, d.w, d.h);
    g.restore();
  }
  // caption
  const a = ctx.artist(item);
  g.fillStyle = "rgba(15,18,20,.62)"; g.fillRect(0, H - 34, W, 34);
  g.fillStyle = "#f4efe4"; g.font = "15px Spectral, Georgia, serif"; g.textBaseline = "middle";
  g.fillText(`${item.title} — ${a.name}, ${item.date}  ·  then & now`, 12, H - 17, W - 24);
  let blob;
  try { blob = await new Promise((res, rej) => c.toBlob(b => (b ? res(b) : rej(new Error("empty"))), "image/jpeg", 0.92)); }
  catch { return flash("Couldn't export — the image host blocked it."); }
  const file = new File([blob], `vantage-${item.id}.jpg`, { type: "image/jpeg" });
  if (navigator.canShare && navigator.canShare({ files: [file] })) {
    try { await navigator.share({ files: [file], title: item.title }); return; } catch { /* cancelled or unsupported */ }
  }
  const url = URL.createObjectURL(blob), aEl = document.createElement("a");
  aEl.href = url; aEl.download = file.name; document.body.appendChild(aEl); aEl.click(); aEl.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
  flash("Saved then-&-now image");
}
function flash(text) {
  const f = $("#arFlash"); f.textContent = text; f.hidden = false;
  clearTimeout(flash.t); flash.t = setTimeout(() => (f.hidden = true), 2200);
}

export const _debug = { get st() { return st; }, displayed, visHFov, get mode() { return mode; } };
