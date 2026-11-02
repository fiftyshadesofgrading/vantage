// geo.js — small spherical-earth helpers (metres, degrees true)
const R = 6371008.8;
const rad = d => (d * Math.PI) / 180;
const deg = r => (r * 180) / Math.PI;

export function dist(a, b) {
  const dLat = rad(b.lat - a.lat), dLon = rad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function bearing(a, b) {
  const y = Math.sin(rad(b.lon - a.lon)) * Math.cos(rad(b.lat));
  const x = Math.cos(rad(a.lat)) * Math.sin(rad(b.lat)) - Math.sin(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.cos(rad(b.lon - a.lon));
  return norm360(deg(Math.atan2(y, x)));
}

export function dest(p, brg, d) {
  const δ = d / R, θ = rad(brg), φ1 = rad(p.lat), λ1 = rad(p.lon);
  const φ2 = Math.asin(Math.sin(φ1) * Math.cos(δ) + Math.cos(φ1) * Math.sin(δ) * Math.cos(θ));
  const λ2 = λ1 + Math.atan2(Math.sin(θ) * Math.sin(δ) * Math.cos(φ1), Math.cos(δ) - Math.sin(φ1) * Math.sin(φ2));
  return { lat: deg(φ2), lon: deg(λ2) };
}

export const norm360 = d => ((d % 360) + 360) % 360;
/** signed smallest rotation from a to b, in (-180, 180] — positive = turn right */
export const angDiff = (a, b) => { const d = norm360(b - a); return d > 180 ? d - 360 : d; };

export function fmtDist(m) {
  if (m == null || !isFinite(m)) return "";
  if (m < 10) return `${Math.round(m)} m`;
  if (m < 1000) return `${Math.round(m / 5) * 5} m`;
  return `${(m / 1000).toFixed(m < 10000 ? 1 : 0)} km`;
}

const PTS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
export const compass = d => PTS[Math.round(norm360(d) / 22.5) % 16];

/** polygon (lat/lon pairs) for a view cone */
export function cone(p, heading, fov, range, steps = 18) {
  const pts = [[p.lat, p.lon]];
  for (let i = 0; i <= steps; i++) {
    const b = heading - fov / 2 + (fov * i) / steps;
    const q = dest(p, b, range);
    pts.push([q.lat, q.lon]);
  }
  return pts;
}

/** circular low-pass for headings */
export function smoothAngle(prev, next, k = 0.25) {
  if (prev == null) return next;
  return norm360(prev + angDiff(prev, next) * k);
}
