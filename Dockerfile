# ---------------------------------
# Stage 1: Build React Frontend
# ---------------------------------
FROM node:16 as frontend_builder

WORKDIR /app

# Copy package.json and package-lock.json first for caching
COPY frontend/package*.json ./

# Install dependencies for frontend
RUN npm --proxy http://proxy.azercell.com:8080 install

# Copy the rest of the frontend sources and build
COPY frontend/ .
RUN npm run build

# ---------------------------------
# Stage 2: Build Production Image with Python
# ---------------------------------
FROM python:3.12-slim

# Set working directory
WORKDIR /usr/src/app

# Copy backend code
COPY backend/ /usr/app/src/backend/

# Install Python dependencies
RUN pip install --proxy http://proxy.azercell.com:8080 --user --no-cache-dir -r /usr/app/src/backend/requirements.txt

# Copy the frontend build from the previous stage
# into a folder that Flask can serve, e.g. `backend/static`
COPY --from=frontend_builder /app/build/ /usr/app/src/backend/static/

# Create a user for security (optional, but recommended)
RUN useradd -m myappuser

# Switch to the new user
USER myappuser

# Expose the port your Flask app will run on
EXPOSE 5000

# The shared volume location (for DNS record uploads, etc.)
# We'll mount this in docker-compose.
VOLUME [ "/usr/src/app/shared" ]

# Generate SSH key pair for 'myappuser' if needed for deployment
# (You can also generate these in your CI pipeline and COPY them in.)
# For demonstration only (not recommended to store private keys in Dockerfile).
# RUN mkdir -p /home/myappuser/.ssh && \
#     ssh-keygen -t rsa -f /home/myappuser/.ssh/id_rsa -q -N ""

# Start the Flask server
CMD ["python", "/usr/app/src/backend/main.py"]