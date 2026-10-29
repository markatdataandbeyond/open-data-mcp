/** Shared HTTP helpers. Never logs secrets. */
export const UA =
  'open-data-mcp/1.1 (+https://github.com/markatdataandbeyond/open-data-mcp; mailto:mark@dataandbeyond.dk)';

export class UpstreamError extends Error {
  constructor(message, { status } = {}) {
    super(message);
    this.name = 'UpstreamError';
    this.code = 'UPSTREAM_ERROR';
    if (status != null) this.status = status;
  }
}

export async function j(url, opt = {}, tries = 3) {
  const allow = opt.allowStatus || [];
  const { allowStatus: _drop, ...rest } = opt;
  let last = '';
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, {
        ...rest,
        headers: { 'User-Agent': UA, Accept: 'application/json', ...(rest.headers || {}) },
        signal: AbortSignal.timeout(rest.timeoutMs || 30000),
      });
      if (r.status === 404) return null;
      const t = await r.text();
      if (r.ok || allow.includes(r.status)) {
        try {
          return JSON.parse(t);
        } catch {
          if (r.ok) return t;
        }
      }
      last = `HTTP ${r.status}: ${t.replace(/\s+/g, ' ').slice(0, 300)}`;
      if (r.status >= 400 && r.status < 500 && r.status !== 429) {
        throw new UpstreamError(`Upstream API failed: ${last}`, { status: r.status });
      }
    } catch (e) {
      if (e instanceof UpstreamError) throw e;
      last = e.name === 'TimeoutError' || e.name === 'AbortError' ? 'timeout' : e.message;
    }
    await sleep(1500 * (i + 1));
  }
  throw new UpstreamError(`Upstream API failed: ${last}`);
}

export const sleep = (ms) => new Promise((s) => setTimeout(s, ms));

export function validateInput(inp) {
  for (const [k, v] of Object.entries(inp || {})) {
    if (typeof v === 'string' && v.length && !v.trim()) {
      throw new Error(`Invalid input: "${k}" contains only spaces.`);
    }
    if (Array.isArray(v)) {
      v.forEach((x, i) => {
        if (typeof x === 'string' && !x.trim()) {
          throw new Error(`Invalid input: "${k}" item ${i + 1} is empty or only spaces.`);
        }
      });
    }
  }
  return inp || {};
}

export function notFound(query, source, extra = {}) {
  return {
    query,
    status: 'NOT_FOUND',
    message: `No results for ${JSON.stringify(query)} in ${source}.`,
    ...extra,
  };
}
