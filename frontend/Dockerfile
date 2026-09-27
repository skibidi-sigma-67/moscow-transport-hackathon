# Build stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

ARG VITE_API_URL
ARG VITE_WS_URL
ARG VITE_YANDEX_MAP_API_KEY
ARG VITE_HEALTH_CHECK_INTERVAL

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL
ENV VITE_YANDEX_MAP_API_KEY=$VITE_YANDEX_MAP_API_KEY
ENV VITE_HEALTH_CHECK_INTERVAL=$VITE_HEALTH_CHECK_INTERVAL

RUN npm run build

# Production stage
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
