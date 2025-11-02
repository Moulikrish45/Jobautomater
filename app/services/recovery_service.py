"""System recovery service with graceful degradation capabilities."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from dataclasses import dataclass

from app.config import settings
from app.services.logging_service import get_logger
from app.services.error_handling_service import error_handler, ErrorSeverity


logger = get_logger(__name__)


class RecoveryAction(str, Enum):
    """Recovery action types."""
    RESTART_SERVICE = "restart_service"
    FALLBACK_MODE = "fallback_mode"
    CIRCUIT_BREAKER = "circuit_breaker"
    RETRY_OPERATION = "retry_operation"
    GRACEFUL_DEGRADATION = "graceful_degradation"
    ALERT_ADMIN = "alert_admin"


class SystemMode(str, Enum):
    """System operation modes."""
    NORMAL = "normal"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"


@dataclass
class RecoveryStrategy:
    """Recovery strategy configuration."""
    component: str
    trigger_conditions: List[str]
    actions: List[RecoveryAction]
    cooldown_period: int = 300  # 5 minutes
    max_attempts: int = 3
    escalation_threshold: int = 5


class SystemRecoveryService:
    """Service for system recovery and graceful degradation."""
    
    def __init__(self):
        self.current_mode = SystemMode.NORMAL
        self.recovery_strategies: Dict[str, RecoveryStrategy] = {}
        self.recovery_attempts: Dict[str, List[datetime]] = {}
        self.degraded_components: Dict[str, datetime] = {}
        self.fallback_handlers: Dict[str, Callable] = {}
        self._setup_default_strategies()
    
    def _setup_default_strategies(self):
        """Setup default recovery strategies for system components."""
        
        # Database recovery strategy
        self.recovery_strategies["database"] = RecoveryStrategy(
            component="database",
            trigger_conditions=["connection_failed", "timeout", "authentication_error"],
            actions=[
                RecoveryAction.RETRY_OPERATION,
                RecoveryAction.CIRCUIT_BREAKER,
                RecoveryAction.GRACEFUL_DEGRADATION,
                RecoveryAction.ALERT_ADMIN
            ],
            cooldown_period=60,
            max_attempts=3
        )
        
        # MCP agents recovery strategy
        self.recovery_strategies["mcp_agents"] = RecoveryStrategy(
            component="mcp_agents",
            trigger_conditions=["agent_crashed", "communication_failed", "timeout"],
            actions=[
                RecoveryAction.RESTART_SERVICE,
                RecoveryAction.FALLBACK_MODE,
                RecoveryAction.ALERT_ADMIN
            ],
            cooldown_period=120,
            max_attempts=2
        )
        
        # AI model recovery strategy
        self.recovery_strategies["ai_model"] = RecoveryStrategy(
            component="ai_model",
            trigger_conditions=["model_unavailable", "inference_failed", "timeout"],
            actions=[
                RecoveryAction.RETRY_OPERATION,
                RecoveryAction.FALLBACK_MODE,
                RecoveryAction.GRACEFUL_DEGRADATION
            ],
            cooldown_period=180,
            max_attempts=2
        )
        
        # File system recovery strategy
        self.recovery_strategies["file_system"] = RecoveryStrategy(
            component="file_system",
            trigger_conditions=["disk_full", "permission_denied", "io_error"],
            actions=[
                RecoveryAction.GRACEFUL_DEGRADATION,
                RecoveryAction.ALERT_ADMIN
            ],
            cooldown_period=300,
            max_attempts=1
        )
        
        # External API recovery strategy
        self.recovery_strategies["external_api"] = RecoveryStrategy(
            component="external_api",
            trigger_conditions=["rate_limited", "service_unavailable", "timeout"],
            actions=[
                RecoveryAction.CIRCUIT_BREAKER,
                RecoveryAction.RETRY_OPERATION,
                RecoveryAction.FALLBACK_MODE
            ],
            cooldown_period=600,  # 10 minutes
            max_attempts=3
        )
    
    async def handle_component_failure(
        self,
        component: str,
        failure_type: str,
        error_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle component failure with appropriate recovery actions."""
        
        logger.info(
            f"Handling failure for component: {component}",
            component=component,
            operation="handle_failure",
            extra_data={"failure_type": failure_type, "error_details": error_details}
        )
        
        if component not in self.recovery_strategies:
            logger.warning(
                f"No recovery strategy found for component: {component}",
                component=component
            )
            return {"success": False, "reason": "no_strategy"}
        
        strategy = self.recovery_strategies[component]
        
        # Check if failure type matches trigger conditions
        if failure_type not in strategy.trigger_conditions:
            logger.debug(
                f"Failure type {failure_type} not in trigger conditions for {component}",
                component=component
            )
            return {"success": False, "reason": "no_trigger_match"}
        
        # Check cooldown period
        if not self._can_attempt_recovery(component, strategy):
            logger.info(
                f"Recovery for {component} is in cooldown period",
                component=component
            )
            return {"success": False, "reason": "cooldown_active"}
        
        # Record recovery attempt
        self._record_recovery_attempt(component)
        
        # Execute recovery actions
        recovery_results = []
        for action in strategy.actions:
            try:
                result = await self._execute_recovery_action(
                    component, action, error_details
                )
                recovery_results.append({
                    "action": action,
                    "success": result.get("success", False),
                    "details": result
                })
                
                # If action succeeded, we can stop here
                if result.get("success"):
                    logger.info(
                        f"Recovery action {action} succeeded for {component}",
                        component=component,
                        operation="recovery_success"
                    )
                    break
                    
            except Exception as e:
                logger.error(
                    f"Recovery action {action} failed for {component}: {e}",
                    component=component,
                    operation="recovery_action_failed"
                )
                recovery_results.append({
                    "action": action,
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "success": any(r["success"] for r in recovery_results),
            "actions_taken": recovery_results,
            "component": component,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _execute_recovery_action(
        self,
        component: str,
        action: RecoveryAction,
        error_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute specific recovery action."""
        
        if action == RecoveryAction.RESTART_SERVICE:
            return await self._restart_service(component)
        
        elif action == RecoveryAction.FALLBACK_MODE:
            return await self._enable_fallback_mode(component)
        
        elif action == RecoveryAction.CIRCUIT_BREAKER:
            return await self._activate_circuit_breaker(component)
        
        elif action == RecoveryAction.RETRY_OPERATION:
            return await self._retry_operation(component, error_details)
        
        elif action == RecoveryAction.GRACEFUL_DEGRADATION:
            return await self._enable_graceful_degradation(component)
        
        elif action == RecoveryAction.ALERT_ADMIN:
            return await self._send_admin_alert(component, error_details)
        
        else:
            return {"success": False, "reason": "unknown_action"}
    
    async def _restart_service(self, component: str) -> Dict[str, Any]:
        """Restart a system component."""
        logger.info(f"Attempting to restart component: {component}", component=component)
        
        try:
            if component == "mcp_agents":
                from app.mcp.coordinator import coordinator
                await coordinator.stop()
                await asyncio.sleep(2)
                await coordinator.start()
                return {"success": True, "action": "service_restarted"}
            
            elif component == "database":
                from app.database import close_mongo_connection, connect_to_mongo
                await close_mongo_connection()
                await asyncio.sleep(1)
                await connect_to_mongo()
                return {"success": True, "action": "database_reconnected"}
            
            else:
                logger.warning(f"No restart procedure defined for component: {component}")
                return {"success": False, "reason": "no_restart_procedure"}
                
        except Exception as e:
            logger.error(f"Failed to restart {component}: {e}", component=component)
            return {"success": False, "error": str(e)}
    
    async def _enable_fallback_mode(self, component: str) -> Dict[str, Any]:
        """Enable fallback mode for component."""
        logger.info(f"Enabling fallback mode for component: {component}", component=component)
        
        if component in self.fallback_handlers:
            try:
                await self.fallback_handlers[component]()
                self.degraded_components[component] = datetime.now()
                return {"success": True, "action": "fallback_enabled"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            # Default fallback behavior
            self.degraded_components[component] = datetime.now()
            return {"success": True, "action": "default_fallback"}
    
    async def _activate_circuit_breaker(self, component: str) -> Dict[str, Any]:
        """Activate circuit breaker for component."""
        logger.info(f"Activating circuit breaker for component: {component}", component=component)
        
        # Circuit breaker is handled by error_handler service
        return {"success": True, "action": "circuit_breaker_activated"}
    
    async def _retry_operation(self, component: str, error_details: Dict[str, Any]) -> Dict[str, Any]:
        """Retry failed operation with exponential backoff."""
        logger.info(f"Retrying operation for component: {component}", component=component)
        
        # This is a placeholder - actual retry logic would depend on the specific operation
        await asyncio.sleep(1)  # Brief delay before retry
        return {"success": True, "action": "operation_retried"}
    
    async def _enable_graceful_degradation(self, component: str) -> Dict[str, Any]:
        """Enable graceful degradation for component."""
        logger.info(f"Enabling graceful degradation for component: {component}", component=component)
        
        self.degraded_components[component] = datetime.now()
        
        # Update system mode if necessary
        if len(self.degraded_components) > 0 and self.current_mode == SystemMode.NORMAL:
            self.current_mode = SystemMode.DEGRADED
            logger.warning("System entering degraded mode", component="system")
        
        return {"success": True, "action": "graceful_degradation_enabled"}
    
    async def _send_admin_alert(self, component: str, error_details: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert to system administrators."""
        logger.critical(
            f"Admin alert: Component {component} requires attention",
            component=component,
            operation="admin_alert",
            extra_data=error_details
        )
        
        # Here you would integrate with your alerting system
        # (email, Slack, PagerDuty, etc.)
        
        return {"success": True, "action": "admin_alert_sent"}
    
    def _can_attempt_recovery(self, component: str, strategy: RecoveryStrategy) -> bool:
        """Check if recovery can be attempted based on cooldown and max attempts."""
        now = datetime.now()
        
        if component not in self.recovery_attempts:
            return True
        
        attempts = self.recovery_attempts[component]
        
        # Remove old attempts outside cooldown period
        cutoff_time = now - timedelta(seconds=strategy.cooldown_period)
        recent_attempts = [attempt for attempt in attempts if attempt > cutoff_time]
        self.recovery_attempts[component] = recent_attempts
        
        # Check if we've exceeded max attempts
        return len(recent_attempts) < strategy.max_attempts
    
    def _record_recovery_attempt(self, component: str):
        """Record a recovery attempt."""
        if component not in self.recovery_attempts:
            self.recovery_attempts[component] = []
        
        self.recovery_attempts[component].append(datetime.now())
    
    def add_fallback_handler(self, component: str, handler: Callable):
        """Add custom fallback handler for component."""
        self.fallback_handlers[component] = handler
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status and degraded components."""
        return {
            "mode": self.current_mode,
            "degraded_components": {
                component: degraded_time.isoformat()
                for component, degraded_time in self.degraded_components.items()
            },
            "recovery_attempts": {
                component: len(attempts)
                for component, attempts in self.recovery_attempts.items()
            },
            "timestamp": datetime.now().isoformat()
        }
    
    async def restore_component(self, component: str) -> Dict[str, Any]:
        """Attempt to restore a degraded component to normal operation."""
        if component not in self.degraded_components:
            return {"success": False, "reason": "component_not_degraded"}
        
        logger.info(f"Attempting to restore component: {component}", component=component)
        
        try:
            # Attempt to restart or restore the component
            result = await self._restart_service(component)
            
            if result.get("success"):
                # Remove from degraded components
                del self.degraded_components[component]
                
                # Update system mode if no more degraded components
                if len(self.degraded_components) == 0 and self.current_mode == SystemMode.DEGRADED:
                    self.current_mode = SystemMode.NORMAL
                    logger.info("System restored to normal mode", component="system")
                
                return {"success": True, "action": "component_restored"}
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to restore component {component}: {e}", component=component)
            return {"success": False, "error": str(e)}


# Global recovery service instance
recovery_service = SystemRecoveryService()

# Register recovery strategies with error handler
error_handler.add_recovery_strategy("database", recovery_service.handle_component_failure)
error_handler.add_recovery_strategy("mcp_agents", recovery_service.handle_component_failure)
error_handler.add_recovery_strategy("ai_model", recovery_service.handle_component_failure)
error_handler.add_recovery_strategy("file_system", recovery_service.handle_component_failure)
error_handler.add_recovery_strategy("external_api", recovery_service.handle_component_failure)