# --- Frontend Build Stage ---
USER root
FROM node:16 AS frontend_builder
WORKDIR /app
COPY frontend/package*.json ./
ARG http_proxy
RUN npm --proxy $http_proxy install
COPY frontend/ .
RUN npm run build

# --- Backend Setup Stage ---
USER root
FROM python:3.12-slim
WORKDIR /usr/app/src
ARG http_proxy
ENV http_proxy=$http_proxy
ENV https_proxy=$http_proxy
COPY backend/ /usr/app/src/backend/
RUN pip install --no-cache-dir -r /usr/app/src/backend/requirements.txt

# --- Final Stage ---
COPY --from=frontend_builder /app/build/ /usr/app/src/backend/static/
RUN useradd -m myappuser
RUN mkdir -p /appdata && chown myappuser:myappuser /appdata
USER myappuser
EXPOSE 5000
CMD ["python", "/usr/app/src/backend/main.py"]