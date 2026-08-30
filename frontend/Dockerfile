# Multi-stage build producing a small, non-root runtime image.

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci 2>/dev/null || npm install

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* values are inlined at build time, so the API URL must be
# supplied as a build argument rather than only at runtime.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup -g 10001 -S nyaya && adduser -u 10001 -S nyaya -G nyaya

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nyaya:nyaya /app/.next/standalone ./
COPY --from=builder --chown=nyaya:nyaya /app/.next/static ./.next/static

USER nyaya
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0

CMD ["node", "server.js"]
