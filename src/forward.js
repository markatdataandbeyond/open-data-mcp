/**
 * Forward tools/call to mcp.apify.com over Streamable HTTP.
 * Never logs or returns the token value.
 */
import { UPSTREAM_URL, missingTokenMessage } from './tools.js';

const DEFAULT_TIMEOUT_MS = 120_000;

function redact(text, token) {
  if (!token || !text) return text;
  return String(text).split(token).join('***');
}

async function readSseOrJson(res) {
  const ctype = (res.headers.get('content-type') || '').toLowerCase();
  const body = await res.text();
  if (ctype.includes('text/event-stream')) {
    const payloads = [];
    for (const line of body.split(/\r?\n/)) {
      if (line.startsWith('data: ')) {
        try {
          payloads.push(JSON.parse(line.slice(6)));
        } catch {
          /* ignore non-json data lines */
        }
      }
    }
    return payloads;
  }
  try {
    return [JSON.parse(body)];
  } catch {
    return [{ error: { message: body.slice(0, 500) || `HTTP ${res.status}` } }];
  }
}

export async function callUpstreamTool({ name, args, token, timeoutMs = DEFAULT_TIMEOUT_MS, fetchImpl = fetch }) {
  if (!token || !String(token).trim()) {
    const err = new Error(missingTokenMessage());
    err.code = 'MISSING_TOKEN';
    throw err;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const headersBase = {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
    Accept: 'application/json, text/event-stream',
    'MCP-Protocol-Version': '2024-11-05',
  };

  try {
    const initRes = await fetchImpl(UPSTREAM_URL, {
      method: 'POST',
      headers: headersBase,
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'initialize',
        params: {
          protocolVersion: '2024-11-05',
          capabilities: {},
          clientInfo: { name: 'open-data-mcp-proxy', version: '1.0.0' },
        },
      }),
      signal: controller.signal,
    });

    if (!initRes.ok) {
      const t = redact(await initRes.text(), token);
      const err = new Error(`Upstream initialize failed: HTTP ${initRes.status} ${t.slice(0, 300)}`);
      err.code = 'UPSTREAM_ERROR';
      err.status = initRes.status;
      throw err;
    }

    const sessionId = initRes.headers.get('mcp-session-id');
    await readSseOrJson(initRes);

    const sessionHeaders = { ...headersBase };
    if (sessionId) sessionHeaders['Mcp-Session-Id'] = sessionId;

    await fetchImpl(UPSTREAM_URL, {
      method: 'POST',
      headers: sessionHeaders,
      body: JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }),
      signal: controller.signal,
    });

    const callRes = await fetchImpl(UPSTREAM_URL, {
      method: 'POST',
      headers: sessionHeaders,
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 2,
        method: 'tools/call',
        params: { name, arguments: args || {} },
      }),
      signal: controller.signal,
    });

    if (!callRes.ok) {
      const t = redact(await callRes.text(), token);
      const err = new Error(`Upstream tools/call failed: HTTP ${callRes.status} ${t.slice(0, 300)}`);
      err.code = 'UPSTREAM_ERROR';
      err.status = callRes.status;
      throw err;
    }

    const payloads = await readSseOrJson(callRes);
    const withResult = payloads.find((p) => p && (p.result || p.error));
    if (!withResult) {
      const err = new Error('Upstream returned no JSON-RPC result for tools/call');
      err.code = 'UPSTREAM_ERROR';
      throw err;
    }
    if (withResult.error) {
      const msg = redact(withResult.error.message || JSON.stringify(withResult.error), token);
      const err = new Error(`Upstream tool error: ${msg}`);
      err.code = 'UPSTREAM_ERROR';
      throw err;
    }
    return withResult.result;
  } catch (e) {
    if (e?.name === 'AbortError' || e?.code === 'ABORT_ERR') {
      const err = new Error(`Upstream call timed out after ${timeoutMs}ms`);
      err.code = 'TIMEOUT';
      throw err;
    }
    if (e?.code === 'MISSING_TOKEN' || e?.code === 'UPSTREAM_ERROR' || e?.code === 'TIMEOUT') throw e;
    const err = new Error(redact(e?.message || String(e), token));
    err.code = 'UPSTREAM_ERROR';
    throw err;
  } finally {
    clearTimeout(timer);
  }
}
