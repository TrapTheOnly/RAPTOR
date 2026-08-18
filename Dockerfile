# --- Collector binaries ---
FROM golang:1.23-bookworm AS collector_builder
WORKDIR /src
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG http_proxy
ARG https_proxy
ENV GOPROXY=https://proxy.golang.org,direct
COPY collector/go.mod collector/go.sum ./
RUN set -eux; \
    go_proxy="${HTTPS_PROXY:-${https_proxy:-${HTTP_PROXY:-${http_proxy:-}}}}"; \
    if [ -n "$go_proxy" ]; then export HTTPS_PROXY="$go_proxy" HTTP_PROXY="$go_proxy"; fi; \
    go mod download
COPY collector/ ./
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags "-s -w -X main.Version=1.1.0" -o dist/raptor-collector-linux-amd64 ./cmd/raptor-collector \
 && CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -ldflags "-s -w -X main.Version=1.1.0" -o dist/raptor-collector-linux-arm64 ./cmd/raptor-collector \
 && CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -ldflags "-s -w -X main.Version=1.1.0" -o dist/raptor-collector-windows-amd64.exe ./cmd/raptor-collector

# --- Frontend Build Stage ---
FROM node:20 AS frontend_builder
USER root
WORKDIR /app
COPY frontend/package*.json ./
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG http_proxy
ARG https_proxy
RUN set -eux; \
    proxy_http="${HTTP_PROXY:-${http_proxy:-}}"; \
    proxy_https="${HTTPS_PROXY:-${https_proxy:-$proxy_http}}"; \
    if [ -n "$proxy_http" ]; then npm config set proxy "$proxy_http"; fi; \
    if [ -n "$proxy_https" ]; then npm config set https-proxy "$proxy_https"; fi; \
    npm install; \
    npm config delete proxy >/dev/null 2>&1 || true; \
    npm config delete https-proxy >/dev/null 2>&1 || true
COPY frontend/ .
RUN npm run build

# --- Backend Setup Stage ---
FROM python:3.12-slim AS backend_builder
USER root
WORKDIR /usr/app/src
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG http_proxy
ARG https_proxy
COPY backend/ /usr/app/src/backend/
RUN set -eux; \
    pip_proxy="${HTTPS_PROXY:-${https_proxy:-${HTTP_PROXY:-${http_proxy:-}}}}"; \
    if [ -n "$pip_proxy" ]; then \
      pip install --no-cache-dir --proxy "$pip_proxy" -r /usr/app/src/backend/requirements.txt; \
    else \
      pip install --no-cache-dir -r /usr/app/src/backend/requirements.txt; \
    fi
RUN echo "Finished installing backend dependencies"

# --- Final Stage ---
FROM backend_builder AS final
COPY --from=frontend_builder /app/build/ /usr/app/src/backend/static/
COPY --from=collector_builder /src/dist/ /usr/app/src/collector/dist/
ENV COLLECTOR_DIST_DIR=/usr/app/src/collector/dist
RUN useradd -m raptor_data_user
RUN mkdir -p /appdata && chown -R raptor_data_user:raptor_data_user /appdata
RUN sed -i 's/\r$//' /usr/app/src/backend/entrypoint.sh \
    && chmod +x /usr/app/src/backend/entrypoint.sh
USER raptor_data_user
ENV PYTHONPATH=/usr/app/src/backend
EXPOSE 5000
CMD ["/usr/app/src/backend/entrypoint.sh"]
