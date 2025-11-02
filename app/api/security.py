"""Security management API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging

from app.services.security_service import security_service
from app.services.audit_service import audit_service, AuditEventType, AuditSeverity
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter()
user_repo = UserRepository()


# Request/Response Models

class CredentialRequest(BaseModel):
    """Request model for storing credentials."""
    service_name: str = Field(..., description="Name of the service")
    credentials: Dict[str, Any] = Field(..., description="Credential data")


class CredentialResponse(BaseModel):
    """Response model for credential operations."""
    service_name: str
    success: bool
    message: str


class EncryptionRequest(BaseModel):
    """Request model for data encryption."""
    data: str = Field(..., description="Data to encrypt")


class EncryptionResponse(BaseModel):
    """Response model for encryption operations."""
    encrypted_data: str
    success: bool


class DecryptionRequest(BaseModel):
    """Request model for data decryption."""
    encrypted_data: str = Field(..., description="Data to decrypt")


class DecryptionResponse(BaseModel):
    """Response model for decryption operations."""
    decrypted_data: str
    success: bool


class AuditLogResponse(BaseModel):
    """Response model for audit logs."""
    logs: List[Dict[str, Any]]
    total_count: int


class ActivitySummaryResponse(BaseModel):
    """Response model for user activity summary."""
    user_id: str
    period_days: int
    total_events: int
    event_types: Dict[str, int]
    severity_breakdown: Dict[str, int]
    daily_activity: Dict[str, int]
    recent_events: List[Dict[str, Any]]


# Credential Management Endpoints

@router.post("/credentials", response_model=CredentialResponse)
async def store_credentials(request: CredentialRequest):
    """
    Store encrypted credentials for a service.
    
    Credentials are encrypted using Fernet symmetric encryption and stored securely.
    This endpoint is used to store authentication credentials for job portals.
    """
    try:
        success = security_service.store_credentials(
            service_name=request.service_name,
            credentials=request.credentials
        )
        
        if success:
            return CredentialResponse(
                service_name=request.service_name,
                success=True,
                message="Credentials stored successfully"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to store credentials")
            
    except Exception as e:
        logger.error(f"Error storing credentials: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to store credentials")


@router.get("/credentials/{service_name}")
async def retrieve_credentials(service_name: str):
    """
    Retrieve and decrypt credentials for a service.
    
    **Warning: This endpoint returns decrypted credentials. Use with caution.**
    """
    try:
        credentials = security_service.retrieve_credentials(service_name)
        
        if credentials is None:
            raise HTTPException(status_code=404, detail="Credentials not found")
        
        return {
            "service_name": service_name,
            "credentials": credentials,
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving credentials: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve credentials")


@router.put("/credentials/{service_name}", response_model=CredentialResponse)
async def update_credentials(service_name: str, request: CredentialRequest):
    """
    Update existing credentials for a service.
    
    This will replace the existing credentials with new ones.
    """
    try:
        success = security_service.update_credentials(
            service_name=service_name,
            credentials=request.credentials
        )
        
        if success:
            return CredentialResponse(
                service_name=service_name,
                success=True,
                message="Credentials updated successfully"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to update credentials")
            
    except Exception as e:
        logger.error(f"Error updating credentials: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update credentials")


@router.delete("/credentials/{service_name}", response_model=CredentialResponse)
async def delete_credentials(service_name: str):
    """
    Delete stored credentials for a service.
    
    **Warning: This action is irreversible.**
    """
    try:
        success = security_service.delete_credentials(service_name)
        
        if success:
            return CredentialResponse(
                service_name=service_name,
                success=True,
                message="Credentials deleted successfully"
            )
        else:
            raise HTTPException(status_code=404, detail="Credentials not found")
            
    except Exception as e:
        logger.error(f"Error deleting credentials: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete credentials")


@router.get("/credentials")
async def list_stored_services():
    """
    List all services that have stored credentials.
    
    Returns only the service names, not the actual credentials.
    """
    try:
        services = security_service.list_stored_services()
        return {
            "services": services,
            "count": len(services)
        }
        
    except Exception as e:
        logger.error(f"Error listing services: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list services")


# Encryption Endpoints

@router.post("/encrypt", response_model=EncryptionResponse)
async def encrypt_data(request: EncryptionRequest):
    """
    Encrypt arbitrary data using the system's encryption key.
    
    This can be used to encrypt sensitive data before storing it.
    """
    try:
        encrypted_data = security_service.encrypt_data(request.data)
        
        return EncryptionResponse(
            encrypted_data=encrypted_data,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error encrypting data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to encrypt data")


@router.post("/decrypt", response_model=DecryptionResponse)
async def decrypt_data(request: DecryptionRequest):
    """
    Decrypt data using the system's encryption key.
    
    **Warning: This endpoint returns decrypted data. Use with caution.**
    """
    try:
        decrypted_data = security_service.decrypt_data(
            request.encrypted_data, 
            return_type="string"
        )
        
        return DecryptionResponse(
            decrypted_data=decrypted_data,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error decrypting data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to decrypt data")


# Key Management Endpoints

@router.post("/rotate-key")
async def rotate_encryption_key():
    """
    Rotate the system encryption key.
    
    This will generate a new encryption key and re-encrypt all stored credentials.
    **Warning: This is a critical operation that affects all encrypted data.**
    """
    try:
        success = security_service.rotate_encryption_key()
        
        if success:
            return {
                "success": True,
                "message": "Encryption key rotated successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Key rotation failed")
            
    except Exception as e:
        logger.error(f"Error rotating encryption key: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to rotate encryption key")


@router.post("/generate-api-key")
async def generate_api_key(length: int = Query(32, ge=16, le=64)):
    """
    Generate a secure random API key.
    
    This can be used to generate API keys for external integrations.
    """
    try:
        api_key = security_service.generate_api_key(length=length)
        
        return {
            "api_key": api_key,
            "length": length,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error generating API key: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate API key")


# Audit Log Endpoints

@router.get("/audit/logs", response_model=AuditLogResponse)
async def get_audit_logs(
    start_date: Optional[datetime] = Query(None, description="Start date for log retrieval"),
    end_date: Optional[datetime] = Query(None, description="End date for log retrieval"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs to return")
):
    """
    Retrieve audit logs with optional filtering.
    
    This endpoint provides access to the system's audit trail for security monitoring
    and compliance purposes.
    """
    try:
        # Convert string parameters to enums if provided
        event_type_enum = None
        if event_type:
            try:
                event_type_enum = AuditEventType(event_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid event_type: {event_type}")
        
        severity_enum = None
        if severity:
            try:
                severity_enum = AuditSeverity(severity)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")
        
        logs = await audit_service.get_audit_logs(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            event_type=event_type_enum,
            severity=severity_enum,
            limit=limit
        )
        
        return AuditLogResponse(
            logs=logs,
            total_count=len(logs)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving audit logs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit logs")


@router.get("/audit/activity/{user_id}", response_model=ActivitySummaryResponse)
async def get_user_activity_summary(
    user_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back")
):
    """
    Get activity summary for a specific user.
    
    This provides an overview of a user's activity including event counts,
    severity breakdown, and recent events.
    """
    try:
        # Verify user exists
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        activity_summary = await audit_service.get_user_activity_summary(
            user_id=user_id,
            days=days
        )
        
        return ActivitySummaryResponse(**activity_summary)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user activity summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get activity summary")


@router.get("/audit/events/types")
async def get_audit_event_types():
    """
    Get list of all available audit event types.
    
    This is useful for filtering audit logs by event type.
    """
    try:
        event_types = [event_type.value for event_type in AuditEventType]
        severities = [severity.value for severity in AuditSeverity]
        
        return {
            "event_types": event_types,
            "severities": severities
        }
        
    except Exception as e:
        logger.error(f"Error getting audit event types: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get event types")


# Security Health Check

@router.get("/health")
async def security_health_check():
    """
    Health check for security services.
    
    Verifies that encryption is working and credential storage is accessible.
    """
    try:
        health_status = {
            "security_service": "healthy",
            "audit_service": "healthy",
            "encryption_available": False,
            "credentials_directory": str(security_service.credentials_dir),
            "stored_services_count": 0
        }
        
        # Test encryption
        try:
            test_data = "health_check_test"
            encrypted = security_service.encrypt_data(test_data)
            decrypted = security_service.decrypt_data(encrypted, return_type="string")
            health_status["encryption_available"] = (decrypted == test_data)
        except Exception:
            health_status["encryption_available"] = False
        
        # Count stored services
        try:
            services = security_service.list_stored_services()
            health_status["stored_services_count"] = len(services)
        except Exception:
            health_status["stored_services_count"] = 0
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error in security health check: {str(e)}")
        raise HTTPException(status_code=500, detail="Health check failed")