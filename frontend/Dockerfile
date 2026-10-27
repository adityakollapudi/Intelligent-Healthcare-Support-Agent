# IHSA frontend: static build served by unprivileged nginx. VITE_* values are public build-time
# settings only (never secrets). Build: docker build --build-arg VITE_API_BASE_URL=... ./frontend
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ARG VITE_API_TIMEOUT_MS=15000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL VITE_API_TIMEOUT_MS=$VITE_API_TIMEOUT_MS
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
