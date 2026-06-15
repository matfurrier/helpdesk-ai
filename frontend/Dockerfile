FROM node:22-alpine AS base
ENV PNPM_HOME="/pnpm" PATH="$PNPM_HOME:$PATH"
RUN corepack enable pnpm
WORKDIR /app

# ---------- dev stage (hot-reload) ----------
FROM base AS dev
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile 2>/dev/null || pnpm install
EXPOSE 3004
CMD ["pnpm", "dev"]

# ---------- build ----------
FROM base AS builder
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile 2>/dev/null || pnpm install
COPY . .
RUN pnpm build

# ---------- prod ----------
FROM node:22-alpine AS prod
WORKDIR /app
ENV NODE_ENV=production PORT=3004
RUN addgroup -S app && adduser -S app -G app
COPY --chown=app:app --from=builder /app/.next/standalone ./
COPY --chown=app:app --from=builder /app/.next/static ./.next/static
COPY --chown=app:app --from=builder /app/public ./public
USER app
EXPOSE 3004
CMD ["node", "server.js"]
