"""Comprehensive system monitoring and alerting service."""

import asyncio
import logging
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from app.config import settings
from app.services.logging_service import get_logger
from app.services.error_handling_service import error_handler, ErrorSeverity
from app.services.notification_service import notification_service


logger = get_logger(__name__)


class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class SystemMetrics:
    """System performance metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, int]
    process_count: int
    load_average: List[float]


@dataclass
class AlertRule:
    """Alert rule configuration."""
    name: str
    metric: str
    threshold: float
    comparison: str  # 'gt', 'lt', 'eq'
    level: AlertLevel
    cooldown_minutes: int = 5
    consecutive_violations: int = 1


class SystemMonitoringService:
    """Service for monitoring system health and performance."""
    
    def __init__(self):
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.metrics_history: List[SystemMetrics] = []
        self.alert_rules: List[AlertRule] = []
        self.last_alerts: Dict[str, datetime] = {}
        self.violation_counts: Dict[str, int] = {}
        self._setup_default_alert_rules()
    
    def _setup_default_alert_rules(self):
        """Setup default system alert rules."""
        self.alert_rules = [
            # CPU alerts
            AlertRule(
                name="high_cpu_usage",
                metric="cpu_percent",
                threshold=80.0,
                comparison="gt",
                level=AlertLevel.WARNING,
                cooldown_minutes=5,
                consecutive_violations=3
            ),
            AlertRule(
                name="critical_cpu_usage",
                metric="cpu_percent",
                threshold=95.0,
                comparison="gt",
                level=AlertLevel.CRITICAL,
                cooldown_minutes=2,
                consecutive_violations=2
            ),
            
            # Memory alerts
            AlertRule(
                name="high_memory_usage",
                metric="memory_percent",
                threshold=85.0,
                comparison="gt",
                level=AlertLevel.WARNING,
                cooldown_minutes=5,
                consecutive_violations=3
            ),
            AlertRule(
                name="critical_memory_usage",
                metric="memory_percent",
                threshold=95.0,
                comparison="gt",
                level=AlertLevel.CRITICAL,
                cooldown_minutes=2,
                consecutive_violations=2
            ),
            
            # Disk alerts
            AlertRule(
                name="high_disk_usage",
                metric="disk_percent",
                threshold=90.0,
                comparison="gt",
                level=AlertLevel.WARNING,
                cooldown_minutes=10,
                consecutive_violations=2
            ),
            AlertRule(
                name="critical_disk_usage",
                metric="disk_percent",
                threshold=98.0,
                comparison="gt",
                level=AlertLevel.CRITICAL,
                cooldown_minutes=5,
                consecutive_violations=1
            ),
        ]
    
    async def start_monitoring(self, interval_seconds: int = 30):
        """Start system monitoring."""
        if self.monitoring_active:
            logger.warning("System monitoring is already active")
            return
        
        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval_seconds)
        )
        
        logger.info(
            f"System monitoring started with {interval_seconds}s interval",
            component="system_monitoring",
            operation="start_monitoring"
        )
    
    async def stop_monitoring(self):
        """Stop system monitoring."""
        if not self.monitoring_active:
            return
        
        self.monitoring_active = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            self.monitoring_task = None
        
        logger.info(
            "System monitoring stopped",
            component="system_monitoring",
            operation="stop_monitoring"
        )
    
    async def _monitoring_loop(self, interval_seconds: int):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                # Collect system metrics
                metrics = await self._collect_system_metrics()
                
                # Store metrics
                self.metrics_history.append(metrics)
                
                # Keep only last 24 hours of metrics
                cutoff_time = datetime.now() - timedelta(hours=24)
                self.metrics_history = [
                    m for m in self.metrics_history 
                    if m.timestamp > cutoff_time
                ]
                
                # Check alert rules
                await self._check_alert_rules(metrics)
                
                # Log metrics periodically
                if len(self.metrics_history) % 10 == 0:  # Every 10 intervals
                    logger.debug(
                        f"System metrics: CPU {metrics.cpu_percent:.1f}%, "
                        f"Memory {metrics.memory_percent:.1f}%, "
                        f"Disk {metrics.disk_percent:.1f}%",
                        component="system_monitoring",
                        operation="metrics_collection",
                        extra_data={
                            "cpu_percent": metrics.cpu_percent,
                            "memory_percent": metrics.memory_percent,
                            "disk_percent": metrics.disk_percent,
                            "process_count": metrics.process_count
                        }
                    )
                
                await asyncio.sleep(interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                await error_handler.handle_error(
                    e,
                    component="system_monitoring",
                    operation="monitoring_loop",
                    severity=ErrorSeverity.MEDIUM
                )
                await asyncio.sleep(interval_seconds)
    
    async def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage (root partition)
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Network I/O
            network_io = psutil.net_io_counters()._asdict()
            
            # Process count
            process_count = len(psutil.pids())
            
            # Load average (Unix-like systems)
            try:
                load_average = list(psutil.getloadavg())
            except (AttributeError, OSError):
                # Windows doesn't have load average
                load_average = [0.0, 0.0, 0.0]
            
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_percent=disk_percent,
                network_io=network_io,
                process_count=process_count,
                load_average=load_average
            )
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            # Return default metrics on error
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_percent=0.0,
                disk_percent=0.0,
                network_io={},
                process_count=0,
                load_average=[0.0, 0.0, 0.0]
            )
    
    async def _check_alert_rules(self, metrics: SystemMetrics):
        """Check alert rules against current metrics."""
        for rule in self.alert_rules:
            try:
                # Get metric value
                metric_value = getattr(metrics, rule.metric, None)
                if metric_value is None:
                    continue
                
                # Check threshold
                violation = False
                if rule.comparison == "gt":
                    violation = metric_value > rule.threshold
                elif rule.comparison == "lt":
                    violation = metric_value < rule.threshold
                elif rule.comparison == "eq":
                    violation = metric_value == rule.threshold
                
                if violation:
                    # Increment violation count
                    self.violation_counts[rule.name] = self.violation_counts.get(rule.name, 0) + 1
                    
                    # Check if we've reached consecutive violations threshold
                    if self.violation_counts[rule.name] >= rule.consecutive_violations:
                        await self._trigger_alert(rule, metric_value, metrics)
                        # Reset violation count after triggering
                        self.violation_counts[rule.name] = 0
                else:
                    # Reset violation count on non-violation
                    self.violation_counts[rule.name] = 0
                    
            except Exception as e:
                logger.error(f"Error checking alert rule {rule.name}: {e}")
    
    async def _trigger_alert(self, rule: AlertRule, value: float, metrics: SystemMetrics):
        """Trigger an alert if cooldown period has passed."""
        now = datetime.now()
        
        # Check cooldown period
        if rule.name in self.last_alerts:
            time_since_last = now - self.last_alerts[rule.name]
            if time_since_last.total_seconds() < (rule.cooldown_minutes * 60):
                return  # Still in cooldown
        
        # Record alert time
        self.last_alerts[rule.name] = now
        
        # Create alert message
        alert_message = (
            f"System Alert: {rule.name} - {rule.metric} is {value:.1f}% "
            f"(threshold: {rule.threshold}%)"
        )
        
        # Log alert
        log_method = getattr(logger, rule.level.value, logger.info)
        log_method(
            alert_message,
            component="system_monitoring",
            operation="alert_triggered",
            extra_data={
                "rule_name": rule.name,
                "metric": rule.metric,
                "value": value,
                "threshold": rule.threshold,
                "level": rule.level,
                "system_metrics": {
                    "cpu_percent": metrics.cpu_percent,
                    "memory_percent": metrics.memory_percent,
                    "disk_percent": metrics.disk_percent,
                    "process_count": metrics.process_count
                }
            }
        )
        
        # Send notification for warning and above
        if rule.level in [AlertLevel.WARNING, AlertLevel.ERROR, AlertLevel.CRITICAL]:
            try:
                await notification_service.notify_system_error(
                    user_id="system",
                    error_type="system_alert",
                    error_message=alert_message,
                    context={
                        "rule_name": rule.name,
                        "metric": rule.metric,
                        "value": value,
                        "threshold": rule.threshold,
                        "level": rule.level,
                        "timestamp": now.isoformat()
                    }
                )
            except Exception as e:
                logger.error(f"Failed to send alert notification: {e}")
        
        # Handle critical alerts with error handler
        if rule.level == AlertLevel.CRITICAL:
            await error_handler.handle_error(
                Exception(alert_message),
                component="system_monitoring",
                operation="critical_alert",
                severity=ErrorSeverity.CRITICAL,
                additional_context={
                    "rule_name": rule.name,
                    "metric": rule.metric,
                    "value": value,
                    "threshold": rule.threshold
                }
            )
    
    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """Get the most recent system metrics."""
        if not self.metrics_history:
            return None
        return self.metrics_history[-1]
    
    def get_metrics_history(self, hours: int = 1) -> List[SystemMetrics]:
        """Get metrics history for specified hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            m for m in self.metrics_history 
            if m.timestamp > cutoff_time
        ]
    
    def get_alert_status(self) -> Dict[str, Any]:
        """Get current alert status."""
        return {
            "active_rules": len(self.alert_rules),
            "recent_alerts": {
                name: alert_time.isoformat()
                for name, alert_time in self.last_alerts.items()
                if (datetime.now() - alert_time).total_seconds() < 3600  # Last hour
            },
            "violation_counts": self.violation_counts.copy(),
            "monitoring_active": self.monitoring_active
        }
    
    def add_alert_rule(self, rule: AlertRule):
        """Add custom alert rule."""
        self.alert_rules.append(rule)
        logger.info(f"Added alert rule: {rule.name}")
    
    def remove_alert_rule(self, rule_name: str) -> bool:
        """Remove alert rule by name."""
        for i, rule in enumerate(self.alert_rules):
            if rule.name == rule_name:
                del self.alert_rules[i]
                logger.info(f"Removed alert rule: {rule_name}")
                return True
        return False


# Global system monitoring service instance
system_monitor = SystemMonitoringService()


async def initialize_system_monitoring():
    """Initialize system monitoring service."""
    try:
        await system_monitor.start_monitoring(interval_seconds=30)
        logger.info("System monitoring service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize system monitoring: {e}")


async def shutdown_system_monitoring():
    """Shutdown system monitoring service."""
    await system_monitor.stop_monitoring()


# Export for use in other modules
__all__ = [
    "system_monitor", 
    "SystemMetrics", 
    "AlertRule", 
    "AlertLevel",
    "initialize_system_monitoring",
    "shutdown_system_monitoring"
]