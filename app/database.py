"""Database connection and initialization."""

import logging
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.config import settings
from app.models.user import User
from app.models.job import Job
from app.models.application import Application
from app.models.resume import Resume

logger = logging.getLogger(__name__)

# Global database client
client: AsyncIOMotorClient = None
database = None


async def connect_to_mongo():
    """Create database connection."""
    global client, database
    
    try:
        logger.info(f"Connecting to MongoDB at {settings.mongodb_url}")
        
        # Create MongoDB client
        client = AsyncIOMotorClient(
            settings.mongodb_url,
            maxPoolSize=settings.mongodb_max_connections,
            minPoolSize=settings.mongodb_min_connections
        )
        
        # Get database
        database = client[settings.database_name]
        
        # Test connection
        await client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")
        
        # Initialize Beanie with document models
        await init_beanie(
            database=database,
            document_models=[User, Job, Application, Resume]
        )
        logger.info("Beanie ODM initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close database connection."""
    global client
    
    if client:
        try:
            client.close()
            logger.info("MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}")


def get_database():
    """Get database instance."""
    return database