# --- Frontend Build Stage ---
FROM node:16 as frontend_builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm --proxy http://proxy.azercell.com:8080 install
COPY frontend/ .
ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=${REACT_APP_API_URL}
RUN REACT_APP_API_URL=${REACT_APP_API_URL} npm run build

# --- Backend Setup Stage ---
FROM python:3.12-slim
WORKDIR /usr/src/app
COPY backend/ /usr/app/src/backend/
RUN pip install --proxy http://proxy.azercell.com:8080 --no-cache-dir -r /usr/app/src/backend/requirements.txt

# --- Final Stage ---
COPY --from=frontend_builder /app/build/ /usr/app/src/backend/static/
RUN useradd -m myappuser
RUN mkdir -p /appdata && chown myappuser:myappuser /appdata
USER myappuser
EXPOSE 5000
CMD ["python", "/usr/app/src/backend/main.py"]