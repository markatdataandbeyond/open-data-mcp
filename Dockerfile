# Glama / local stdio MCP proxy for open-data-mcp.
# Introspection (initialize + tools/list) works without APIFY_TOKEN.
# tools/call forwards to https://mcp.apify.com with Authorization: Bearer $APIFY_TOKEN.
# Glama Admin → Dockerfile should use this file (CMD starts the stdio server).
FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev || npm install --omit=dev
COPY src ./src
COPY catalog ./catalog
ENV NODE_ENV=production
# Optional at runtime for tools/call only; leave unset for Glama introspection.
# APIFY_TOKEN=
USER node
CMD ["node", "src/index.js"]
