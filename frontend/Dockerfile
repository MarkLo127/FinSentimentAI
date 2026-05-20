# Multi-stage build: bun compiles the SPA, nginx serves the static dist.
# nginx also proxies /api/* to the backend service so the SPA is same-origin.

FROM oven/bun:1.3-alpine AS build
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile
COPY . .
RUN bun run build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
# nginx 1.19+ auto-runs envsubst on /etc/nginx/templates/*.template at boot,
# emitting the result into /etc/nginx/conf.d/. The filter limits substitution
# to PORT and BACKEND_HOST so nginx's own variables ($host, $uri) survive.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
ENV NGINX_ENVSUBST_FILTER='^(PORT|BACKEND_HOST)$' \
    PORT=80 \
    BACKEND_HOST=backend:8000
