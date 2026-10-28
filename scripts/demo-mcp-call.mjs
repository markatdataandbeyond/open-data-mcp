#!/usr/bin/env node
/**
 * Minimal stdio MCP client for demos.
 * Spawns the local open-data-mcp proxy and calls one tool.
 * Never prints APIFY_TOKEN or Authorization headers.
 *
 * Usage: node scripts/demo-mcp-call.mjs <toolName> '<json-args>'
 * Example: node scripts/demo-mcp-call.mjs dataandbeyond--eu-company-verify '{"queries":["Novo Nordisk A/S"]}'
 */
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const toolName = process.argv[2];
const argsJson = process.argv[3] || '{}';

if (!toolName) {
  console.error('Usage: demo-mcp-call.mjs <toolName> \'<json-args>\'');
  process.exit(2);
}

let args;
try {
  args = JSON.parse(argsJson);
} catch (e) {
  console.error('Invalid JSON args');
  process.exit(2);
}

if (!process.env.APIFY_TOKEN) {
  console.error('APIFY_TOKEN env var is required (value not shown)');
  process.exit(1);
}

const child = spawn('node', [join(ROOT, 'src/index.js')], {
  cwd: ROOT,
  env: process.env,
  stdio: ['pipe', 'pipe', 'inherit'],
});

let buf = '';
let nextId = 1;
const pending = new Map();

function send(method, params) {
  const id = nextId++;
  const msg = { jsonrpc: '2.0', id, method, params };
  child.stdin.write(JSON.stringify(msg) + '\n');
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    setTimeout(() => {
      if (pending.has(id)) {
        pending.delete(id);
        reject(new Error(`Timeout waiting for ${method}`));
      }
    }, 120000);
  });
}

child.stdout.setEncoding('utf8');
child.stdout.on('data', (chunk) => {
  buf += chunk;
  let idx;
  while ((idx = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, idx).trim();
    buf = buf.slice(idx + 1);
    if (!line) continue;
    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      continue;
    }
    if (msg.id != null && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(JSON.stringify(msg.error)));
      else resolve(msg.result);
    }
  }
});

function summarize(tool, result) {
  const texts = (result?.content || [])
    .filter((c) => c.type === 'text')
    .map((c) => c.text)
    .join('\n');
  let data;
  try {
    data = JSON.parse(texts);
  } catch {
    // Apify MCP sometimes appends prose after the JSON object
    data = null;
    const start = texts.indexOf('{');
    if (start >= 0) {
      let depth = 0;
      for (let i = start; i < texts.length; i++) {
        if (texts[i] === '{') depth++;
        else if (texts[i] === '}') {
          depth--;
          if (depth === 0) {
            try { data = JSON.parse(texts.slice(start, i + 1)); } catch { data = null; }
            break;
          }
        }
      }
    }
    if (!data) {
      const m = texts.match(/"runId"\s*:\s*"([^"]+)"/);
      const s = texts.match(/"status"\s*:\s*"([^"]+)"/);
      const d = texts.match(/"id"\s*:\s*"([^"]+)"[^}]*"itemCount"\s*:\s*(\d+)/);
      if (m) data = { runId: m[1], status: s ? s[1] : undefined, storages: d ? { datasets: { default: { id: d[1], itemCount: Number(d[2]) } } } : undefined };
    }
  }
  let items = Array.isArray(data) ? data : data?.items;
  console.log(`MCP tool: ${tool}`);
  console.log(`isError: ${Boolean(result?.isError)}`);
  if (data && data.runId) {
    console.log(`runId: ${data.runId}`);
    console.log(`status: ${data.status}  exitCode: ${data.exitCode}`);
    const ds = data.storages?.datasets?.default;
    if (ds) console.log(`datasetId: ${ds.id}  itemCount: ${ds.itemCount}`);
    if (data.summary) console.log(`summary: ${data.summary}`);
  }
  if (Array.isArray(items) && items.length) {
    console.log(`items: ${items.length}`);
    for (const it of items.slice(0, 3)) {
      if (it.lei?.legalName || it.query) {
        console.log(
          `- ${it.query || ''} → ${it.lei?.legalName || it.verdict || 'n/a'}` +
            (it.lei?.lei ? ` (LEI ${it.lei.lei})` : '') +
            (it.verdict ? ` [${it.verdict}]` : ''),
        );
      } else if (it.vin || it.make) {
        console.log(
          `- VIN ${it.vin}: ${it.make || '?'} ${it.model || ''} ${it.modelYear || ''}` +
            (it.recalls ? ` | recalls: ${Array.isArray(it.recalls) ? it.recalls.length : it.recallCount ?? '?'}` : ''),
        );
      } else if (it.title) {
        console.log(
          `- ${it.year || '?'} | cited ${it.citedByCount ?? '?'} | ${it.title}` +
            (it.doi ? ` (DOI ${it.doi})` : ''),
        );
      } else {
        console.log('-', JSON.stringify(it).slice(0, 200));
      }
    }
    return;
  }
  if (!data && texts) {
    const preview = texts.length > 900 ? texts.slice(0, 900) + '\n… (truncated)' : texts;
    console.log(preview);
  }
}

(async () => {
  try {
    await send('initialize', {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: { name: 'open-data-mcp-demo', version: '1.0.0' },
    });
    // notifications/initialized (no id)
    child.stdin.write(
      JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n',
    );
    const listed = await send('tools/list', {});
    const names = (listed?.tools || []).map((t) => t.name);
    console.log(`tools/list → ${names.length} tools (token not required)`);
    if (!names.includes(toolName)) {
      console.error(`Tool ${toolName} not in list`);
      process.exit(1);
    }
    console.log(`Calling ${toolName} via stdio proxy → mcp.apify.com …`);
    console.log(`(APIFY_TOKEN is set in env; value never printed)`);
    const result = await send('tools/call', { name: toolName, arguments: args });
    summarize(toolName, result);
    child.kill();
    process.exit(0);
  } catch (e) {
    console.error('Demo MCP call failed:', e.message || String(e));
    child.kill();
    process.exit(1);
  }
})();
