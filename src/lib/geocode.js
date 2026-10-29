import { sleep } from './http.js';

export function makeGeocoder({
  fetchFn = fetch,
  sleepFn = sleep,
  now = Date.now,
  ua,
  minGapMs = 1100,
  tries = 5,
} = {}) {
  const cache = new Map();
  let last = -Infinity;
  async function gated(url) {
    const wait = last + minGapMs - now();
    if (wait > 0) await sleepFn(wait);
    last = now();
    return fetchFn(url, {
      headers: { 'User-Agent': ua, Accept: 'application/json' },
      signal: AbortSignal.timeout(30000),
    });
  }
  return async function geocode(text) {
    const key = text.toLowerCase().trim();
    if (cache.has(key)) return cache.get(key);
    const m = text.match(/^(.*?),\s*([A-Za-z]{2})$/);
    const p = new URLSearchParams({
      q: m ? m[1] : text,
      format: 'jsonv2',
      limit: '8',
      addressdetails: '1',
      'accept-language': 'en',
      featureType: 'settlement',
    });
    if (m) p.set('countrycodes', m[2].toLowerCase());
    let lastErr = '';
    for (let i = 0; i < tries; i++) {
      let r;
      try {
        r = await gated(`https://nominatim.openstreetmap.org/search?${p}`);
      } catch (e) {
        lastErr = e.message;
        await sleepFn(1000 * 2 ** i);
        continue;
      }
      if (r.status === 429 || r.status === 503) {
        const ra = Number(r.headers.get('retry-after')) * 1000 || 0;
        lastErr = `HTTP ${r.status}`;
        await sleepFn(Math.max(1000 * 2 ** i, ra));
        last = now();
        continue;
      }
      const t = await r.text();
      if (!r.ok) throw new Error(`Upstream API failed (nominatim): HTTP ${r.status}`);
      const hits = (JSON.parse(t) || []).map((h) => ({
        name: h.display_name,
        lat: +h.lat,
        lon: +h.lon,
        countryCode: h.address?.country_code || null,
      }));
      cache.set(key, hits);
      return hits;
    }
    throw new Error(`Upstream API failed (nominatim): ${lastErr} after ${tries} tries`);
  };
}
