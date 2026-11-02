// store.js — per-device settings and field calibrations (localStorage, always optional)
const KEY_CAL = "vantage.calibrations.v1";
const KEY_PREF = "vantage.prefs.v1";

function read(key, fallback) {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
}
function write(key, val) {
  try { localStorage.setItem(key, JSON.stringify(val)); return true; } catch { return false; }
}

export const prefs = Object.assign(
  {
    camFov: 66,          // horizontal FOV of the phone's main camera, long side (deg)
    declination: -14.4,  // Cape Ann magnetic declination (deg, west negative): true = magnetic + declination
    track: true,         // slide the overlay with the compass
    tiles: "engraving",  // engraving | streets | satellite
    opacity: 55,
  },
  read(KEY_PREF, {})
);
export const savePrefs = () => write(KEY_PREF, prefs);

export const calibrations = read(KEY_CAL, {});
export function saveCalibration(id, cal) {
  calibrations[id] = { ...cal, updated: new Date().toISOString() };
  return write(KEY_CAL, calibrations);
}
export function clearCalibration(id) {
  delete calibrations[id];
  return write(KEY_CAL, calibrations);
}

/** Download calibrations as JSON (drop the file into data/calibrations.json to share it) */
export function exportCalibrations(serverCals = {}) {
  const merged = { ...serverCals, ...calibrations };
  const blob = new Blob([JSON.stringify({ exported: new Date().toISOString(), calibrations: merged }, null, 1)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "calibrations.json";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  return Object.keys(merged).length;
}
