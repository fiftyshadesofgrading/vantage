// sensors.js — GPS fix + compass/pitch, with a simulated position for desk testing
import { norm360, smoothAngle } from "./geo.js";
import { prefs } from "./store.js";

const listeners = { fix: new Set(), heading: new Set() };
export const state = { fix: null, heading: null, pitch: null, headingSource: null, simulated: false, geoError: null };

export function on(type, fn) { listeners[type].add(fn); return () => listeners[type].delete(fn); }
const emit = (type, v) => listeners[type].forEach(fn => { try { fn(v); } catch (e) { console.error(e); } });

/* ── GPS ─────────────────────────────────────────────────────────── */
let watchId = null;
export function startGeo() {
  if (state.simulated || watchId != null) return true;
  if (!("geolocation" in navigator)) { state.geoError = "This browser has no geolocation."; return false; }
  if (!window.isSecureContext) { state.geoError = "GPS needs HTTPS (or localhost)."; return false; }
  watchId = navigator.geolocation.watchPosition(
    p => {
      state.geoError = null;
      state.fix = { lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy, t: p.timestamp };
      emit("fix", state.fix);
    },
    err => { state.geoError = err.message || "Location unavailable"; emit("fix", null); },
    { enableHighAccuracy: true, maximumAge: 2000, timeout: 20000 }
  );
  return true;
}

export function simulate(lat, lon) {
  if (watchId != null) { navigator.geolocation.clearWatch(watchId); watchId = null; }
  state.simulated = true;
  state.fix = { lat, lon, acc: 5, t: Date.now(), simulated: true };
  emit("fix", state.fix);
}
export function stopSimulating() { state.simulated = false; state.fix = null; startGeo(); emit("fix", state.fix); }

/* ── Compass ─────────────────────────────────────────────────────── */
let compassOn = false;

/** Must be called from a user gesture on iOS. Resolves true when a heading source is attached. */
export async function startCompass() {
  if (compassOn) return true;
  if (!window.isSecureContext) return false;
  const DOE = window.DeviceOrientationEvent;
  if (!DOE) return false;
  if (typeof DOE.requestPermission === "function") {
    try { if ((await DOE.requestPermission()) !== "granted") return false; } catch { return false; }
  }
  const handler = e => onOrientation(e);
  if ("ondeviceorientationabsolute" in window) window.addEventListener("deviceorientationabsolute", handler, true);
  window.addEventListener("deviceorientation", handler, true);
  compassOn = true;
  return true;
}

const rad = d => (d * Math.PI) / 180;
function onOrientation(e) {
  const { alpha, beta, gamma } = e;
  let mag = null, src = null;
  if (typeof e.webkitCompassHeading === "number" && !isNaN(e.webkitCompassHeading)) {
    // iOS: already the direction the camera faces, magnetic
    const so = (screen.orientation && screen.orientation.angle) || window.orientation || 0;
    mag = norm360(e.webkitCompassHeading + so);
    src = "ios";
  } else if (e.absolute || e.type === "deviceorientationabsolute") {
    if (alpha == null || beta == null || gamma == null) return;
    // heading of the rear camera (device −Z axis) from the full rotation (W3C Z-X'-Y'')
    const cA = Math.cos(rad(alpha)), sA = Math.sin(rad(alpha));
    const sB = Math.sin(rad(beta)), cB = Math.cos(rad(beta));
    const sG = Math.sin(rad(gamma)), cG = Math.cos(rad(gamma));
    const vx = -cA * sG - sA * sB * cG;   // east
    const vy = -sA * sG + cA * sB * cG;   // north
    if (Math.hypot(vx, vy) < 0.15) return; // camera pointing at the ground/sky: heading undefined
    mag = norm360((Math.atan2(vx, vy) * 180) / Math.PI);
    src = "absolute";
  } else {
    return; // relative-only orientation can't give a compass heading
  }
  if (beta != null && gamma != null) {
    const vz = -Math.cos(rad(beta)) * Math.cos(rad(gamma));
    state.pitch = (Math.asin(Math.max(-1, Math.min(1, vz))) * 180) / Math.PI;
  }
  const trueHdg = norm360(mag + prefs.declination);
  state.heading = smoothAngle(state.heading, trueHdg, 0.2);
  state.headingSource = src;
  emit("heading", state.heading);
}

/** for testing on a desk: feed a true heading directly */
export function fakeHeading(h, pitch = 0) {
  state.heading = norm360(h); state.pitch = pitch; state.headingSource = "fake";
  emit("heading", state.heading);
}
