#!/usr/bin/env node
/**
 * Stdio MCP proxy for open-data-mcp.
 * - initialize + tools/list: no APIFY_TOKEN required (Glama introspection)
 * - tools/call: forwards to mcp.apify.com with APIFY_TOKEN from env
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { loadTools, missingTokenMessage, actorToolName, ACTORS } from './tools.js';
import { callUpstreamTool } from './forward.js';

const tools = loadTools();
const toolByName = new Map(tools.map((t) => [t.name, t]));

const server = new Server(
  {
    name: 'open-data-mcp',
    version: '1.0.0',
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
      content: [
        {
          type: 'text',
          text: `Unknown tool "${name}". Known tools: ${known}`,
        },
      ],
    };
  }

  const token = process.env.APIFY_TOKEN;
  if (!token || !String(token).trim()) {
    return {
      isError: true,
      content: [{ type: 'text', text: missingTokenMessage() }],
    };
  }

  try {
    const timeoutMs = Number(process.env.OPEN_DATA_MCP_TIMEOUT_MS || 120000);
    const result = await callUpstreamTool({ name, args, token, timeoutMs });
    if (result?.content) return result;
    return {
      content: [{ type: 'text', text: JSON.stringify(result ?? null) }],
    };
  } catch (e) {
    const code = e?.code || 'UPSTREAM_ERROR';
    return {
      isError: true,
      content: [
        {
          type: 'text',
          text: `[${code}] ${e?.message || String(e)}`,
        },
      ],
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  // Never print env secrets
  console.error(err?.message || String(err));
  process.exit(1);
});
