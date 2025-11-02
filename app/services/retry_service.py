"""Async error handling and retry mechanisms for job application automation."""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime, timedelta
from enum import Enum
import random
import json
from pathlib import Path

from app.config import settings


class RetryStrategy(str, Enum):
    """Retry strategy types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    FIBONACCI_BACKOFF = "fibonacci_backoff"


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RetryableError(Exception):
    """Base class for retryable errors."""
    
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM, retry_after: Optional[float] = None):
        super().__init__(message)
        self.severity = severity
        self.retry_after = retry_after
        self.timestamp = datetime.utcnow()


class NonRetryableError(Exception):
    """Base class for non-retryable errors."""
    
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.HIGH):
        super().__init__(message)
        self.severity = severity
        self.timestamp = datetime.utcnow()


class BrowserError(RetryableError):
    """Browser-related errors."""
    pass


class NavigationError(RetryableError):
    """Navigation-related errors."""
    pass


class FormError(RetryableError):
    """Form-related errors."""
    pass


class NetworkError(RetryableError):
    """Network-related errors."""
    pass


class PortalChangeError(RetryableError):
    """Job portal interface change errors."""
    pass


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True,
        jitter_range: float = 0.1
    ):
        """Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of retry attempts
            strategy: Retry strategy to use
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            backoff_multiplier: Multiplier for exponential backoff
            jitter: Whether to add random jitter
            jitter_range: Range for jitter (0.0 to 1.0)
        """
        self.max_attempts = max_attempts
        self.strategy = strategy
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
        self.jitter_range = jitter_range


class ErrorLogger:
    """Structured error logging system."""
    
    def __init__(self, log_file: Optional[str] = None):
        """Initialize error logger.
        
        Args:
            log_file: Optional log file path
        """
        self.logger = logging.getLogger(__name__)
        self.log_file = Path(log_file) if log_file else Path("data/logs/error_log.json")
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    async def log_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        severity: ErrorSeverity = ErrorSeverity.MEDIUM
    ) -> None:
        """Log error with structured data.
        
        Args:
            error: Exception that occurred
            context: Context information
            severity: Error severity
        """
        try:
            error_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "error_type": type(error).__name__,
                "error_message": str(error),
                "severity": severity.value,
                "context": context,
                "traceback": None
            }
            
            # Add traceback for debugging
            if hasattr(error, '__traceback__') and error.__traceback__:
                import traceback
                error_data["traceback"] = traceback.format_exception(
                    type(error), error, error.__traceback__
                )
            
            # Log to standard logger
            log_level = {
                ErrorSeverity.LOW: logging.INFO,
                ErrorSeverity.MEDIUM: logging.WARNING,
                ErrorSeverity.HIGH: logging.ERROR,
                ErrorSeverity.CRITICAL: logging.CRITICAL
            }.get(severity, logging.WARNING)
            
            self.logger.log(log_level, f"{error_data['error_type']}: {error_data['error_message']}")
            
            # Append to JSON log file
            await self._append_to_log_file(error_data)
            
        except Exception as e:
            self.logger.error(f"Failed to log error: {e}")
    
    async def _append_to_log_file(self, error_data: Dict[str, Any]) -> None:
        """Append error data to JSON log file.
        
        Args:
            error_data: Error data to log
        """
        try:
            import aiofiles
            
            # Read existing log data
            log_entries = []
            if self.log_file.exists():
                async with aiofiles.open(self.log_file, 'r') as f:
                    content = await f.read()
                    if content.strip():
                        log_entries = json.loads(content)
            
            # Add new entry
            log_entries.append(error_data)
            
            # Keep only last 1000 entries
            if len(log_entries) > 1000:
                log_entries = log_entries[-1000:]
            
            # Write back to file
            async with aiofiles.open(self.log_file, 'w') as f:
                await f.write(json.dumps(log_entries, indent=2))
                
        except Exception as e:
            self.logger.error(f"Failed to write to log file: {e}")
    
    async def get_error_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get error statistics for the specified time period.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Error statistics
        """
        try:
            if not self.log_file.exists():
                return {"total_errors": 0, "error_types": {}, "severity_breakdown": {}}
            
            import aiofiles
            
            async with aiofiles.open(self.log_file, 'r') as f:
                content = await f.read()
                if not content.strip():
                    return {"total_errors": 0, "error_types": {}, "severity_breakdown": {}}
                
                log_entries = json.loads(content)
            
            # Filter by time period
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            recent_errors = [
                entry for entry in log_entries
                if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
            ]
            
            # Calculate statistics
            error_types = {}
            severity_breakdown = {}
            
            for entry in recent_errors:
                error_type = entry["error_type"]
                severity = entry["severity"]
                
                error_types[error_type] = error_types.get(error_type, 0) + 1
                severity_breakdown[severity] = severity_breakdown.get(severity, 0) + 1
            
            return {
                "total_errors": len(recent_errors),
                "error_types": error_types,
                "severity_breakdown": severity_breakdown,
                "time_period_hours": hours,
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get error statistics: {e}")
            return {"error": str(e)}


class RetryService:
    """Service for handling retries with exponential backoff and error handling."""
    
    def __init__(self):
        """Initialize retry service."""
        self.logger = logging.getLogger(__name__)
        self.error_logger = ErrorLogger()
        self.default_config = RetryConfig()
    
    def calculate_delay(
        self,
        attempt: int,
        config: RetryConfig
    ) -> float:
        """Calculate delay for retry attempt.
        
        Args:
            attempt: Current attempt number (0-based)
            config: Retry configuration
            
        Returns:
            Delay in seconds
        """
        if config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.base_delay * (config.backoff_multiplier ** attempt)
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.base_delay * (attempt + 1)
        elif config.strategy == RetryStrategy.FIBONACCI_BACKOFF:
            # Fibonacci sequence for delays
            if attempt <= 1:
                delay = config.base_delay
            else:
                fib_a, fib_b = 1, 1
                for _ in range(attempt - 1):
                    fib_a, fib_b = fib_b, fib_a + fib_b
                delay = config.base_delay * fib_b
        else:  # FIXED_DELAY
            delay = config.base_delay
        
        # Apply maximum delay limit
        delay = min(delay, config.max_delay)
        
        # Add jitter if enabled
        if config.jitter:
            jitter_amount = delay * config.jitter_range * (random.random() * 2 - 1)
            delay = max(0, delay + jitter_amount)
        
        return delay
    
    async def retry_with_backoff(
        self,
        func: Callable,
        *args,
        config: Optional[RetryConfig] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """Execute function with retry and backoff logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            config: Retry configuration
            context: Context for error logging
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retry attempts fail
        """
        if config is None:
            config = self.default_config
        
        if context is None:
            context = {"function": func.__name__}
        
        last_exception = None
        
        func_name = getattr(func, '__name__', str(func))
        
        for attempt in range(config.max_attempts):
            try:
                self.logger.info(f"Executing {func_name} (attempt {attempt + 1}/{config.max_attempts})")
                
                # Execute function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Success - log if this was a retry
                if attempt > 0:
                    self.logger.info(f"{func_name} succeeded on attempt {attempt + 1}")
                
                return result
                
            except NonRetryableError as e:
                # Don't retry non-retryable errors
                await self.error_logger.log_error(
                    e, 
                    {**context, "attempt": attempt + 1, "retryable": False},
                    e.severity
                )
                raise e
                
            except Exception as e:
                last_exception = e
                
                # Determine if error is retryable
                is_retryable = self._is_retryable_error(e)
                severity = self._determine_error_severity(e)
                
                # Log the error
                await self.error_logger.log_error(
                    e,
                    {**context, "attempt": attempt + 1, "retryable": is_retryable},
                    severity
                )
                
                if not is_retryable:
                    self.logger.error(f"{func_name} failed with non-retryable error: {e}")
                    raise e
                
                # Check if we have more attempts
                if attempt < config.max_attempts - 1:
                    delay = self.calculate_delay(attempt, config)
                    
                    self.logger.warning(
                        f"{func_name} failed (attempt {attempt + 1}), retrying in {delay:.2f}s: {e}"
                    )
                    
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(f"{func_name} failed after {config.max_attempts} attempts")
        
        # All attempts failed
        raise last_exception
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable.
        
        Args:
            error: Exception to check
            
        Returns:
            True if error is retryable
        """
        # Explicit retryable errors
        if isinstance(error, RetryableError):
            return True
        
        # Explicit non-retryable errors
        if isinstance(error, NonRetryableError):
            return False
        
        # Common retryable error patterns
        retryable_patterns = [
            "timeout",
            "connection",
            "network",
            "temporary",
            "rate limit",
            "server error",
            "503",
            "502",
            "504"
        ]
        
        error_message = str(error).lower()
        return any(pattern in error_message for pattern in retryable_patterns)
    
    def _determine_error_severity(self, error: Exception) -> ErrorSeverity:
        """Determine error severity.
        
        Args:
            error: Exception to analyze
            
        Returns:
            Error severity level
        """
        if hasattr(error, 'severity'):
            return error.severity
        
        error_message = str(error).lower()
        
        # Critical errors
        if any(pattern in error_message for pattern in ["critical", "fatal", "crash"]):
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if any(pattern in error_message for pattern in ["authentication", "authorization", "permission"]):
            return ErrorSeverity.HIGH
        
        # Medium severity errors (default)
        if any(pattern in error_message for pattern in ["timeout", "connection", "network"]):
            return ErrorSeverity.MEDIUM
        
        # Low severity errors
        if any(pattern in error_message for pattern in ["warning", "info"]):
            return ErrorSeverity.LOW
        
        return ErrorSeverity.MEDIUM


class FallbackStrategy:
    """Fallback strategies for handling portal interface changes."""
    
    def __init__(self):
        """Initialize fallback strategy."""
        self.logger = logging.getLogger(__name__)
        self.fallback_selectors = {
            "email": [
                'input[type="email"]',
                'input[name*="email" i]',
                'input[id*="email" i]',
                'input[placeholder*="email" i]',
                'input[name="username"]',
                'input[id="username"]'
            ],
            "submit": [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Submit")',
                'button:has-text("Apply")',
                'button:has-text("Send")',
                'a:has-text("Submit")',
                'a:has-text("Apply")',
                '[role="button"]:has-text("Submit")'
            ]
        }
    
    async def find_element_with_fallback(
        self,
        page,
        primary_selector: str,
        element_type: str,
        timeout: int = 10000
    ) -> Optional[Any]:
        """Find element using fallback selectors.
        
        Args:
            page: Playwright page object
            primary_selector: Primary CSS selector
            element_type: Element type for fallback
            timeout: Timeout in milliseconds
            
        Returns:
            Found element or None
        """
        try:
            # Try primary selector first
            element = await page.wait_for_selector(primary_selector, timeout=timeout)
            if element:
                self.logger.info(f"Found element with primary selector: {primary_selector}")
                return element
        except:
            pass
        
        # Try fallback selectors
        fallback_selectors = self.fallback_selectors.get(element_type, [])
        
        for selector in fallback_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=2000)
                if element:
                    self.logger.info(f"Found element with fallback selector: {selector}")
                    return element
            except:
                continue
        
        self.logger.warning(f"No element found for type: {element_type}")
        return None
    
    async def detect_portal_changes(
        self,
        page,
        expected_elements: List[str]
    ) -> Dict[str, Any]:
        """Detect if job portal interface has changed.
        
        Args:
            page: Playwright page object
            expected_elements: List of expected element selectors
            
        Returns:
            Change detection result
        """
        detection_result = {
            "changes_detected": False,
            "missing_elements": [],
            "found_elements": [],
            "confidence_score": 0.0,
            "recommendations": []
        }
        
        try:
            for selector in expected_elements:
                try:
                    element = await page.wait_for_selector(selector, timeout=2000)
                    if element:
                        detection_result["found_elements"].append(selector)
                    else:
                        detection_result["missing_elements"].append(selector)
                except:
                    detection_result["missing_elements"].append(selector)
            
            # Calculate confidence score
            total_elements = len(expected_elements)
            found_elements = len(detection_result["found_elements"])
            
            if total_elements > 0:
                detection_result["confidence_score"] = found_elements / total_elements
            
            # Determine if changes detected
            detection_result["changes_detected"] = detection_result["confidence_score"] < 0.7
            
            # Generate recommendations
            if detection_result["changes_detected"]:
                detection_result["recommendations"] = [
                    "Update element selectors",
                    "Review page structure changes",
                    "Consider using fallback selectors",
                    "Manual verification may be required"
                ]
            
            return detection_result
            
        except Exception as e:
            self.logger.error(f"Portal change detection failed: {e}")
            return {
                "changes_detected": True,
                "error": str(e),
                "confidence_score": 0.0
            }


# Global service instances
retry_service = RetryService()
fallback_strategy = FallbackStrategy()