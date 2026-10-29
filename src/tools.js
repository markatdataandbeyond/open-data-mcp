import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

export const ACTORS = [
  'eu-company-verify',
  'dk-statistics',
  'scholar-search',
  'pubmed-search',
  'eu-tenders',
  'france-company-search',
  'nordic-company-registry',
  'clinical-trials',
  'vin-decoder-recalls',
  'weather-forecast',
];

export function actorToolName(actor) {
  return `dataandbeyond--${actor}`;
}

export function loadTools() {
  const raw = readFileSync(join(ROOT, 'catalog', 'tools.json'), 'utf8');
  const tools = JSON.parse(raw);
  if (!Array.isArray(tools) || tools.length !== 10) {
    throw new Error(`catalog/tools.json must list exactly 10 tools, got ${tools?.length}`);
  }
  const expected = new Set(ACTORS.map(actorToolName));
  for (const t of tools) {
    if (!expected.has(t.name)) throw new Error(`Unexpected tool name in catalog: ${t.name}`);
    if (!t.inputSchema || typeof t.inputSchema !== 'object') {
      throw new Error(`Tool ${t.name} missing inputSchema`);
    }
  }
  return tools;
}
