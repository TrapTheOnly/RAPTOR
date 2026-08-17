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
RUN useradd -m raptor_data_user
RUN mkdir -p /appdata && chown -R raptor_data_user:raptor_data_user /appdata
RUN sed -i 's/\r$//' /usr/app/src/backend/entrypoint.sh \
    && chmod +x /usr/app/src/backend/entrypoint.sh
USER raptor_data_user
ENV PYTHONPATH=/usr/app/src/backend
EXPOSE 5000
CMD ["/usr/app/src/backend/entrypoint.sh"]
