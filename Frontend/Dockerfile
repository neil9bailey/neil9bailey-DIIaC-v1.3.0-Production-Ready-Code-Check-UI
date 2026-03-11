FROM node:24-bookworm AS build

WORKDIR /app

ARG VITE_API_BASE
ARG VITE_ENTRA_CLIENT_ID
ARG VITE_ENTRA_TENANT_ID
ARG VITE_ENTRA_REDIRECT_URI
ARG VITE_ENTRA_GROUP_MAP

ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_ENTRA_CLIENT_ID=$VITE_ENTRA_CLIENT_ID
ENV VITE_ENTRA_TENANT_ID=$VITE_ENTRA_TENANT_ID
ENV VITE_ENTRA_REDIRECT_URI=$VITE_ENTRA_REDIRECT_URI
ENV VITE_ENTRA_GROUP_MAP=$VITE_ENTRA_GROUP_MAP

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
