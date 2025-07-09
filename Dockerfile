# --- Frontend Build Stage ---
FROM node:20 AS frontend_builder
USER root
WORKDIR /app
COPY frontend/package*.json ./
ARG http_proxy
ARG https_proxy
RUN npm install
COPY frontend/ .
RUN npm run build

# --- Backend Setup Stage ---
FROM python:3.12-slim AS backend_builder
USER root
WORKDIR /usr/app/src
ARG http_proxy
ARG https_proxy
COPY backend/ /usr/app/src/backend/
RUN pip install --no-cache-dir -r /usr/app/src/backend/requirements.txt
RUN echo "Finished installing backend dependencies"

# --- Final Stage ---
COPY --from=frontend_builder /app/build/ /usr/app/src/backend/static/
RUN useradd -m dnsradar_data_user
RUN mkdir -p /appdata && chown -R dnsradar_data_user:dnsradar_data_user /appdata
USER dnsradar_data_user
EXPOSE 5000
CMD ["python", "/usr/app/src/backend/main.py"]