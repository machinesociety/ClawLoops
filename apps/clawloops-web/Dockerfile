FROM node:22.12.0-alpine AS builder

WORKDIR /app
ARG NPM_REGISTRY=https://registry.npmjs.org
ARG PNPM_REGISTRY=https://registry.npmjs.org
RUN npm config set registry "${NPM_REGISTRY}" \
    && npm install -g pnpm@10.4.1 \
    && pnpm config set registry "${PNPM_REGISTRY}"

COPY apps/clawloops-web/package.json /app/package.json
COPY apps/clawloops-web/pnpm-lock.yaml /app/pnpm-lock.yaml
COPY apps/clawloops-web/patches /app/patches
RUN pnpm install --frozen-lockfile

COPY apps/clawloops-web /app
RUN pnpm build

FROM node:22.12.0-alpine

WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/package.json /app/package.json
COPY --from=builder /app/pnpm-lock.yaml /app/pnpm-lock.yaml
COPY --from=builder /app/node_modules /app/node_modules
COPY --from=builder /app/dist /app/dist

EXPOSE 3000
CMD ["node", "dist/index.js"]
