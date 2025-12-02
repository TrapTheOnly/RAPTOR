import os
from dotenv import load_dotenv

# Load environment variables once at module import.
load_dotenv()

# Core paths
DATA_PATH = os.getenv("DATA_PATH", "./data/")
DB_PATH = os.path.join(DATA_PATH, "database.db")
BACKUP_FOLDER = os.getenv("BACKUP_FOLDER", "./appdata/backup")
SHARED_PATH = os.getenv("SHARED_PATH", "")

# App / security
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Scheduling
UPDATE_TIME_SECONDS = int(os.getenv("UPDATE_TIME", "86400"))

# TLS / server
CERT_FILE = os.getenv("CERT_FILE")
KEY_FILE = os.getenv("KEY_FILE")
APP_PORT = os.getenv("APP_PORT", "5000")
