"""Privacy and data management service for user data export and deletion."""

import asyncio
import json
import csv
import zipfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from io import StringIO, BytesIO
from bson import ObjectId
import pandas as pd

from app.models.user import User
from app.models.job import Job
from app.models.application import Application
from app.models.resume import Resume
from app.repositories.user_repository import UserRepository
from app.repositories.job_repository import JobRepository
from app.repositories.application_repository import ApplicationRepository
from app.repositories.resume_repository import ResumeRepository
from app.database_utils import handle_db_errors, NotFoundError
from app.config import settings
from app.services.audit_service import audit_service, AuditEventType, AuditSeverity

import logging

logger = logging.getLogger(__name__)


class PrivacyService:
    """Service for handling user data privacy operations."""
    
    def __init__(self):
        self.user_repo = UserRepository()
        self.job_repo = JobRepository()
        self.application_repo = ApplicationRepository()
        self.resume_repo = ResumeRepository()
        self.export_dir = Path(settings.data_dir) / "exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    @handle_db_errors
    async def export_user_data(self, 
                              user_id: Union[str, ObjectId],
                              format: str = "json",
                              include_files: bool = True) -> Dict[str, Any]:
        """
        Export all user data in specified format.
        
        Args:
            user_id: User ID to export data for
            format: Export format ('json' or 'csv')
            include_files: Whether to include resume files in export
            
        Returns:
            Dict containing export metadata and file paths
        """
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        logger.info(f"Starting data export for user {user_id} in {format} format")
        
        # Verify user exists
        user = await self.user_repo.get_by_id_or_raise(user_id)
        
        # Create export directory for this user
        export_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        user_export_dir = self.export_dir / f"user_{user_id}_{export_timestamp}"
        user_export_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Collect all user data
            user_data = await self._collect_user_data(user_id)
            
            # Export in requested format
            if format.lower() == "json":
                export_files = await self._export_as_json(user_data, user_export_dir)
            elif format.lower() == "csv":
                export_files = await self._export_as_csv(user_data, user_export_dir)
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            # Include resume files if requested
            if include_files:
                files_copied = await self._copy_user_files(user_id, user_export_dir)
                export_files.update(files_copied)
            
            # Create ZIP archive
            zip_path = await self._create_zip_archive(user_export_dir)
            
            # Clean up temporary directory
            shutil.rmtree(user_export_dir)
            
            logger.info(f"Data export completed for user {user_id}")
            
            # Log audit event
            audit_service.log_data_event(
                event_type=AuditEventType.DATA_EXPORTED,
                user_id=user_id,
                action="export_user_data",
                data_type=format,
                details={
                    "export_format": format,
                    "include_files": include_files,
                    "total_records": sum(len(data) if isinstance(data, list) else 1 
                                       for data in user_data.values()),
                    "zip_file_size_bytes": zip_path.stat().st_size if zip_path.exists() else 0
                },
                severity=AuditSeverity.MEDIUM
            )
            
            return {
                "user_id": str(user_id),
                "export_format": format,
                "export_timestamp": export_timestamp,
                "zip_file_path": str(zip_path),
                "files_included": list(export_files.keys()),
                "include_files": include_files,
                "total_records": sum(len(data) if isinstance(data, list) else 1 
                                   for data in user_data.values())
            }
            
        except Exception as e:
            # Clean up on error
            if user_export_dir.exists():
                shutil.rmtree(user_export_dir)
            logger.error(f"Error during data export for user {user_id}: {str(e)}")
            raise
    
    @handle_db_errors
    async def delete_user_data(self, 
                              user_id: Union[str, ObjectId],
                              confirmation_token: str,
                              delete_files: bool = True) -> Dict[str, Any]:
        """
        Permanently delete all user data with confirmation.
        
        Args:
            user_id: User ID to delete data for
            confirmation_token: Confirmation token (should be user email or special token)
            delete_files: Whether to delete associated files
            
        Returns:
            Dict containing deletion summary
        """
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        logger.info(f"Starting data deletion for user {user_id}")
        
        # Verify user exists and confirmation
        user = await self.user_repo.get_by_id_or_raise(user_id)
        
        # Validate confirmation token (should be user email)
        if confirmation_token != user.personal_info.email:
            raise ValueError("Invalid confirmation token")
        
        deletion_summary = {
            "user_id": str(user_id),
            "deletion_timestamp": datetime.utcnow().isoformat(),
            "deleted_records": {},
            "deleted_files": [],
            "errors": []
        }
        
        try:
            # Delete in reverse dependency order to avoid foreign key issues
            
            # 1. Delete applications
            applications = await self.application_repo.find_all({"user_id": user_id})
            app_count = len(applications)
            if app_count > 0:
                await self.application_repo.delete_by_filter({"user_id": user_id})
                deletion_summary["deleted_records"]["applications"] = app_count
                logger.info(f"Deleted {app_count} applications for user {user_id}")
            
            # 2. Delete resumes and associated files
            resumes = await self.resume_repo.find_all({"user_id": user_id})
            resume_count = len(resumes)
            deleted_files = []
            
            if delete_files:
                for resume in resumes:
                    if resume.file_info and resume.file_info.file_path:
                        file_path = Path(resume.file_info.file_path)
                        if file_path.exists():
                            try:
                                file_path.unlink()
                                deleted_files.append(str(file_path))
                            except Exception as e:
                                deletion_summary["errors"].append(
                                    f"Failed to delete file {file_path}: {str(e)}"
                                )
            
            if resume_count > 0:
                await self.resume_repo.delete_by_filter({"user_id": user_id})
                deletion_summary["deleted_records"]["resumes"] = resume_count
                deletion_summary["deleted_files"] = deleted_files
                logger.info(f"Deleted {resume_count} resumes for user {user_id}")
            
            # 3. Delete jobs (user-specific job records)
            jobs = await self.job_repo.find_all({"user_id": user_id})
            job_count = len(jobs)
            if job_count > 0:
                await self.job_repo.delete_by_filter({"user_id": user_id})
                deletion_summary["deleted_records"]["jobs"] = job_count
                logger.info(f"Deleted {job_count} jobs for user {user_id}")
            
            # 4. Delete user profile (last)
            await self.user_repo.delete(user_id)
            deletion_summary["deleted_records"]["user_profile"] = 1
            logger.info(f"Deleted user profile for user {user_id}")
            
            # 5. Clean up any remaining user files
            if delete_files:
                user_files_dir = Path(settings.data_dir) / "resumes" / str(user_id)
                if user_files_dir.exists():
                    try:
                        shutil.rmtree(user_files_dir)
                        deletion_summary["deleted_files"].append(str(user_files_dir))
                    except Exception as e:
                        deletion_summary["errors"].append(
                            f"Failed to delete user files directory {user_files_dir}: {str(e)}"
                        )
            
            logger.info(f"Data deletion completed for user {user_id}")
            
            # Log audit event
            audit_service.log_data_event(
                event_type=AuditEventType.DATA_DELETED,
                user_id=user_id,
                action="delete_user_data",
                data_type="all_user_data",
                details={
                    "deleted_records": deletion_summary["deleted_records"],
                    "deleted_files_count": len(deletion_summary["deleted_files"]),
                    "errors_count": len(deletion_summary["errors"])
                },
                severity=AuditSeverity.CRITICAL
            )
            
            return deletion_summary
            
        except Exception as e:
            logger.error(f"Error during data deletion for user {user_id}: {str(e)}")
            deletion_summary["errors"].append(f"Deletion failed: {str(e)}")
            raise
    
    async def _collect_user_data(self, user_id: ObjectId) -> Dict[str, Any]:
        """Collect all user data from all collections."""
        logger.info(f"Collecting user data for user {user_id}")
        
        # Collect data from all collections
        user_data = {}
        
        # User profile
        user = await self.user_repo.get_by_id(user_id)
        if user:
            user_data["user_profile"] = user.dict()
        
        # Jobs
        jobs = await self.job_repo.find_all({"user_id": user_id})
        user_data["jobs"] = [job.dict() for job in jobs]
        
        # Applications
        applications = await self.application_repo.find_all({"user_id": user_id})
        user_data["applications"] = [app.dict() for app in applications]
        
        # Resumes
        resumes = await self.resume_repo.find_all({"user_id": user_id})
        user_data["resumes"] = [resume.dict() for resume in resumes]
        
        logger.info(f"Collected data: {len(user_data['jobs'])} jobs, "
                   f"{len(user_data['applications'])} applications, "
                   f"{len(user_data['resumes'])} resumes")
        
        return user_data
    
    async def _export_as_json(self, user_data: Dict[str, Any], 
                             export_dir: Path) -> Dict[str, str]:
        """Export user data as JSON files."""
        export_files = {}
        
        for data_type, data in user_data.items():
            if data:  # Only export if data exists
                file_path = export_dir / f"{data_type}.json"
                
                # Convert ObjectId and datetime objects to strings for JSON serialization
                json_data = self._serialize_for_json(data)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
                
                export_files[data_type] = str(file_path)
        
        return export_files
    
    async def _export_as_csv(self, user_data: Dict[str, Any], 
                            export_dir: Path) -> Dict[str, str]:
        """Export user data as CSV files."""
        export_files = {}
        
        for data_type, data in user_data.items():
            if not data:
                continue
            
            file_path = export_dir / f"{data_type}.csv"
            
            try:
                if data_type == "user_profile":
                    # Flatten user profile for CSV
                    flattened_data = self._flatten_user_profile(data)
                    df = pd.DataFrame([flattened_data])
                else:
                    # Convert list of documents to DataFrame
                    flattened_records = []
                    for record in data:
                        flattened_records.append(self._flatten_dict(record))
                    df = pd.DataFrame(flattened_records)
                
                df.to_csv(file_path, index=False, encoding='utf-8')
                export_files[data_type] = str(file_path)
                
            except Exception as e:
                logger.warning(f"Failed to export {data_type} as CSV: {str(e)}")
                # Fall back to JSON for complex data
                json_file_path = export_dir / f"{data_type}.json"
                json_data = self._serialize_for_json(data)
                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
                export_files[data_type] = str(json_file_path)
        
        return export_files
    
    async def _copy_user_files(self, user_id: ObjectId, 
                              export_dir: Path) -> Dict[str, str]:
        """Copy user's resume files to export directory."""
        files_copied = {}
        
        # Get all resumes with file info
        resumes = await self.resume_repo.find_all({"user_id": user_id})
        
        files_dir = export_dir / "files"
        files_dir.mkdir(exist_ok=True)
        
        for resume in resumes:
            if resume.file_info and resume.file_info.file_path:
                source_path = Path(resume.file_info.file_path)
                if source_path.exists():
                    # Create unique filename to avoid conflicts
                    dest_filename = f"resume_{resume.id}_{resume.file_info.filename}"
                    dest_path = files_dir / dest_filename
                    
                    try:
                        shutil.copy2(source_path, dest_path)
                        files_copied[f"resume_{resume.id}"] = str(dest_path)
                    except Exception as e:
                        logger.warning(f"Failed to copy file {source_path}: {str(e)}")
        
        return files_copied
    
    async def _create_zip_archive(self, export_dir: Path) -> Path:
        """Create ZIP archive of exported data."""
        zip_path = export_dir.parent / f"{export_dir.name}.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in export_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(export_dir)
                    zipf.write(file_path, arcname)
        
        return zip_path
    
    def _serialize_for_json(self, data: Any) -> Any:
        """Recursively serialize data for JSON export."""
        if isinstance(data, dict):
            return {key: self._serialize_for_json(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._serialize_for_json(item) for item in data]
        elif isinstance(data, ObjectId):
            return str(data)
        elif isinstance(data, datetime):
            return data.isoformat()
        else:
            return data
    
    def _flatten_dict(self, data: Dict[str, Any], parent_key: str = '', 
                     sep: str = '_') -> Dict[str, Any]:
        """Flatten nested dictionary for CSV export."""
        items = []
        for key, value in data.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else key
            
            if isinstance(value, dict):
                items.extend(self._flatten_dict(value, new_key, sep=sep).items())
            elif isinstance(value, list):
                # Convert lists to comma-separated strings
                if value and isinstance(value[0], dict):
                    # For list of dicts, create separate columns
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            items.extend(
                                self._flatten_dict(item, f"{new_key}_{i}", sep=sep).items()
                            )
                        else:
                            items.append((f"{new_key}_{i}", str(item)))
                else:
                    # Simple list - join as string
                    items.append((new_key, ', '.join(str(v) for v in value)))
            else:
                items.append((new_key, str(value) if value is not None else ''))
        
        return dict(items)
    
    def _flatten_user_profile(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten user profile data specifically for CSV export."""
        flattened = {}
        
        # Basic fields
        for key in ['id', 'is_active', 'created_at', 'updated_at']:
            if key in user_data:
                flattened[key] = str(user_data[key])
        
        # Personal info
        if 'personal_info' in user_data:
            for key, value in user_data['personal_info'].items():
                flattened[f'personal_info_{key}'] = str(value) if value else ''
        
        # Skills as comma-separated
        if 'skills' in user_data:
            flattened['skills'] = ', '.join(user_data['skills'])
        
        # Experience and education as JSON strings (too complex for CSV columns)
        for key in ['experience', 'education']:
            if key in user_data and user_data[key]:
                flattened[key] = json.dumps(user_data[key])
        
        # Job preferences
        if 'preferences' in user_data and user_data['preferences']:
            prefs = user_data['preferences']
            flattened['preferences_desired_roles'] = ', '.join(prefs.get('desired_roles', []))
            flattened['preferences_locations'] = ', '.join(prefs.get('locations', []))
            flattened['preferences_work_type'] = prefs.get('work_type', '')
            if 'salary_range' in prefs:
                flattened['preferences_salary_min'] = prefs['salary_range'].get('min', '')
                flattened['preferences_salary_max'] = prefs['salary_range'].get('max', '')
        
        return flattened


# Global service instance
privacy_service = PrivacyService()