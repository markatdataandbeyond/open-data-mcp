# Glama / local stdio MCP proxy for open-data-mcp.
# Introspection (initialize + tools/list) works without APIFY_TOKEN.
# tools/call forwards to https://mcp.apify.com with Authorization: Bearer $APIFY_TOKEN.
FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev || npm install --omit=dev
COPY src ./src
COPY catalog ./catalog
ENV NODE_ENV=production
ENTRYPOINT ["node", "src/index.js"]
