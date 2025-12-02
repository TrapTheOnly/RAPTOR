# DNS Zone File Monitoring Feature

This feature provides automated monitoring of DNS zone files to ensure that the cron job responsible for uploading zone files from DNS servers is functioning correctly.

## Overview

The DNS Zone File Monitoring system:
- Checks the modification dates of DNS zone files in the shared volume
- Verifies that zone files are updated within the expected timeframe (25 hours by default)
- Updates system status in the database
- Provides real-time status information on the dashboard

## Components

### 1. DNSZoneMonitor Class (`modules/dns_monitor.py`)

The main monitoring class that handles:
- **File freshness checking**: Scans DNS zone files and checks their modification times
- **Status classification**: Categorizes system health as `healthy`, `warning`, or `error`
- **Database updates**: Stores monitoring results in the system_status table
- **Detailed reporting**: Provides comprehensive status information

### 2. Database Schema

A new `system_status` table was added to track service health:

```sql
CREATE TABLE system_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    message TEXT,
    details TEXT,
    last_updated TEXT NOT NULL
);
```

### 3. API Endpoints

Two new endpoints were added to expose system status:

- `GET /api/system-status` - Returns status for all services
- `GET /api/system-status/<service_name>` - Returns status for a specific service

### 4. Dashboard Integration

The dashboard now displays real-time status for the "Data Collection" service:
- **Color-coded status**: Green (healthy), Orange (warning), Red (error)
- **Status messages**: Detailed information about current state
- **Last updated timestamp**: When the status was last checked

## Configuration

### Environment Variables

The monitoring system uses the following environment variables:

- `SHARED_PATH`: Path to the directory containing DNS zone files
- `UPDATE_TIME`: Interval for data updates (defaults to 86400 seconds = 24 hours)

### Monitoring Parameters

- **File age threshold**: 25 hours (allows 1-hour buffer for 24-hour cron jobs)
- **Check interval**: 24 hours (86400 seconds)
- **File pattern**: `*_A_Records` files in the shared directory

## Status Classifications

### Healthy
- All zone files are updated within the expected timeframe
- Status: `healthy`
- Dashboard: Green "Active" chip

### Warning
- Some zone files are stale but not all
- Status: `warning`
- Dashboard: Orange "Warning" chip

### Error
- All zone files are stale or no zone files found
- Status: `error`
- Dashboard: Red "Error" chip

## Testing

A test script is provided to verify the monitoring functionality:

```bash
cd backend
python test_dns_monitor.py
```

This script tests various scenarios:
1. No zone files present
2. Fresh zone files
3. Stale zone files
4. Complete monitoring check with database updates

## Integration with Main Application

The monitoring system is integrated into `main.py`:

1. **Initialization**: DNS monitor runs on application startup
2. **Periodic checks**: Monitoring runs every 24 hours via `periodic_update()`
3. **Status updates**: Results are stored in the database and accessible via API
4. **Dashboard display**: Real-time status shown on the dashboard

## Manual Monitoring Check

To manually trigger a monitoring check, you can call the `run_dns_monitoring()` function or use the test script.

## Troubleshooting

### Common Issues

1. **"No zone files found"**: 
   - Check that `SHARED_PATH` environment variable is set correctly
   - Verify that zone files with `*_A_Records` pattern exist in the shared directory

2. **"All zone files are stale"**:
   - Check if the cron job on DNS servers is running
   - Verify SFTP connectivity between DNS servers and the application
   - Check file permissions on the shared volume

3. **Database errors**:
   - Ensure the database is properly initialized
   - Check database permissions and disk space

### Monitoring Logs

The system logs monitoring activities to the application log:
- Zone file check results
- Database update confirmations
- Error messages with details

## Security Considerations

- The monitoring system only reads file metadata (modification times)
- No sensitive DNS data is processed or stored
- All database operations use parameterized queries
- API endpoints require authentication via `@login_required_json`

## Future Enhancements

Potential improvements to the monitoring system:
- Email notifications for status changes
- Historical status tracking
- Configurable thresholds per zone file
- Integration with external monitoring systems
- Automated remediation actions 