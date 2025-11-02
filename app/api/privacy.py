"""Privacy and data management API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any
from bson import ObjectId
from pathlib import Path
import logging

from app.services.privacy_service import privacy_service
from app.services.backup_service import backup_service
from app.repositories.user_repository import UserRepository
from app.database_utils import NotFoundError

logger = logging.getLogger(__name__)

router = APIRouter()
user_repo = UserRepository()


# Request/Response Models

class DataExportRequest(BaseModel):
    """Request model for data export."""
    user_id: str = Field(..., description="User ID to export data for")
    format: str = Field(default="json", description="Export format (json or csv)")
    include_files: bool = Field(default=True, description="Include resume files in export")


class DataExportResponse(BaseModel):
    """Response model for data export."""
    user_id: str
    export_format: str
    export_timestamp: str
    zip_file_path: str
    files_included: list[str]
    include_files: bool
    total_records: int


class DataDeletionRequest(BaseModel):
    """Request model for data deletion."""
    user_id: str = Field(..., description="User ID to delete data for")
    confirmation_email: EmailStr = Field(..., description="User email for confirmation")
    delete_files: bool = Field(default=True, description="Delete associated files")


class DataDeletionResponse(BaseModel):
    """Response model for data deletion."""
    user_id: str
    deletion_timestamp: str
    deleted_records: Dict[str, int]
    deleted_files: list[str]
    errors: list[str]


class BackupRequest(BaseModel):
    """Request model for backup creation."""
    backup_name: Optional[str] = Field(None, description="Custom backup name")
    backup_type: str = Field(default="full", description="Backup type (full or collection)")
    collection_name: Optional[str] = Field(None, description="Collection name for collection backup")


class BackupResponse(BaseModel):
    """Response model for backup operations."""
    backup_name: str
    backup_type: str
    database_name: str
    created_at: str
    backup_path: str
    backup_size_bytes: int


class RestoreRequest(BaseModel):
    """Request model for backup restore."""
    backup_name: str = Field(..., description="Name of backup to restore")
    drop_existing: bool = Field(default=False, description="Drop existing collections before restore")


# Helper Functions

async def get_user_or_404(user_id: str):
    """Get user by ID or raise 404."""
    try:
        user = await user_repo.get_by_id(ObjectId(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid user ID")


# Data Export Endpoints

@router.post("/export", response_model=DataExportResponse)
async def export_user_data(
    request: DataExportRequest,
    background_tasks: BackgroundTasks
):
    """
    Export all user data in specified format.
    
    This endpoint creates a comprehensive export of all user data including:
    - User profile information
    - Job listings and search history
    - Application records and status
    - Resume versions and optimization history
    - Associated files (if requested)
    
    The export is created as a ZIP file containing the data in the requested format.
    """
    try:
        # Verify user exists
        await get_user_or_404(request.user_id)
        
        # Validate export format
        if request.format.lower() not in ["json", "csv"]:
            raise HTTPException(
                status_code=400, 
                detail="Invalid export format. Must be 'json' or 'csv'"
            )
        
        logger.info(f"Starting data export for user {request.user_id}")
        
        # Create export (this may take some time for large datasets)
        export_result = await privacy_service.export_user_data(
            user_id=request.user_id,
            format=request.format,
            include_files=request.include_files
        )
        
        return DataExportResponse(**export_result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting user data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export user data")


@router.get("/export/{user_id}/download")
async def download_user_export(
    user_id: str,
    export_timestamp: str = Query(..., description="Export timestamp from export response")
):
    """
    Download the exported user data ZIP file.
    
    Use the export_timestamp from the export response to download the specific export.
    """
    try:
        # Verify user exists
        await get_user_or_404(user_id)
        
        # Construct expected file path
        export_filename = f"user_{user_id}_{export_timestamp}.zip"
        export_path = Path(privacy_service.export_dir) / export_filename
        
        if not export_path.exists():
            raise HTTPException(status_code=404, detail="Export file not found")
        
        return FileResponse(
            path=str(export_path),
            filename=export_filename,
            media_type="application/zip"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading export: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download export")


# Data Deletion Endpoints

@router.post("/delete", response_model=DataDeletionResponse)
async def delete_user_data(request: DataDeletionRequest):
    """
    Permanently delete all user data with email confirmation.
    
    This endpoint permanently deletes:
    - User profile and account information
    - All job listings and search history
    - All application records and status
    - All resume versions and files
    - Associated files and directories
    
    **WARNING: This action is irreversible!**
    
    Requires email confirmation to prevent accidental deletion.
    """
    try:
        # Verify user exists and get user data for confirmation
        user = await get_user_or_404(request.user_id)
        
        logger.info(f"Starting data deletion for user {request.user_id}")
        
        # Delete user data with confirmation
        deletion_result = await privacy_service.delete_user_data(
            user_id=request.user_id,
            confirmation_token=request.confirmation_email,
            delete_files=request.delete_files
        )
        
        return DataDeletionResponse(**deletion_result)
        
    except ValueError as e:
        # This catches confirmation token validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete user data")


# Backup Management Endpoints

@router.post("/backup", response_model=BackupResponse)
async def create_backup(request: BackupRequest):
    """
    Create a database backup.
    
    Supports two types of backups:
    - full: Complete database backup (all collections)
    - collection: Backup of a specific collection
    
    Requires MongoDB tools (mongodump) to be installed and accessible.
    """
    try:
        if request.backup_type == "full":
            backup_result = await backup_service.create_full_backup(
                backup_name=request.backup_name
            )
        elif request.backup_type == "collection":
            if not request.collection_name:
                raise HTTPException(
                    status_code=400,
                    detail="collection_name is required for collection backup"
                )
            backup_result = await backup_service.create_collection_backup(
                collection_name=request.collection_name,
                backup_name=request.backup_name
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid backup_type. Must be 'full' or 'collection'"
            )
        
        return BackupResponse(**backup_result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating backup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create backup: {str(e)}")


@router.get("/backups")
async def list_backups():
    """
    List all available database backups with metadata.
    
    Returns information about all backups including:
    - Backup name and type
    - Creation timestamp
    - Size and collections included
    """
    try:
        backups = await backup_service.list_backups()
        return {"backups": backups}
        
    except Exception as e:
        logger.error(f"Error listing backups: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list backups")


@router.post("/restore")
async def restore_backup(request: RestoreRequest):
    """
    Restore database from backup.
    
    **WARNING: This will overwrite existing data!**
    
    Use drop_existing=True to completely replace existing collections.
    Use drop_existing=False to merge with existing data (may cause duplicates).
    
    Requires MongoDB tools (mongorestore) to be installed and accessible.
    """
    try:
        restore_result = await backup_service.restore_backup(
            backup_name=request.backup_name,
            drop_existing=request.drop_existing
        )
        
        return {
            "message": "Backup restored successfully",
            "restore_details": restore_result
        }
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error restoring backup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to restore backup: {str(e)}")


@router.delete("/backups/{backup_name}")
async def delete_backup(backup_name: str):
    """
    Delete a specific backup.
    
    Permanently removes the backup directory and all its contents.
    """
    try:
        success = await backup_service.delete_backup(backup_name)
        
        if success:
            return {"message": f"Backup '{backup_name}' deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Backup not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting backup: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete backup")


@router.post("/backups/cleanup")
async def cleanup_old_backups(keep_count: int = Query(10, ge=1, le=100)):
    """
    Clean up old backups, keeping only the specified number of most recent ones.
    
    This helps manage disk space by automatically removing older backups.
    """
    try:
        cleanup_result = await backup_service.cleanup_old_backups(keep_count=keep_count)
        
        return {
            "message": f"Backup cleanup completed. Kept {cleanup_result['kept_count']} backups.",
            "cleanup_details": cleanup_result
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up backups: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cleanup backups")


# Health Check Endpoints

@router.get("/health")
async def privacy_health_check():
    """
    Health check for privacy and backup services.
    
    Verifies that required directories exist and MongoDB tools are available.
    """
    try:
        health_status = {
            "privacy_service": "healthy",
            "backup_service": "healthy",
            "export_directory": str(privacy_service.export_dir),
            "backup_directory": str(backup_service.backup_dir),
            "mongodb_tools_available": False
        }
        
        # Check if MongoDB tools are available
        import subprocess
        try:
            subprocess.run(["mongodump", "--version"], 
                         capture_output=True, check=True, timeout=5)
            health_status["mongodb_tools_available"] = True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            health_status["mongodb_tools_available"] = False
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error in privacy health check: {str(e)}")
        raise HTTPException(status_code=500, detail="Health check failed")