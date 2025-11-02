"""Base repository class with common CRUD operations."""

from typing import TypeVar, Generic, List, Optional, Dict, Any, Union
from abc import ABC, abstractmethod
from datetime import datetime
from beanie import Document
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from app.database_utils import handle_db_errors, NotFoundError, ValidationError

T = TypeVar('T', bound=Document)


class BaseRepository(Generic[T], ABC):
    """Base repository class with common async CRUD operations."""
    
    def __init__(self, model_class: type[T]):
        self.model_class = model_class
    
    @handle_db_errors
    async def create(self, data: Union[Dict[str, Any], T]) -> T:
        """Create a new document."""
        if isinstance(data, dict):
            document = self.model_class(**data)
        else:
            document = data
        
        await document.insert()
        return document
    
    @handle_db_errors
    async def get_by_id(self, document_id: Union[str, ObjectId]) -> Optional[T]:
        """Get document by ID."""
        if isinstance(document_id, str):
            document_id = ObjectId(document_id)
        
        return await self.model_class.get(document_id)
    
    @handle_db_errors
    async def get_by_id_or_raise(self, document_id: Union[str, ObjectId]) -> T:
        """Get document by ID or raise NotFoundError."""
        document = await self.get_by_id(document_id)
        if not document:
            raise NotFoundError(f"{self.model_class.__name__} with ID {document_id} not found")
        return document
    
    @handle_db_errors
    async def update(self, document_id: Union[str, ObjectId], 
                    update_data: Dict[str, Any]) -> Optional[T]:
        """Update document by ID."""
        document = await self.get_by_id_or_raise(document_id)
        
        # Update fields
        for field, value in update_data.items():
            if hasattr(document, field):
                setattr(document, field, value)
        
        # Update timestamp if available
        if hasattr(document, 'updated_at'):
            document.updated_at = datetime.utcnow()
        
        await document.save()
        return document
    
    @handle_db_errors
    async def delete(self, document_id: Union[str, ObjectId]) -> bool:
        """Delete document by ID."""
        document = await self.get_by_id(document_id)
        if document:
            await document.delete()
            return True
        return False
    
    @handle_db_errors
    async def delete_by_filter(self, filter_dict: Dict[str, Any]) -> int:
        """Delete documents matching filter."""
        result = await self.model_class.find(filter_dict).delete()
        return result.deleted_count
    
    @handle_db_errors
    async def find_all(self, 
                      filter_dict: Optional[Dict[str, Any]] = None,
                      sort_by: Optional[str] = None,
                      sort_order: int = DESCENDING,
                      skip: int = 0,
                      limit: Optional[int] = None) -> List[T]:
        """Find all documents matching filter with pagination and sorting."""
        query = self.model_class.find(filter_dict or {})
        
        if sort_by:
            query = query.sort([(sort_by, sort_order)])
        
        if skip > 0:
            query = query.skip(skip)
        
        if limit:
            query = query.limit(limit)
        
        return await query.to_list()
    
    @handle_db_errors
    async def find_one(self, filter_dict: Dict[str, Any]) -> Optional[T]:
        """Find single document matching filter."""
        return await self.model_class.find_one(filter_dict)
    
    @handle_db_errors
    async def find_one_or_raise(self, filter_dict: Dict[str, Any]) -> T:
        """Find single document or raise NotFoundError."""
        document = await self.find_one(filter_dict)
        if not document:
            raise NotFoundError(f"{self.model_class.__name__} not found with filter: {filter_dict}")
        return document
    
    @handle_db_errors
    async def count(self, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """Count documents matching filter."""
        return await self.model_class.find(filter_dict or {}).count()
    
    @handle_db_errors
    async def exists(self, filter_dict: Dict[str, Any]) -> bool:
        """Check if document exists matching filter."""
        count = await self.model_class.find(filter_dict).limit(1).count()
        return count > 0
    
    @handle_db_errors
    async def bulk_create(self, documents: List[Union[Dict[str, Any], T]]) -> List[T]:
        """Create multiple documents in bulk."""
        if not documents:
            return []
        
        # Convert dicts to document instances
        doc_instances = []
        for doc in documents:
            if isinstance(doc, dict):
                doc_instances.append(self.model_class(**doc))
            else:
                doc_instances.append(doc)
        
        await self.model_class.insert_many(doc_instances)
        return doc_instances
    
    @handle_db_errors
    async def bulk_update(self, updates: List[Dict[str, Any]]) -> int:
        """Perform bulk updates. Each update dict should have 'filter' and 'update' keys."""
        if not updates:
            return 0
        
        total_modified = 0
        for update_op in updates:
            if 'filter' not in update_op or 'update' not in update_op:
                raise ValidationError("Each update operation must have 'filter' and 'update' keys")
            
            result = await self.model_class.find(update_op['filter']).update_many(
                {"$set": update_op['update']}
            )
            total_modified += result.modified_count
        
        return total_modified
    
    @handle_db_errors
    async def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute aggregation pipeline."""
        cursor = self.model_class.aggregate(pipeline)
        return await cursor.to_list(length=None)
    
    @handle_db_errors
    async def distinct(self, field: str, 
                      filter_dict: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Get distinct values for a field."""
        return await self.model_class.find(filter_dict or {}).distinct(field)
    
    # Utility methods for common query patterns
    
    async def find_by_date_range(self, 
                               date_field: str,
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None,
                               **kwargs) -> List[T]:
        """Find documents within date range."""
        filter_dict = {}
        
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            filter_dict[date_field] = date_filter
        
        # Add any additional filters
        filter_dict.update(kwargs)
        
        return await self.find_all(filter_dict)
    
    async def search_text(self, 
                         search_term: str,
                         search_fields: List[str],
                         **kwargs) -> List[T]:
        """Search documents by text in specified fields."""
        if not search_term or not search_fields:
            return []
        
        # Create regex pattern for case-insensitive search
        pattern = {"$regex": search_term, "$options": "i"}
        
        if len(search_fields) == 1:
            filter_dict = {search_fields[0]: pattern}
        else:
            filter_dict = {"$or": [{field: pattern} for field in search_fields]}
        
        # Add any additional filters
        filter_dict.update(kwargs)
        
        return await self.find_all(filter_dict)
    
    async def paginate(self, 
                      page: int = 1,
                      page_size: int = 20,
                      filter_dict: Optional[Dict[str, Any]] = None,
                      sort_by: Optional[str] = None,
                      sort_order: int = DESCENDING) -> Dict[str, Any]:
        """Paginate results with metadata."""
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100
        
        skip = (page - 1) * page_size
        
        # Get total count
        total_count = await self.count(filter_dict)
        
        # Get paginated results
        documents = await self.find_all(
            filter_dict=filter_dict,
            sort_by=sort_by,
            sort_order=sort_order,
            skip=skip,
            limit=page_size
        )
        
        total_pages = (total_count + page_size - 1) // page_size
        
        return {
            "documents": documents,
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    
    async def get_recent(self, 
                        limit: int = 10,
                        date_field: str = "created_at",
                        **kwargs) -> List[T]:
        """Get most recent documents."""
        return await self.find_all(
            filter_dict=kwargs,
            sort_by=date_field,
            sort_order=DESCENDING,
            limit=limit
        )
    
    # Synchronous methods for Celery tasks
    
    def get_by_id_sync(self, document_id: Union[str, ObjectId]) -> Optional[T]:
        """Synchronous version of get_by_id for Celery tasks."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.get_by_id(document_id))
    
    def create_sync(self, data: Union[Dict[str, Any], T]) -> T:
        """Synchronous version of create for Celery tasks."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.create(data))
    
    def update_sync(self, document_id: Union[str, ObjectId], 
                   update_data: Dict[str, Any]) -> Optional[T]:
        """Synchronous version of update for Celery tasks."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.update(document_id, update_data))
    
    def delete_sync(self, document_id: Union[str, ObjectId]) -> bool:
        """Synchronous version of delete for Celery tasks."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.delete(document_id))
    
    def find_all_sync(self, 
                     filter_dict: Optional[Dict[str, Any]] = None,
                     sort_by: Optional[str] = None,
                     sort_order: int = DESCENDING,
                     skip: int = 0,
                     limit: Optional[int] = None) -> List[T]:
        """Synchronous version of find_all for Celery tasks."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.find_all(filter_dict, sort_by, sort_order, skip, limit)
        )
    
    def find_one_sync(self, filter_dict: Dict[str, Any]) -> Optional[T]:
        """Synchronous version of find_one for Celery tasks."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.find_one(filter_dict))