import os
import glob
import logging
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class DNSZoneMonitor:
    def __init__(self, db_path, shared_path):
        self.db_path = db_path
        self.shared_path = shared_path
        self.expected_file_age_hours = 25  # Allow 1 hour buffer for 24-hour cron job
        
    def check_zone_files_freshness(self):
        """
        Check if DNS zone files have been updated within the expected timeframe.
        
        Returns:
            dict: Status information including overall health and details
        """
        try:
            logger.info("Starting DNS zone file freshness check...")
            
            # Get all zone files
            zone_files = glob.glob(f"{self.shared_path}/*_A_Records")
            
            if not zone_files:
                logger.warning("No zone files found in shared path")
                return {
                    'status': 'error',
                    'message': 'No zone files found',
                    'details': {
                        'total_files': 0,
                        'stale_files': 0,
                        'fresh_files': 0
                    }
                }
            
            now = datetime.now()
            stale_threshold = now - timedelta(hours=self.expected_file_age_hours)
            
            stale_files = []
            fresh_files = []
            
            for zone_file in zone_files:
                try:
                    file_stat = os.stat(zone_file)
                    modification_time = datetime.fromtimestamp(file_stat.st_mtime)
                    
                    file_info = {
                        'filename': os.path.basename(zone_file),
                        'modification_time': modification_time.isoformat(),
                        'age_hours': (now - modification_time).total_seconds() / 3600
                    }
                    
                    if modification_time < stale_threshold:
                        stale_files.append(file_info)
                    else:
                        fresh_files.append(file_info)
                        
                except OSError as e:
                    logger.error(f"Error checking file {zone_file}: {e}")
                    stale_files.append({
                        'filename': os.path.basename(zone_file),
                        'error': str(e)
                    })
            
            # Determine overall status
            if len(stale_files) == 0:
                status = 'healthy'
                message = f"All {len(fresh_files)} zone files are up to date"
            elif len(stale_files) < len(zone_files):
                status = 'warning'
                message = f"{len(stale_files)} of {len(zone_files)} zone files are stale"
            else:
                status = 'error'
                message = f"All {len(stale_files)} zone files are stale"
            
            result = {
                'status': status,
                'message': message,
                'details': {
                    'total_files': len(zone_files),
                    'stale_files': len(stale_files),
                    'fresh_files': len(fresh_files),
                    'stale_file_list': stale_files,
                    'fresh_file_list': fresh_files,
                    'threshold_hours': self.expected_file_age_hours
                }
            }
            
            logger.info(f"Zone file check completed: {status} - {message}")
            return result
            
        except Exception as e:
            logger.error(f"Error during zone file freshness check: {e}")
            return {
                'status': 'error',
                'message': f"Failed to check zone files: {str(e)}",
                'details': {
                    'total_files': 0,
                    'stale_files': 0,
                    'fresh_files': 0
                }
            }
    
    def update_system_status(self, service_name, status, message, details=None):
        """
        Update system status in the database.
        
        Args:
            service_name (str): Name of the service
            status (str): Status (healthy, warning, error)
            message (str): Status message
            details (dict): Additional details
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Update or insert system status
            c.execute("""
                INSERT OR REPLACE INTO system_status (
                    service_name, status, message, details, last_updated
                ) VALUES (?, ?, ?, ?, ?)
            """, (service_name, status, message, str(details or {}), datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated system status for {service_name}: {status}")
            
        except Exception as e:
            logger.error(f"Error updating system status: {e}")
    
    def run_monitoring_check(self):
        """
        Run the complete monitoring check and update system status.
        """
        try:
            logger.info("Running DNS zone file monitoring check...")
            
            # Check zone files freshness
            result = self.check_zone_files_freshness()
            
            # Update system status
            self.update_system_status(
                service_name='data_collection',
                status=result['status'],
                message=result['message'],
                details=result['details']
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in monitoring check: {e}")
            # Update status as error
            self.update_system_status(
                service_name='data_collection',
                status='error',
                message=f"Monitoring check failed: {str(e)}",
                details={}
            )
            return {
                'status': 'error',
                'message': f"Monitoring check failed: {str(e)}"
            } 