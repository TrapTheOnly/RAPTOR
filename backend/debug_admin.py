#!/usr/bin/env python3
"""
Debug script to check admin credentials and database status
"""
import os
import sqlite3
import bcrypt
from pathlib import Path

# Load environment variables (you might need to adjust these paths)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ dotenv not available, using system environment variables")

# Get environment variables
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
DATA_PATH = os.getenv("DATA_PATH", "./data/")
DB_PATH = os.path.join(DATA_PATH, "database.db")

print("🔍 DEBUGGING ADMIN AUTHENTICATION")
print("=" * 50)

# Check environment variables
print(f"📌 ADMIN_USERNAME: {ADMIN_USERNAME}")
print(f"📌 DATA_PATH: {DATA_PATH}")
print(f"📌 DB_PATH: {DB_PATH}")
print()

# Check if database exists
if os.path.exists(DB_PATH):
    print(f"✅ Database exists at: {DB_PATH}")
    print(f"📊 Database size: {os.path.getsize(DB_PATH)} bytes")
else:
    print(f"❌ Database does not exist at: {DB_PATH}")
    print("🔧 Try running the main application first to initialize the database")
    exit(1)

print()

# Check admin credentials file
admin_creds_file = "/tmp/writehere.txt"
if os.path.exists(admin_creds_file):
    print(f"📝 Admin credentials file found at: {admin_creds_file}")
    with open(admin_creds_file, 'r') as f:
        content = f.read()
        print(f"📄 Content: {content}")
else:
    print(f"⚠️ Admin credentials file not found at: {admin_creds_file}")

print()

# Check database tables and admin user
try:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Check if admin_users table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_users'")
        if c.fetchone():
            print("✅ admin_users table exists")
            
            # Get admin user info
            c.execute("SELECT username, password FROM admin_users")
            users = c.fetchall()
            
            if users:
                print(f"👥 Found {len(users)} admin user(s):")
                for username, hashed_password in users:
                    print(f"   - Username: {username}")
                    print(f"   - Password hash length: {len(hashed_password)} bytes")
                    
                    # If this is our expected admin user, let's test password verification
                    if username == ADMIN_USERNAME:
                        print(f"🔍 This matches the expected admin username: {ADMIN_USERNAME}")
                        
                        # Test with a sample password (you'll need to replace this)
                        test_password = input(f"\n🔐 Enter password to test for user '{username}': ")
                        try:
                            if bcrypt.checkpw(test_password.encode(), hashed_password):
                                print("✅ Password verification SUCCESSFUL!")
                            else:
                                print("❌ Password verification FAILED!")
                        except Exception as e:
                            print(f"💥 Error testing password: {e}")
            else:
                print("❌ No admin users found in database")
        else:
            print("❌ admin_users table does not exist")
            
        # Check allowed_users table
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='allowed_users'")
        if c.fetchone():
            print("\n✅ allowed_users table exists")
            c.execute("SELECT COUNT(*) FROM allowed_users")
            count = c.fetchone()[0]
            print(f"👥 Found {count} allowed user(s)")
        else:
            print("\n❌ allowed_users table does not exist")
            
except Exception as e:
    print(f"💥 Error connecting to database: {e}")

print()
print("🔧 TROUBLESHOOTING TIPS:")
print("1. Check if the application is running with the correct environment variables")
print("2. Look for log files in the data directory")
print("3. Make sure the database is properly initialized")
print("4. Restart the application to regenerate admin credentials if needed")

# Show log file location
log_file = os.path.join(DATA_PATH, "application.log")
if os.path.exists(log_file):
    print(f"\n📋 Log file found at: {log_file}")
    print("📋 Last 10 lines of log:")
    print("-" * 30)
    with open(log_file, 'r') as f:
        lines = f.readlines()
        for line in lines[-10:]:
            print(line.rstrip())
else:
    print(f"\n⚠️ Log file not found at: {log_file}") 