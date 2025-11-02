"""Structured logging service with JSON formatting and centralized management."""

import logging
import json
import sys
from datetime import datetime
from typing import Dict, Any, Optional, Union
from pathlib import Path
import asyncio
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from contextlib import contextmanager

from app.config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "thread_name": record.threadName,
            "process": record.process,
        }
        
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        
        if hasattr(record, 'correlation_id'):
            log_entry['correlation_id'] = record.correlation_id
        
        if hasattr(record, 'component'):
            log_entry['component'] = record.component
        
        if hasattr(record, 'operation'):
            log_entry['operation'] = record.operation
        
        if hasattr(record, 'duration'):
            log_entry['duration'] = record.duration
        
        if hasattr(record, 'extra_data'):
            log_entry['extra_data'] = record.extra_data
        
        # Add exception information if present
        if record.exc_info:
            log_entry['exception'] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        return json.dumps(log_entry, ensure_ascii=False)


class StructuredLogger:
    """Enhanced logger with structured logging capabilities."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.name = name
    
    def _log_with_context(
        self,
        level: int,
        message: str,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        component: Optional[str] = None,
        operation: Optional[str] = None,
        duration: Optional[float] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        exc_info: Optional[bool] = None
    ):
        """Log message with structured context."""
        extra = {}
        
        if user_id:
            extra['user_id'] = user_id
        if correlation_id:
            extra['correlation_id'] = correlation_id
        if component:
            extra['component'] = component
        if operation:
            extra['operation'] = operation
        if duration is not None:
            extra['duration'] = duration
        if extra_data:
            extra['extra_data'] = extra_data
        
        self.logger.log(level, message, extra=extra, exc_info=exc_info)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self._log_with_context(logging.ERROR, message, exc_info=True, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with context."""
        self._log_with_context(logging.CRITICAL, message, exc_info=True, **kwargs)
    
    @contextmanager
    def operation_context(
        self,
        operation: str,
        component: Optional[str] = None,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        """Context manager for operation logging with timing."""
        start_time = datetime.now()
        
        self.info(
            f"Starting operation: {operation}",
            component=component,
            operation=operation,
            user_id=user_id,
            correlation_id=correlation_id
        )
        
        try:
            yield
            duration = (datetime.now() - start_time).total_seconds()
            self.info(
                f"Completed operation: {operation}",
                component=component,
                operation=operation,
                user_id=user_id,
                correlation_id=correlation_id,
                duration=duration
            )
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.error(
                f"Failed operation: {operation} - {str(e)}",
                component=component,
                operation=operation,
                user_id=user_id,
                correlation_id=correlation_id,
                duration=duration
            )
            raise


class LoggingService:
    """Centralized logging service management."""
    
    def __init__(self):
        self.configured = False
        self.loggers: Dict[str, StructuredLogger] = {}
    
    def configure_logging(self):
        """Configure logging based on settings."""
        if self.configured:
            return
        
        # Clear existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Set log level
        log_level = getattr(logging, settings.log_level.value)
        root_logger.setLevel(log_level)
        
        # Create formatters
        if settings.enable_json_logging:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(settings.log_format)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # File handler (if configured)
        if settings.log_file:
            log_path = Path(settings.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Use rotating file handler
            file_handler = RotatingFileHandler(
                settings.log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        
        # Configure specific loggers
        self._configure_component_loggers()
        
        self.configured = True
    
    def _configure_component_loggers(self):
        """Configure component-specific loggers."""
        # Suppress noisy third-party loggers
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("aiohttp").setLevel(logging.WARNING)
        logging.getLogger("motor").setLevel(logging.WARNING)
        logging.getLogger("pymongo").setLevel(logging.WARNING)
        
        # Set appropriate levels for our components
        component_levels = {
            "app.mcp": logging.INFO,
            "app.services": logging.INFO,
            "app.api": logging.INFO,
            "app.tasks": logging.INFO,
            "celery": logging.WARNING,
        }
        
        for component, level in component_levels.items():
            logging.getLogger(component).setLevel(level)
    
    def get_logger(self, name: str) -> StructuredLogger:
        """Get or create structured logger for component."""
        if name not in self.loggers:
            self.loggers[name] = StructuredLogger(name)
        return self.loggers[name]
    
    def log_system_event(
        self,
        event_type: str,
        message: str,
        component: str,
        level: str = "INFO",
        extra_data: Optional[Dict[str, Any]] = None
    ):
        """Log system-wide events."""
        logger = self.get_logger("system")
        log_method = getattr(logger, level.lower(), logger.info)
        
        log_method(
            message,
            component=component,
            operation=event_type,
            extra_data=extra_data
        )
    
    def log_user_action(
        self,
        user_id: str,
        action: str,
        component: str,
        result: str = "success",
        extra_data: Optional[Dict[str, Any]] = None
    ):
        """Log user actions for audit trail."""
        logger = self.get_logger("audit")
        
        logger.info(
            f"User action: {action} - {result}",
            user_id=user_id,
            component=component,
            operation=action,
            extra_data=extra_data
        )
    
    def log_performance_metric(
        self,
        metric_name: str,
        value: Union[int, float],
        component: str,
        operation: Optional[str] = None,
        unit: str = "ms"
    ):
        """Log performance metrics."""
        logger = self.get_logger("performance")
        
        logger.info(
            f"Performance metric: {metric_name} = {value}{unit}",
            component=component,
            operation=operation or "performance_measurement",
            extra_data={
                "metric_name": metric_name,
                "value": value,
                "unit": unit
            }
        )
    
    def log_security_event(
        self,
        event_type: str,
        message: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ):
        """Log security-related events."""
        logger = self.get_logger("security")
        
        security_data = {
            "event_type": event_type,
            "ip_address": ip_address
        }
        if extra_data:
            security_data.update(extra_data)
        
        logger.warning(
            f"Security event: {event_type} - {message}",
            user_id=user_id,
            component="security",
            operation=event_type,
            extra_data=security_data
        )


# Global logging service instance
logging_service = LoggingService()

# Configure logging on import
logging_service.configure_logging()


# Convenience functions for getting loggers
def get_logger(name: str) -> StructuredLogger:
    """Get structured logger for component."""
    return logging_service.get_logger(name)


def log_system_event(event_type: str, message: str, component: str, **kwargs):
    """Log system event."""
    logging_service.log_system_event(event_type, message, component, **kwargs)


def log_user_action(user_id: str, action: str, component: str, **kwargs):
    """Log user action."""
    logging_service.log_user_action(user_id, action, component, **kwargs)


def log_performance_metric(metric_name: str, value: Union[int, float], component: str, **kwargs):
    """Log performance metric."""
    logging_service.log_performance_metric(metric_name, value, component, **kwargs)


def log_security_event(event_type: str, message: str, **kwargs):
    """Log security event."""
    logging_service.log_security_event(event_type, message, **kwargs)