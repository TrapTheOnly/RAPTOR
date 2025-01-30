# --- Frontend Build Stage ---
FROM node:16 as frontend_builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm --proxy http://proxy.azercell.com:8080 install
COPY frontend/ .
RUN npm run build

# --- Backend Setup Stage ---
FROM python:3.12-slim
WORKDIR /usr/app/src
COPY backend/ /usr/app/src/backend/
RUN pip install --proxy http://proxy.azercell.com:8080 --no-cache-dir -r /usr/app/src/backend/requirements.txt

# --- Final Stage ---
COPY --from=frontend_builder /app/build/ /usr/app/src/backend/static/
RUN useradd -m myappuser
RUN mkdir -p /appdata && chown myappuser:myappuser /appdata
USER myappuser
ARG CERT_DIR=/certs
COPY $CERT_DIR /certs
ENV CERT_FILE=/certs/app.crt
ENV KEY_FILE=/certs/app.key
EXPOSE 5000
CMD ["python", "/usr/app/src/backend/main.py"]