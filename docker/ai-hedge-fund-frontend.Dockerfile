FROM node:20-alpine AS build

WORKDIR /app/frontend

ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

COPY external/ai-hedge-fund/app/frontend/package*.json ./
RUN npm ci

COPY external/ai-hedge-fund/app/frontend ./
RUN printf "export { Layout } from './Layout';\n" > /app/frontend/src/components/layout.ts \
    && find /app/frontend/src -type f \( -name "*.ts" -o -name "*.tsx" \) -exec sed -i "s|http://localhost:8000|${VITE_API_URL}|g" {} + \
    && npx vite build

FROM nginx:1.27-alpine

COPY docker/ai-hedge-fund-frontend.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
