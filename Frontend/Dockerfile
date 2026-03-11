FROM node:24-bookworm AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm config set fetch-retries 5 \
 && npm config set fetch-retry-mintimeout 20000 \
 && npm config set fetch-retry-maxtimeout 120000 \
 && npm config set fetch-timeout 300000 \
 && npm ci --no-audit --prefer-online

COPY . .
RUN npm run build

FROM node:24-bookworm-slim

WORKDIR /app

COPY --from=build /app/package.json /app/package-lock.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY --from=build /app/vite.config.ts ./

RUN groupadd -r diiac && useradd -r -g diiac -m -d /home/diiac -s /bin/false diiac \
 && chown -R diiac:diiac /app
USER diiac

EXPOSE 5173

CMD ["npx", "vite", "preview", "--host", "--port", "5173"]
