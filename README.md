# RAPTOR Security Platform

**R**econnaissance, **A**ssessment, **P**enetration **T**esting, **O**perations & **R**eporting

> **New:** See [DNS Zone File Monitoring Feature](backend/DNS_MONITORING_README.md) for details on automated DNS zone file health checks and dashboard integration.

## Overview

RAPTOR is a comprehensive cybersecurity operations platform designed for security professionals, penetration testers, and IT administrators. It provides integrated asset discovery, vulnerability assessment, and penetration testing management capabilities.

## Key Features

### 🎯 **Asset Discovery & Management**
- Automated DNS zone file monitoring
- Real-time asset inventory tracking
- IP-to-source mapping and classification
- Change detection and alerting

### 🔒 **Security Testing Operations**
- Integrated penetration testing workflow
- Vulnerability tracking and management
- OWASP testing methodology support
- Security test reporting and documentation

### 📊 **Operations Dashboard**
- Real-time security metrics and KPIs
- Asset status monitoring
- Test progress tracking
- Activity timeline and alerts

### 👥 **Multi-Role Access Control**
- Admin: Full system control and user management
- Pentester: Security testing and vulnerability management
- User: Asset viewing and basic operations
- LDAP/Active Directory integration

### 🛡️ **Vulnerability Management**
- Automated vulnerability status tracking
- Remediation workflow management
- Service desk integration
- Fix verification and reporting

## Architecture

- **Frontend**: React.js with Material-UI
- **Backend**: Python Flask REST API
- **Database**: SQLite with comprehensive audit trails
- **Authentication**: LDAP/AD integration + local admin
- **Deployment**: Docker containerization

## Quick Start

### Prerequisites
- Docker and Docker Compose
- LDAP/Active Directory server (for user authentication)
- SSL certificates (for production)

### Environment Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd raptor-security-platform
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your specific configuration
   ```

3. **Start the platform**
   ```bash
   # Development
   docker-compose -f docker-compose.dev.yml up -d

   # Production
   docker-compose -f docker-compose.prod.yml up -d
   ```

4. **Access the platform**
   - Navigate to `https://localhost:5000` (or your configured port)
   - Retrieve the generated admin credentials from the file defined by `ADMIN_CREDENTIALS_FILE` (defaults to `/tmp/writehere.txt`)

## Configuration

### Required Environment Variables

```bash
# Application Settings
APP_PORT=5000
SECRET_KEY=your-secret-key
DATA_PATH=./data/
BACKUP_FOLDER=./backups/

# Admin User
ADMIN_USERNAME=admin
ADMIN_CREDENTIALS_FILE=/tmp/writehere.txt

# LDAP Configuration
LDAP_SERVER=ldap.yourdomain.com
LDAP_DOMAIN=yourdomain.com
LDAP_USER=service-account@yourdomain.com
LDAP_PASS=service-account-password

# File Transfer
SHARED_PATH=./shared/
FTP_USER=raptor-ftp
FTP_PASS=secure-ftp-password

# SSL (Production)
CERT_FILE=./certs/cert.pem
KEY_FILE=./certs/key.pem
```

## User Roles & Permissions

| Feature | Admin | Pentester | User |
|---------|-------|-----------|------|
| View Assets | ✅ | ✅ | ✅ |
| Edit Asset Details | ✅ | ✅ | ✅ |
| Delete Assets | ✅ | ❌ | ❌ |
| Security Testing | ✅ | ✅ | ❌ |
| User Management | ✅ | ❌ | ❌ |
| System Configuration | ✅ | ❌ | ❌ |
| Reports & Analytics | ✅ | ✅ | ✅ |

## Security Features

- **Secure Authentication**: LDAP/AD integration with session management
- **Role-Based Access Control**: Granular permission system
- **Audit Logging**: Comprehensive activity tracking
- **Data Encryption**: Secure data storage and transmission
- **Input Sanitization**: Protection against injection attacks

## API Documentation

### Authentication Endpoints
- `POST /login` - User authentication
- `GET /session-status` - Check login status
- `POST /logout` - End user session

### Asset Management
- `GET /api/records` - Retrieve all assets
- `POST /api/records/{id}` - Update asset details
- `DELETE /api/records/{id}` - Delete asset (admin only)

### Security Testing
- `GET /pentest/records` - Get penetration test data
- `POST /pentest/{id}` - Update test results
- `DELETE /pentest/{id}` - Remove test data

### Administration
- `GET /ldap-search` - Search LDAP users
- `POST /add-user` - Add new user
- `GET /existing-users` - List current users

## Development

### Local Development Setup

1. **Backend Development**
   ```bash
   cd backend
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   pip install -r requirements.txt
   python main.py
   ```

2. **Frontend Development**
   ```bash
   cd frontend
   npm install
   npm start
   ```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

For support and documentation:
- Check the application logs at `{DATA_PATH}/application.log`
- Review the debug output from `debug_admin.py`
- Ensure all environment variables are properly configured

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**RAPTOR** - *Precision in Cybersecurity Operations*
