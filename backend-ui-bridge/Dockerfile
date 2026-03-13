# ===============================
# DIIaC Backend - Production Image
# Node 20 + Bullseye + PowerShell
# ===============================

FROM node:20-bullseye

# -----------------------------
# Inject deterministic build hash
# MUST appear immediately after FROM
# -----------------------------
ARG GOVERNANCE_BUILD_HASH
ENV GOVERNANCE_BUILD_HASH=${GOVERNANCE_BUILD_HASH}

# -----------------------------
# Install base system dependencies
# -----------------------------
RUN set -eux; \
    apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 update; \
    apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 install -y --no-install-recommends \
      curl \
      ca-certificates \
      gnupg; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Install PowerShell (robust + retry-safe)
# -----------------------------
RUN set -eux; \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/trusted.gpg.d/microsoft.gpg; \
    echo "deb [arch=amd64] https://packages.microsoft.com/repos/microsoft-debian-bullseye-prod bullseye main" > /etc/apt/sources.list.d/microsoft.list; \
    apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 update; \
    apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 install -y --no-install-recommends --fix-missing powershell; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Application Setup
# -----------------------------
WORKDIR /workspace/backend-ui-bridge

COPY package.json package-lock.json ./
RUN npm config set fetch-retries 5 \
 && npm config set fetch-retry-mintimeout 20000 \
 && npm config set fetch-retry-maxtimeout 120000 \
 && npm config set fetch-timeout 300000 \
 && npm ci --omit=dev --no-audit --prefer-online

COPY . .

RUN groupadd -r diiac && useradd -r -g diiac -s /bin/false diiac \
 && mkdir -p /workspace/artefacts/human-input \
             /workspace/artefacts/decision-packs \
             /workspace/ledger \
             /workspace/contracts/keys \
 && cp /workspace/backend-ui-bridge/contracts/keys/public_keys.json /workspace/contracts/keys/public_keys.json \
 && chown -R diiac:diiac /workspace
USER diiac

EXPOSE 3001

CMD ["node", "server.js"]
