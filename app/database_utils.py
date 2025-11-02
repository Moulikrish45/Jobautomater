"""Database utilities and async error handling."""

import asyncio
import logging
from typing import Optional, Any, Dict, List, Callable, TypeVar, Generic
from functools import wraps
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import (
    ConnectionFailure, 
    ServerSelectionTimeoutError,
    DuplicateKeyError,
    BulkWriteError,
    OperationFailure
)
from beanie.exceptions import DocumentNotFound, RevisionIdWasChanged
from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DatabaseError(Exception):
    """Base database error class."""
    pass


class ConnectionError(DatabaseError):
    """Database connection error."""
    pass


class ValidationError(DatabaseError):
    """Data validation error."""
    pass


class DuplicateError(DatabaseError):
    """Duplicate key error."""
    pass


class NotFoundError(DatabaseError):
    """Document not found error."""
    pass


class ConcurrencyError(DatabaseError):
    """Concurrent modification error."""
    pass


def handle_db_errors(func: Callable) -> Callable:
    """Decorator to handle common database errors."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ConnectionFailure as e:
            logger.error(f"Database connection failed: {e}")
            raise ConnectionError(f"Failed to connect to database: {str(e)}")
        except ServerSelectionTimeoutError as e:
            logger.error(f"Database server selection timeout: {e}")
            raise ConnectionError(f"Database server timeout: {str(e)}")
        except DuplicateKeyError as e:
            logger.warning(f"Duplicate key error: {e}")
            raise DuplicateError(f"Duplicate entry: {str(e)}")
        except DocumentNotFound as e:
            logger.warning(f"Document not found: {e}")
            raise NotFoundError(f"Document not found: {str(e)}")
        except RevisionIdWasChanged as e:
            logger.warning(f"Document was modified concurrently: {e}")
            raise ConcurrencyError(f"Document was modified by another process: {str(e)}")
        except BulkWriteError as e:
            logger.error(f"Bulk write operation failed: {e}")
            raise DatabaseError(f"Bulk operation failed: {str(e)}")
        except OperationFailure as e:
            logger.error(f"Database operation failed: {e}")
            raise DatabaseError(f"Database operation failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected database error: {e}")
            raise DatabaseError(f"Unexpected error: {str(e)}")
    
    return wrapper


class RetryConfig:
    """Configuration for retry logic."""
    
    def __init__(self, 
                 max_attempts: int = 3,
                 initial_delay: float = 1.0,
                 max_delay: float = 60.0,
                 backoff_multiplier: float = 2.0):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier


async def retry_on_failure(func: Callable, 
                          retry_config: RetryConfig = None,
                          retryable_exceptions: tuple = None) -> Any:
    """Retry function execution on specific exceptions with exponential backoff."""
    if retry_config is None:
        retry_config = RetryConfig()
    
    if retryable_exceptions is None:
        retryable_exceptions = (ConnectionFailure, ServerSelectionTimeoutError, OperationFailure)
    
    delay = retry_config.initial_delay
    last_exception = None
    
    for attempt in range(retry_config.max_attempts):
        try:
            return await func()
        except retryable_exceptions as e:
            last_exception = e
            if attempt == retry_config.max_attempts - 1:
                logger.error(f"Function failed after {retry_config.max_attempts} attempts: {e}")
                break
            
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
            await asyncio.sleep(delay)
            delay = min(delay * retry_config.backoff_multiplier, retry_config.max_delay)
        except Exception as e:
            # Don't retry on non-retryable exceptions
            logger.error(f"Non-retryable error occurred: {e}")
            raise
    
    raise last_exception


class DatabaseHealthChecker:
    """Database health monitoring utilities."""
    
    @staticmethod
    async def check_connection(client: AsyncIOMotorClient) -> Dict[str, Any]:
        """Check database connection health."""
        try:
            # Ping the database
            await client.admin.command('ping')
            
            # Get server info
            server_info = await client.admin.command('serverStatus')
            
            return {
                'status': 'healthy',
                'server_version': server_info.get('version'),
                'uptime_seconds': server_info.get('uptime'),
                'connections': server_info.get('connections', {}),
                'timestamp': server_info.get('localTime')
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': None
            }
    
    @staticmethod
    async def check_indexes(database) -> Dict[str, Any]:
        """Check if required indexes exist."""
        try:
            collections = ['users', 'jobs', 'applications', 'resumes']
            index_status = {}
            
            for collection_name in collections:
                collection = database[collection_name]
                indexes = await collection.list_indexes().to_list(length=None)
                index_status[collection_name] = {
                    'count': len(indexes),
                    'indexes': [idx.get('name') for idx in indexes]
                }
            
            return {
                'status': 'checked',
                'collections': index_status
            }
        except Exception as e:
            logger.error(f"Index check failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }


class QueryBuilder:
    """Helper class for building complex MongoDB queries."""
    
    @staticmethod
    def build_text_search_query(search_term: str, fields: List[str]) -> Dict[str, Any]:
        """Build text search query for multiple fields."""
        if not search_term or not fields:
            return {}
        
        # Create regex pattern for case-insensitive search
        pattern = {"$regex": search_term, "$options": "i"}
        
        if len(fields) == 1:
            return {fields[0]: pattern}
        else:
            return {"$or": [{field: pattern} for field in fields]}
    
    @staticmethod
    def build_date_range_query(field: str, 
                              start_date: Optional[Any] = None,
                              end_date: Optional[Any] = None) -> Dict[str, Any]:
        """Build date range query."""
        query = {}
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query[field] = date_query
        return query
    
    @staticmethod
    def build_pagination_pipeline(skip: int = 0, limit: int = 20) -> List[Dict[str, Any]]:
        """Build aggregation pipeline for pagination."""
        pipeline = []
        if skip > 0:
            pipeline.append({"$skip": skip})
        if limit > 0:
            pipeline.append({"$limit": limit})
        return pipeline
    
    @staticmethod
    def build_sort_pipeline(sort_field: str, sort_order: int = -1) -> Dict[str, Any]:
        """Build sort stage for aggregation pipeline."""
        return {"$sort": {sort_field: sort_order}}


class TransactionManager:
    """Utility for managing database transactions."""
    
    def __init__(self, client: AsyncIOMotorClient):
        self.client = client
    
    async def execute_transaction(self, operations: List[Callable], 
                                session_options: Dict = None) -> Any:
        """Execute multiple operations in a transaction."""
        if session_options is None:
            session_options = {}
        
        async with await self.client.start_session() as session:
            try:
                async with session.start_transaction():
                    results = []
                    for operation in operations:
                        result = await operation(session)
                        results.append(result)
                    return results
            except Exception as e:
                logger.error(f"Transaction failed: {e}")
                raise DatabaseError(f"Transaction failed: {str(e)}")


# Utility functions for common database operations
async def ensure_indexes_exist(database) -> bool:
    """Ensure all required indexes exist."""
    try:
        # This would typically be called during application startup
        # Beanie handles index creation automatically based on model definitions
        logger.info("Checking database indexes...")
        
        health_checker = DatabaseHealthChecker()
        index_status = await health_checker.check_indexes(database)
        
        if index_status['status'] == 'checked':
            logger.info("Database indexes verified successfully")
            return True
        else:
            logger.error(f"Index verification failed: {index_status.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to ensure indexes exist: {e}")
        return False


async def cleanup_expired_data(database, days_to_keep: int = 90) -> Dict[str, int]:
    """Clean up old data based on retention policy."""
    try:
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        cleanup_results = {}
        
        # Clean up old failed applications
        applications_result = await database.applications.delete_many({
            "status": "failed",
            "created_at": {"$lt": cutoff_date}
        })
        cleanup_results['failed_applications'] = applications_result.deleted_count
        
        # Clean up old job discoveries that were never applied to
        jobs_result = await database.jobs.delete_many({
            "status": "discovered",
            "discovered_at": {"$lt": cutoff_date}
        })
        cleanup_results['old_job_discoveries'] = jobs_result.deleted_count
        
        logger.info(f"Cleanup completed: {cleanup_results}")
        return cleanup_results
        
    except Exception as e:
        logger.error(f"Data cleanup failed: {e}")
        raise DatabaseError(f"Cleanup operation failed: {str(e)}")