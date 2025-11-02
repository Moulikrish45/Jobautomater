"""Database backup and restore utilities using MongoDB tools."""

import asyncio
import subprocess
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

from app.config import settings
from app.database_utils import handle_db_errors

logger = logging.getLogger(__name__)


class BackupService:
    """Service for database backup and restore operations."""
    
    def __init__(self):
        self.backup_dir = Path(settings.data_dir) / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # MongoDB connection details
        self.mongo_uri = settings.mongodb_url
        self.database_name = settings.database_name
    
    @handle_db_errors
    async def create_full_backup(self, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a full database backup using mongodump.
        
        Args:
            backup_name: Optional custom backup name
            
        Returns:
            Dict containing backup metadata
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = backup_name or f"full_backup_{timestamp}"
        backup_path = self.backup_dir / backup_name
        
        logger.info(f"Starting full database backup: {backup_name}")
        
        try:
            # Create backup directory
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Run mongodump command
            cmd = [
                "mongodump",
                "--uri", self.mongo_uri,
                "--db", self.database_name,
                "--out", str(backup_path)
            ]
            
            result = await self._run_mongo_command(cmd)
            
            if result["success"]:
                # Create metadata file
                metadata = {
                    "backup_name": backup_name,
                    "backup_type": "full",
                    "database_name": self.database_name,
                    "created_at": datetime.utcnow().isoformat(),
                    "backup_path": str(backup_path),
                    "collections_backed_up": await self._get_collection_list(),
                    "backup_size_bytes": self._get_directory_size(backup_path)
                }
                
                metadata_file = backup_path / "backup_metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                logger.info(f"Full backup completed successfully: {backup_name}")
                return metadata
            else:
                raise Exception(f"Backup failed: {result['error']}")
                
        except Exception as e:
            logger.error(f"Error creating backup {backup_name}: {str(e)}")
            # Clean up failed backup
            if backup_path.exists():
                shutil.rmtree(backup_path)
            raise
    
    @handle_db_errors
    async def create_collection_backup(self, 
                                     collection_name: str,
                                     backup_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a backup of a specific collection.
        
        Args:
            collection_name: Name of collection to backup
            backup_name: Optional custom backup name
            
        Returns:
            Dict containing backup metadata
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = backup_name or f"{collection_name}_backup_{timestamp}"
        backup_path = self.backup_dir / backup_name
        
        logger.info(f"Starting collection backup: {collection_name}")
        
        try:
            # Create backup directory
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Run mongodump for specific collection
            cmd = [
                "mongodump",
                "--uri", self.mongo_uri,
                "--db", self.database_name,
                "--collection", collection_name,
                "--out", str(backup_path)
            ]
            
            result = await self._run_mongo_command(cmd)
            
            if result["success"]:
                # Create metadata file
                metadata = {
                    "backup_name": backup_name,
                    "backup_type": "collection",
                    "database_name": self.database_name,
                    "collection_name": collection_name,
                    "created_at": datetime.utcnow().isoformat(),
                    "backup_path": str(backup_path),
                    "backup_size_bytes": self._get_directory_size(backup_path)
                }
                
                metadata_file = backup_path / "backup_metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                logger.info(f"Collection backup completed: {collection_name}")
                return metadata
            else:
                raise Exception(f"Collection backup failed: {result['error']}")
                
        except Exception as e:
            logger.error(f"Error creating collection backup {collection_name}: {str(e)}")
            # Clean up failed backup
            if backup_path.exists():
                shutil.rmtree(backup_path)
            raise
    
    @handle_db_errors
    async def restore_backup(self, 
                           backup_name: str,
                           drop_existing: bool = False) -> Dict[str, Any]:
        """
        Restore database from backup using mongorestore.
        
        Args:
            backup_name: Name of backup to restore
            drop_existing: Whether to drop existing collections before restore
            
        Returns:
            Dict containing restore metadata
        """
        backup_path = self.backup_dir / backup_name
        
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_name}")
        
        logger.info(f"Starting database restore from backup: {backup_name}")
        
        try:
            # Load backup metadata
            metadata_file = backup_path / "backup_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    backup_metadata = json.load(f)
            else:
                backup_metadata = {"backup_type": "unknown"}
            
            # Find the actual backup data directory
            db_backup_path = backup_path / self.database_name
            if not db_backup_path.exists():
                # Look for any subdirectory that might contain the backup
                subdirs = [d for d in backup_path.iterdir() if d.is_dir()]
                if subdirs:
                    db_backup_path = subdirs[0]
                else:
                    raise FileNotFoundError(f"No backup data found in {backup_path}")
            
            # Build mongorestore command
            cmd = [
                "mongorestore",
                "--uri", self.mongo_uri,
                "--db", self.database_name
            ]
            
            if drop_existing:
                cmd.append("--drop")
            
            cmd.append(str(db_backup_path))
            
            result = await self._run_mongo_command(cmd)
            
            if result["success"]:
                restore_metadata = {
                    "backup_name": backup_name,
                    "backup_type": backup_metadata.get("backup_type", "unknown"),
                    "restored_at": datetime.utcnow().isoformat(),
                    "drop_existing": drop_existing,
                    "collections_restored": await self._get_collection_list()
                }
                
                logger.info(f"Database restore completed from backup: {backup_name}")
                return restore_metadata
            else:
                raise Exception(f"Restore failed: {result['error']}")
                
        except Exception as e:
            logger.error(f"Error restoring backup {backup_name}: {str(e)}")
            raise
    
    @handle_db_errors
    async def list_backups(self) -> List[Dict[str, Any]]:
        """
        List all available backups with metadata.
        
        Returns:
            List of backup metadata dictionaries
        """
        backups = []
        
        for backup_dir in self.backup_dir.iterdir():
            if backup_dir.is_dir():
                metadata_file = backup_dir / "backup_metadata.json"
                
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                        backups.append(metadata)
                    except Exception as e:
                        logger.warning(f"Failed to read metadata for backup {backup_dir.name}: {str(e)}")
                        # Create basic metadata for backups without metadata files
                        backups.append({
                            "backup_name": backup_dir.name,
                            "backup_type": "unknown",
                            "created_at": datetime.fromtimestamp(backup_dir.stat().st_mtime).isoformat(),
                            "backup_path": str(backup_dir),
                            "backup_size_bytes": self._get_directory_size(backup_dir)
                        })
        
        # Sort by creation date (newest first)
        backups.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return backups
    
    @handle_db_errors
    async def delete_backup(self, backup_name: str) -> bool:
        """
        Delete a backup directory and all its contents.
        
        Args:
            backup_name: Name of backup to delete
            
        Returns:
            True if backup was deleted successfully
        """
        backup_path = self.backup_dir / backup_name
        
        if not backup_path.exists():
            logger.warning(f"Backup not found for deletion: {backup_name}")
            return False
        
        try:
            shutil.rmtree(backup_path)
            logger.info(f"Backup deleted successfully: {backup_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting backup {backup_name}: {str(e)}")
            raise
    
    @handle_db_errors
    async def cleanup_old_backups(self, keep_count: int = 10) -> Dict[str, Any]:
        """
        Clean up old backups, keeping only the specified number of most recent ones.
        
        Args:
            keep_count: Number of backups to keep
            
        Returns:
            Dict containing cleanup summary
        """
        backups = await self.list_backups()
        
        if len(backups) <= keep_count:
            return {
                "total_backups": len(backups),
                "deleted_count": 0,
                "kept_count": len(backups),
                "deleted_backups": []
            }
        
        # Delete oldest backups
        backups_to_delete = backups[keep_count:]
        deleted_backups = []
        
        for backup in backups_to_delete:
            try:
                await self.delete_backup(backup["backup_name"])
                deleted_backups.append(backup["backup_name"])
            except Exception as e:
                logger.error(f"Failed to delete backup {backup['backup_name']}: {str(e)}")
        
        return {
            "total_backups": len(backups),
            "deleted_count": len(deleted_backups),
            "kept_count": len(backups) - len(deleted_backups),
            "deleted_backups": deleted_backups
        }
    
    async def _run_mongo_command(self, cmd: List[str]) -> Dict[str, Any]:
        """Run MongoDB command asynchronously."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return {
                    "success": True,
                    "stdout": stdout.decode('utf-8'),
                    "stderr": stderr.decode('utf-8')
                }
            else:
                return {
                    "success": False,
                    "error": stderr.decode('utf-8'),
                    "stdout": stdout.decode('utf-8')
                }
                
        except FileNotFoundError:
            return {
                "success": False,
                "error": "MongoDB tools not found. Please install MongoDB database tools."
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _get_collection_list(self) -> List[str]:
        """Get list of collections in the database."""
        try:
            from app.database import get_database
            db = await get_database()
            collections = await db.list_collection_names()
            return collections
        except Exception as e:
            logger.warning(f"Failed to get collection list: {str(e)}")
            return []
    
    def _get_directory_size(self, directory: Path) -> int:
        """Calculate total size of directory in bytes."""
        total_size = 0
        try:
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            logger.warning(f"Failed to calculate directory size for {directory}: {str(e)}")
        return total_size


# Global service instance
backup_service = BackupService()