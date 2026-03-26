FROM node:20-alpine AS build

WORKDIR /app/frontend

ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

COPY app/frontend/package*.json ./
RUN npm ci

COPY app/frontend ./
RUN npm run build

FROM nginx:1.27-alpine

COPY docker/dbablo-miniapp.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
