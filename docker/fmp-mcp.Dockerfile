FROM node:25.3.0-alpine AS builder

WORKDIR /app

COPY external/financial-modeling-prep-mcp-server/package.json external/financial-modeling-prep-mcp-server/package-lock.json ./
RUN npm ci

COPY external/financial-modeling-prep-mcp-server ./
RUN npm run build

FROM node:25.3.0-alpine AS runner

WORKDIR /app

COPY external/financial-modeling-prep-mcp-server/package.json external/financial-modeling-prep-mcp-server/package-lock.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist ./dist

ENV NODE_ENV=production \
    PORT=8080

EXPOSE 8080

CMD ["node", "dist/index.js"]
