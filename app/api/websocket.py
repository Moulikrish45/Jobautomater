"""WebSocket endpoints for real-time updates and notifications."""

import json
import asyncio
from typing import Dict, Set, Optional, Any
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from pydantic import BaseModel
import logging
from fastapi import Query
from app.models.application import Application, ApplicationStatus
from app.models.job import Job, JobStatus
from app.repositories.application_repository import ApplicationRepository
from app.repositories.job_repository import JobRepository

logger = logging.getLogger(__name__)

router = APIRouter()

async def get_current_user(token: str = Query(...)):
    return await get_current_user(token)
    


class NotificationMessage(BaseModel):
    """WebSocket notification message structure."""
    type: str  # 'application_update', 'job_discovered', 'system_error', 'progress_update'
    user_id: str
    timestamp: datetime
    data: Dict[str, Any]
    message: Optional[str] = None


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        # Store active connections by user_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        self.active_connections[user_id].add(websocket)
        self.connection_metadata[websocket] = {
            "user_id": user_id,
            "connected_at": datetime.utcnow(),
            "last_ping": datetime.utcnow()
        }
        
        logger.info(f"WebSocket connected for user {user_id}")
        
        # Send connection confirmation
        await self.send_to_connection(websocket, {
            "type": "connection_established",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "WebSocket connection established"
        })
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.connection_metadata:
            user_id = self.connection_metadata[websocket]["user_id"]
            
            # Remove from active connections
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                
                # Clean up empty user connection sets
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            
            # Remove metadata
            del self.connection_metadata[websocket]
            
            logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        """Send message to all connections for a specific user."""
        if user_id not in self.active_connections:
            return
        
        # Create a copy of the set to avoid modification during iteration
        connections = self.active_connections[user_id].copy()
        
        for websocket in connections:
            try:
                await self.send_to_connection(websocket, message)
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
                # Remove failed connection
                self.disconnect(websocket)
    
    async def send_to_connection(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send message to a specific WebSocket connection."""
        try:
            await websocket.send_text(json.dumps(message, default=str))
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            raise
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Broadcast message to all connected users."""
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, message)
    
    def get_user_connection_count(self, user_id: str) -> int:
        """Get number of active connections for a user."""
        return len(self.active_connections.get(user_id, set()))
    
    def get_total_connections(self) -> int:
        """Get total number of active connections."""
        return sum(len(connections) for connections in self.active_connections.values())
    
    async def ping_all_connections(self):
        """Send ping to all connections to keep them alive."""
        ping_message = {
            "type": "ping",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for user_id in list(self.active_connections.keys()):
            connections = self.active_connections[user_id].copy()
            for websocket in connections:
                try:
                    await self.send_to_connection(websocket, ping_message)
                    # Update last ping time
                    if websocket in self.connection_metadata:
                        self.connection_metadata[websocket]["last_ping"] = datetime.utcnow()
                except Exception:
                    # Remove failed connection
                    self.disconnect(websocket)


# Global connection manager instance
manager = ConnectionManager()


class NotificationService:
    """Service for sending real-time notifications."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.manager = connection_manager
    
    async def notify_application_update(self, user_id: str, application: Application, 
                                      job: Optional[Job] = None):
        """Notify user of application status update."""
        message = NotificationMessage(
            type="application_update",
            user_id=user_id,
            timestamp=datetime.utcnow(),
            data={
                "application_id": str(application.id),
                "job_id": str(application.job_id),
                "status": application.status,
                "outcome": application.outcome,
                "job_title": job.title if job else None,
                "company_name": job.company.name if job else None,
                "total_attempts": application.total_attempts
            },
            message=f"Application status updated to {application.status}"
        )
        
        await self.manager.send_to_user(user_id, message.dict())
    
    async def notify_job_discovered(self, user_id: str, job: Job):
        """Notify user of new job discovery."""
        message = NotificationMessage(
            type="job_discovered",
            user_id=user_id,
            timestamp=datetime.utcnow(),
            data={
                "job_id": str(job.id),
                "title": job.title,
                "company": job.company.name,
                "portal": job.portal,
                "match_score": job.match_score,
                "location": job.location.dict()
            },
            message=f"New job discovered: {job.title} at {job.company.name}"
        )
        
        await self.manager.send_to_user(user_id, message.dict())
    
    async def notify_system_error(self, user_id: str, error_type: str, 
                                error_message: str, context: Optional[Dict[str, Any]] = None):
        """Notify user of system errors."""
        message = NotificationMessage(
            type="system_error",
            user_id=user_id,
            timestamp=datetime.utcnow(),
            data={
                "error_type": error_type,
                "error_message": error_message,
                "context": context or {}
            },
            message=f"System error: {error_message}"
        )
        
        await self.manager.send_to_user(user_id, message.dict())
    
    async def notify_progress_update(self, user_id: str, operation: str, 
                                   progress: float, details: Optional[str] = None):
        """Notify user of operation progress."""
        message = NotificationMessage(
            type="progress_update",
            user_id=user_id,
            timestamp=datetime.utcnow(),
            data={
                "operation": operation,
                "progress": progress,  # 0.0 to 1.0
                "details": details
            },
            message=f"{operation}: {int(progress * 100)}% complete"
        )
        
        await self.manager.send_to_user(user_id, message.dict())
    
    async def notify_automation_status(self, user_id: str, enabled: bool, reason: Optional[str] = None):
        """Notify user of automation status changes."""
        message = NotificationMessage(
            type="automation_status",
            user_id=user_id,
            timestamp=datetime.utcnow(),
            data={
                "enabled": enabled,
                "reason": reason
            },
            message=f"Automation {'enabled' if enabled else 'disabled'}"
        )
        
        await self.manager.send_to_user(user_id, message.dict())


# Global notification service instance
notification_service = NotificationService(manager)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    current_user: User = Depends(get_current_user_ws)
):
    user_id = str(current_user.id)
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                try:
                    message = json.loads(data)
                    await handle_client_message(websocket, user_id, message)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received from user {user_id}")
                
            except asyncio.TimeoutError:
                await manager.send_to_connection(websocket, {
                    "type": "ping",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
    finally:
        manager.disconnect(websocket)


async def handle_client_message(websocket: WebSocket, user_id: str, message: Dict[str, Any]):
    """Handle messages received from WebSocket clients."""
    message_type = message.get("type")
    
    if message_type == "pong":
        # Update last ping time
        if websocket in manager.connection_metadata:
            manager.connection_metadata[websocket]["last_ping"] = datetime.utcnow()
    
    elif message_type == "subscribe":
        # Handle subscription to specific event types
        event_types = message.get("events", [])
        if websocket in manager.connection_metadata:
            manager.connection_metadata[websocket]["subscribed_events"] = event_types
        
        await manager.send_to_connection(websocket, {
            "type": "subscription_confirmed",
            "events": event_types,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    elif message_type == "get_status":
        # Send current system status
        await send_system_status(websocket, user_id)
    
    else:
        logger.warning(f"Unknown message type from user {user_id}: {message_type}")


async def send_system_status(websocket: WebSocket, user_id: str):
    """Send current system status to client."""
    # TODO: Get actual system status from services
    status = {
        "type": "system_status",
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "automation_enabled": True,  # Get from user settings
            "agents_status": {
                "job_search": "active",
                "resume_builder": "active", 
                "application": "active"
            },
            "queue_status": {
                "jobs_queued": 0,  # Get from job repository
                "applications_pending": 0  # Get from application repository
            },
            "last_activity": datetime.utcnow().isoformat()
        }
    }
    
    await manager.send_to_connection(websocket, status)


@router.get("/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
    return {
        "total_connections": manager.get_total_connections(),
        "users_connected": len(manager.active_connections),
        "connections_by_user": {
            user_id: len(connections) 
            for user_id, connections in manager.active_connections.items()
        }
    }


# Background task to keep connections alive
async def websocket_keepalive():
    """Background task to ping all WebSocket connections."""
    while True:
        try:
            await manager.ping_all_connections()
            await asyncio.sleep(30)  # Ping every 30 seconds
        except Exception as e:
            logger.error(f"WebSocket keepalive error: {e}")
            await asyncio.sleep(5)


# Export the notification service for use in other modules
__all__ = ["router", "notification_service", "manager", "websocket_keepalive"]