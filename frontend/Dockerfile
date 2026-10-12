# Build context is the repository root (docker-compose.yml sets it): the console reads bench/results.json and
# contracts/ at build time, so they have to be in the image build.
FROM node:20-alpine

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps

COPY bench/results.json /app/bench/results.json
COPY contracts /app/contracts
COPY frontend/ .

# Production-style build (live backend). /api and /mcp are proxied to QUORUM_BACKEND / QUORUM_MCP at runtime.
RUN npm run build

CMD ["npx", "vite", "preview", "--host", "0.0.0.0", "--port", "5173", "--strictPort"]
