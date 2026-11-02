// viewer.js — full-screen pinch/scroll zoom for the high-resolution image
const $ = s => document.querySelector(s);
let E, z = { s: 1, x: 0, y: 0 }, fit = 1;

export function initViewer() {
  E = { root: $("#viewer"), img: $("#vImg"), cap: $("#vCap"), stage: $("#vStage"), dl: $("#vDownload"), info: $("#vInfo") };
  $("#vClose").addEventListener("click", closeViewer);
  addEventListener("keydown", e => { if (e.key === "Escape" && !E.root.hidden) closeViewer(); });
  const pts = new Map(); let base = null;
  const rebase = () => (base = { z: { ...z }, arr: [...pts.values()].map(p => ({ ...p })) });
  E.stage.addEventListener("pointerdown", e => { E.stage.setPointerCapture(e.pointerId); pts.set(e.pointerId, { x: e.clientX, y: e.clientY }); rebase(); });
  const up = e => { if (pts.delete(e.pointerId)) rebase(); };
  E.stage.addEventListener("pointerup", up); E.stage.addEventListener("pointercancel", up);
  E.stage.addEventListener("pointermove", e => {
    if (!pts.has(e.pointerId) || !base) return;
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const now = [...pts.values()];
    if (now.length === 1 || base.arr.length === 1) {
      z.x = base.z.x + now[0].x - base.arr[0].x; z.y = base.z.y + now[0].y - base.arr[0].y;
    } else {
      const [a0, b0] = base.arr, [a, b] = now;
      const k = Math.hypot(b.x - a.x, b.y - a.y) / (Math.hypot(b0.x - a0.x, b0.y - a0.y) || 1);
      const m0 = { x: (a0.x + b0.x) / 2, y: (a0.y + b0.y) / 2 }, m = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      zoomAt(base.z, k, m0, m);
    }
    apply();
  });
  E.stage.addEventListener("wheel", e => {
    e.preventDefault();
    const p = { x: e.clientX, y: e.clientY };
    zoomAt({ ...z }, e.deltaY > 0 ? 0.88 : 1.14, p, p); apply();
  }, { passive: false });
  E.stage.addEventListener("dblclick", e => { const p = { x: e.clientX, y: e.clientY }; zoomAt({ ...z }, z.s > fit * 1.5 ? fit / z.s : 2.5, p, p); apply(); });
  E.img.addEventListener("load", reset);
}

function zoomAt(b, k, m0, m) {
  const s = Math.min(Math.max(b.s * k, fit * 0.5), 12);
  const r = s / b.s;
  z.s = s; z.x = m.x - (m0.x - b.x) * r; z.y = m.y - (m0.y - b.y) * r;
}
function apply() { E.img.style.transform = `translate(${z.x}px, ${z.y}px) scale(${z.s})`; }
function reset() {
  const W = E.stage.clientWidth, H = E.stage.clientHeight, iw = E.img.naturalWidth, ih = E.img.naturalHeight;
  fit = Math.min(W / iw, H / ih);
  z = { s: fit, x: (W - iw * fit) / 2, y: (H - ih * fit) / 2 };
  apply();
  E.info.textContent = `${iw.toLocaleString()} × ${ih.toLocaleString()} px shown`;
}

export function openViewer({ src, fallback, caption, original, originalLabel }) {
  E.root.hidden = false;
  E.cap.innerHTML = caption;
  E.img.onerror = () => { if (fallback && E.img.src !== fallback) E.img.src = fallback; };
  E.img.src = src;
  E.dl.href = original; E.dl.textContent = originalLabel || "Original file";
}
export function closeViewer() { E.root.hidden = true; E.img.removeAttribute("src"); }
