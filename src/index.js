#!/usr/bin/env node
/**
 * open-data-mcp — local stdio MCP server.
 * Tools call official open-data APIs directly (no Apify required).
 * Optional env: OPENALEX_API_KEY, NCBI_API_KEY.
 * tools/list works with no env keys.
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { loadTools, actorToolName, ACTORS } from './tools.js';
import { runTool } from './lib/runTool.js';

const tools = loadTools();
const toolByName = new Map(tools.map((t) => [t.name, t]));

const server = new Server(
  {
    name: 'open-data-mcp',
    version: '1.1.0',
  },
  {
    capabilities: { tools: {} },
  },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: tools.map(({ name, description, inputSchema, annotations }) => {
    const out = { name, description, inputSchema };
    if (annotations) out.annotations = annotations;
    return out;
  }),
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const name = request.params?.name;
  const args = request.params?.arguments || {};

  if (!toolByName.has(name)) {
    const known = ACTORS.map(actorToolName).join(', ');
    return {
      isError: true,
      content: [{ type: 'text', text: `Unknown tool "${name}". Known tools: ${known}` }],
    };
  }

  try {
    return await runTool(name, args);
  } catch (e) {
    const code = e?.code || (e?.name === 'UpstreamError' ? 'UPSTREAM_ERROR' : 'TOOL_ERROR');
    return {
      isError: true,
      content: [{ type: 'text', text: `[${code}] ${e?.message || String(e)}` }],
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error(err?.message || String(err));
  process.exit(1);
});
