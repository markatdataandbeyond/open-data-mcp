# Local open-data MCP server (stdio).
# tools/list works with no secrets. Optional OPENALEX_API_KEY / NCBI_API_KEY for extra sources.
FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev || npm install --omit=dev
COPY src ./src
COPY catalog ./catalog
ENV NODE_ENV=production
USER node
CMD ["node", "src/index.js"]
