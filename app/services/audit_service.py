"""Audit logging service for comprehensive system activity tracking."""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from enum import Enum
from bson import ObjectId
import asyncio
from functools import wraps

from app.config import settings

# Configure structured audit logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# Create audit log directory
audit_log_dir = Path(settings.data_dir) / "logs" / "audit"
audit_log_dir.mkdir(parents=True, exist_ok=True)

# Create file handler for audit logs
audit_log_file = audit_log_dir / "audit.log"
audit_handler = logging.FileHandler(audit_log_file)
audit_handler.setLevel(logging.INFO)

# Create JSON formatter for structured logging
class AuditFormatter(logging.Formatter):
    """Custom formatter for structured audit logs."""
    
    def format(self, record):
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, 'audit_data'):
            log_entry.update(record.audit_data)
        
        return json.dumps(log_entry, default=str)

audit_handler.setFormatter(AuditFormatter())
audit_logger.addHandler(audit_handler)


class AuditEventType(str, Enum):
    """Types of audit events."""
    # User events
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    
    # Data events
    DATA_EXPORTED = "data_exported"
    DATA_DELETED = "data_deleted"
    DATA_IMPORTED = "data_imported"
    
    # Job events
    JOB_DISCOVERED = "job_discovered"
    JOB_APPLIED = "job_applied"
    JOB_SKIPPED = "job_skipped"
    
    # Resume events
    RESUME_CREATED = "resume_created"
    RESUME_OPTIMIZED = "resume_optimized"
    RESUME_DELETED = "resume_deleted"
    
    # Application events
    APPLICATION_STARTED = "application_started"
    APPLICATION_COMPLETED = "application_completed"
    APPLICATION_FAILED = "application_failed"
    
    # Security events
    CREDENTIALS_STORED = "credentials_stored"
    CREDENTIALS_ACCESSED = "credentials_accessed"
    CREDENTIALS_DELETED = "credentials_deleted"
    ENCRYPTION_KEY_ROTATED = "encryption_key_rotated"
    
    # System events
    BACKUP_CREATED = "backup_created"
    BACKUP_RESTORED = "backup_restored"
    BACKUP_DELETED = "backup_deleted"
    
    # Agent events
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"
    AGENT_ERROR = "agent_error"
    
    # API events
    API_REQUEST = "api_request"
    API_ERROR = "api_error"
    
    # Configuration events
    CONFIG_CHANGED = "config_changed"
    SETTINGS_UPDATED = "settings_updated"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditService:
    """Service for comprehensive audit logging and activity tracking."""
    
    def __init__(self):
        self.logger = audit_logger
    
    def log_event(self,
                  event_type: AuditEventType,
                  user_id: Optional[Union[str, ObjectId]] = None,
                  resource_id: Optional[Union[str, ObjectId]] = None,
                  resource_type: Optional[str] = None,
                  action: Optional[str] = None,
                  details: Optional[Dict[str, Any]] = None,
                  severity: AuditSeverity = AuditSeverity.LOW,
                  ip_address: Optional[str] = None,
                  user_agent: Optional[str] = None,
                  session_id: Optional[str] = None) -> None:
        """
        Log an audit event with structured data.
        
        Args:
            event_type: Type of event being logged
            user_id: ID of user performing the action
            resource_id: ID of resource being acted upon
            resource_type: Type of resource (user, job, application, etc.)
            action: Specific action being performed
            details: Additional event details
            severity: Severity level of the event
            ip_address: IP address of the request
            user_agent: User agent string
            session_id: Session identifier
        """
        audit_data = {
            "event_type": event_type.value,
            "severity": severity.value,
            "user_id": str(user_id) if user_id else None,
            "resource_id": str(resource_id) if resource_id else None,
            "resource_type": resource_type,
            "action": action,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "session_id": session_id,
            "details": details or {}
        }
        
        # Remove None values
        audit_data = {k: v for k, v in audit_data.items() if v is not None}
        
        # Log the event
        self.logger.info(f"Audit event: {event_type.value}", extra={"audit_data": audit_data})
    
    def log_user_event(self,
                      event_type: AuditEventType,
                      user_id: Union[str, ObjectId],
                      action: str,
                      details: Optional[Dict[str, Any]] = None,
                      severity: AuditSeverity = AuditSeverity.LOW) -> None:
        """Log a user-related event."""
        self.log_event(
            event_type=event_type,
            user_id=user_id,
            resource_type="user",
            action=action,
            details=details,
            severity=severity
        )
    
    def log_data_event(self,
                      event_type: AuditEventType,
                      user_id: Union[str, ObjectId],
                      action: str,
                      data_type: str,
                      details: Optional[Dict[str, Any]] = None,
                      severity: AuditSeverity = AuditSeverity.MEDIUM) -> None:
        """Log a data-related event (export, deletion, etc.)."""
        self.log_event(
            event_type=event_type,
            user_id=user_id,
            resource_type="data",
            action=action,
            details={**(details or {}), "data_type": data_type},
            severity=severity
        )
    
    def log_security_event(self,
                          event_type: AuditEventType,
                          action: str,
                          service_name: Optional[str] = None,
                          user_id: Optional[Union[str, ObjectId]] = None,
                          details: Optional[Dict[str, Any]] = None,
                          severity: AuditSeverity = AuditSeverity.HIGH) -> None:
        """Log a security-related event."""
        event_details = {**(details or {})}
        if service_name:
            event_details["service_name"] = service_name
        
        self.log_event(
            event_type=event_type,
            user_id=user_id,
            resource_type="security",
            action=action,
            details=event_details,
            severity=severity
        )
    
    def log_job_event(self,
                     event_type: AuditEventType,
                     user_id: Union[str, ObjectId],
                     job_id: Union[str, ObjectId],
                     action: str,
                     details: Optional[Dict[str, Any]] = None) -> None:
        """Log a job-related event."""
        self.log_event(
            event_type=event_type,
            user_id=user_id,
            resource_id=job_id,
            resource_type="job",
            action=action,
            details=details
        )
    
    def log_application_event(self,
                            event_type: AuditEventType,
                            user_id: Union[str, ObjectId],
                            application_id: Union[str, ObjectId],
                            job_id: Optional[Union[str, ObjectId]] = None,
                            action: str = None,
                            details: Optional[Dict[str, Any]] = None) -> None:
        """Log an application-related event."""
        event_details = {**(details or {})}
        if job_id:
            event_details["job_id"] = str(job_id)
        
        self.log_event(
            event_type=event_type,
            user_id=user_id,
            resource_id=application_id,
            resource_type="application",
            action=action,
            details=event_details
        )
    
    def log_resume_event(self,
                        event_type: AuditEventType,
                        user_id: Union[str, ObjectId],
                        resume_id: Union[str, ObjectId],
                        action: str,
                        details: Optional[Dict[str, Any]] = None) -> None:
        """Log a resume-related event."""
        self.log_event(
            event_type=event_type,
            user_id=user_id,
            resource_id=resume_id,
            resource_type="resume",
            action=action,
            details=details
        )
    
    def log_api_request(self,
                       method: str,
                       endpoint: str,
                       user_id: Optional[Union[str, ObjectId]] = None,
                       status_code: Optional[int] = None,
                       response_time_ms: Optional[float] = None,
                       ip_address: Optional[str] = None,
                       user_agent: Optional[str] = None) -> None:
        """Log an API request."""
        details = {
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "response_time_ms": response_time_ms
        }
        
        severity = AuditSeverity.LOW
        if status_code and status_code >= 400:
            severity = AuditSeverity.MEDIUM if status_code < 500 else AuditSeverity.HIGH
        
        self.log_event(
            event_type=AuditEventType.API_REQUEST,
            user_id=user_id,
            resource_type="api",
            action=f"{method} {endpoint}",
            details=details,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def log_system_event(self,
                        event_type: AuditEventType,
                        action: str,
                        component: str,
                        details: Optional[Dict[str, Any]] = None,
                        severity: AuditSeverity = AuditSeverity.MEDIUM) -> None:
        """Log a system-related event."""
        self.log_event(
            event_type=event_type,
            resource_type="system",
            action=action,
            details={**(details or {}), "component": component},
            severity=severity
        )
    
    async def get_audit_logs(self,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None,
                           user_id: Optional[Union[str, ObjectId]] = None,
                           event_type: Optional[AuditEventType] = None,
                           severity: Optional[AuditSeverity] = None,
                           limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve audit logs with filtering.
        
        Args:
            start_date: Start date for log retrieval
            end_date: End date for log retrieval
            user_id: Filter by user ID
            event_type: Filter by event type
            severity: Filter by severity level
            limit: Maximum number of logs to return
            
        Returns:
            List of audit log entries
        """
        try:
            logs = []
            
            with open(audit_log_file, 'r') as f:
                for line in f:
                    try:
                        log_entry = json.loads(line.strip())
                        
                        # Apply filters
                        if start_date:
                            log_time = datetime.fromisoformat(log_entry.get("timestamp", ""))
                            if log_time < start_date:
                                continue
                        
                        if end_date:
                            log_time = datetime.fromisoformat(log_entry.get("timestamp", ""))
                            if log_time > end_date:
                                continue
                        
                        if user_id and log_entry.get("user_id") != str(user_id):
                            continue
                        
                        if event_type and log_entry.get("event_type") != event_type.value:
                            continue
                        
                        if severity and log_entry.get("severity") != severity.value:
                            continue
                        
                        logs.append(log_entry)
                        
                        if len(logs) >= limit:
                            break
                            
                    except json.JSONDecodeError:
                        continue
            
            # Return most recent logs first
            return list(reversed(logs))
            
        except FileNotFoundError:
            return []
        except Exception as e:
            self.log_event(
                event_type=AuditEventType.API_ERROR,
                action="get_audit_logs",
                details={"error": str(e)},
                severity=AuditSeverity.HIGH
            )
            return []
    
    async def get_user_activity_summary(self, 
                                      user_id: Union[str, ObjectId],
                                      days: int = 30) -> Dict[str, Any]:
        """
        Get activity summary for a specific user.
        
        Args:
            user_id: User ID to get activity for
            days: Number of days to look back
            
        Returns:
            Dictionary containing activity summary
        """
        from datetime import timedelta
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        logs = await self.get_audit_logs(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            limit=1000
        )
        
        # Analyze activity
        activity_summary = {
            "user_id": str(user_id),
            "period_days": days,
            "total_events": len(logs),
            "event_types": {},
            "severity_breakdown": {},
            "daily_activity": {},
            "recent_events": logs[:10]  # Most recent 10 events
        }
        
        for log in logs:
            # Count event types
            event_type = log.get("event_type", "unknown")
            activity_summary["event_types"][event_type] = activity_summary["event_types"].get(event_type, 0) + 1
            
            # Count severity levels
            severity = log.get("severity", "unknown")
            activity_summary["severity_breakdown"][severity] = activity_summary["severity_breakdown"].get(severity, 0) + 1
            
            # Count daily activity
            log_date = log.get("timestamp", "")[:10]  # Get date part
            activity_summary["daily_activity"][log_date] = activity_summary["daily_activity"].get(log_date, 0) + 1
        
        return activity_summary


def audit_decorator(event_type: AuditEventType, 
                   action: str,
                   resource_type: Optional[str] = None,
                   severity: AuditSeverity = AuditSeverity.LOW):
    """
    Decorator to automatically audit function calls.
    
    Args:
        event_type: Type of audit event
        action: Action being performed
        resource_type: Type of resource being acted upon
        severity: Severity level of the event
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            
            try:
                result = await func(*args, **kwargs)
                
                # Log successful execution
                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                audit_service.log_event(
                    event_type=event_type,
                    resource_type=resource_type,
                    action=action,
                    details={
                        "function": func.__name__,
                        "execution_time_ms": execution_time,
                        "success": True
                    },
                    severity=severity
                )
                
                return result
                
            except Exception as e:
                # Log failed execution
                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                audit_service.log_event(
                    event_type=AuditEventType.API_ERROR,
                    resource_type=resource_type,
                    action=action,
                    details={
                        "function": func.__name__,
                        "execution_time_ms": execution_time,
                        "success": False,
                        "error": str(e)
                    },
                    severity=AuditSeverity.HIGH
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            
            try:
                result = func(*args, **kwargs)
                
                # Log successful execution
                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                audit_service.log_event(
                    event_type=event_type,
                    resource_type=resource_type,
                    action=action,
                    details={
                        "function": func.__name__,
                        "execution_time_ms": execution_time,
                        "success": True
                    },
                    severity=severity
                )
                
                return result
                
            except Exception as e:
                # Log failed execution
                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                audit_service.log_event(
                    event_type=AuditEventType.API_ERROR,
                    resource_type=resource_type,
                    action=action,
                    details={
                        "function": func.__name__,
                        "execution_time_ms": execution_time,
                        "success": False,
                        "error": str(e)
                    },
                    severity=AuditSeverity.HIGH
                )
                raise
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Global service instance
audit_service = AuditService()