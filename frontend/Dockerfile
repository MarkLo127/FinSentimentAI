# Multi-stage build: bun compiles the SPA, nginx serves the static dist.
# nginx also proxies /api/* to the backend service so the SPA is same-origin.

FROM oven/bun:1.3-alpine AS build
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile
COPY . .
# Build-time env: Vite inlines import.meta.env.VITE_* at `bun run build`, so
# the Google OAuth Client ID must be present in the build environment, not
# just at runtime. Railway exposes service variables as Docker build args
# when ARG is declared here; the ENV line then makes them visible to Vite.
ARG VITE_GOOGLE_CLIENT_ID=""
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
RUN bun run build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
# nginx 1.19+ auto-runs envsubst on /etc/nginx/templates/*.template at boot,
# emitting the result into /etc/nginx/conf.d/. The filter limits substitution
# to PORT and BACKEND_HOST so nginx's own variables ($host, $uri) survive.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
# 15-railway-resolver.envsh exports NGINX_RESOLVER (read from /etc/resolv.conf)
# before the stock 20-envsubst-on-templates.sh runs, so the template can bake it in.
COPY docker-entrypoint.d/ /docker-entrypoint.d/
RUN chmod +x /docker-entrypoint.d/*.envsh
ENV NGINX_ENVSUBST_FILTER='^(PORT|BACKEND_HOST|NGINX_RESOLVER)$' \
    PORT=80 \
    BACKEND_HOST=backend:8000
