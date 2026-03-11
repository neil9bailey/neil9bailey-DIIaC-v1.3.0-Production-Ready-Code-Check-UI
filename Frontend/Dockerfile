FROM node:24-bookworm

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm config set fetch-retries 5 \
 && npm config set fetch-retry-mintimeout 20000 \
 && npm config set fetch-retry-maxtimeout 120000 \
 && npm config set fetch-timeout 300000 \
 && npm ci --no-audit --prefer-online

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
