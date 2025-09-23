# ====== Builder ======
FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# 1) deps
COPY apps/web/package*.json ./apps/web/
RUN cd apps/web && npm install --no-audit --no-fund

# 2) źródła + build
COPY apps/web ./apps/web
RUN cd apps/web && npm run build

# ====== Runner ======
FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1

# Next standalone output:
# - .next/standalone zawiera server.js i node_modules wymagane w runtime
# - .next/static to assety
COPY --from=builder /app/apps/web/.next/standalone ./apps/web
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
# (USUNIĘTO linię COPY public, bo katalog nie istnieje w buildzie)

EXPOSE 3000
CMD ["node", "apps/web/server.js"]
