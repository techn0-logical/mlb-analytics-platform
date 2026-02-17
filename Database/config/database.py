"""
Database configuration and connection management
Implements security best practices and connection pooling
"""
import os
import logging
from typing import Optional
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

# Load environment variables from secrets.env (adjust path based on execution context)
import os
if os.path.exists('secrets.env'):
    load_dotenv('secrets.env')  # Run from project root
elif os.path.exists('../../secrets.env'):
    load_dotenv('../../secrets.env')  # Run from subdirectory
else:
    # Try to find secrets.env in parent directories
    current_dir = os.path.dirname(os.path.abspath(__file__))
    while current_dir != '/':
        secrets_path = os.path.join(current_dir, 'secrets.env')
        if os.path.exists(secrets_path):
            load_dotenv(secrets_path)
            break
        current_dir = os.path.dirname(current_dir)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base class for all models
Base = declarative_base()

class DatabaseConfig:
    """Secure database configuration management"""
    
    def __init__(self):
        self.database_url = self.create_database_url()
        self.engine = None
        self.SessionLocal = None
        
    def create_database_url(self):
        """Get database URL from environment variables"""
        # First try to use the complete DATABASE_URL
        database_url = os.getenv('DATABASE_URL')
        
        if database_url:
            # Convert postgresql:// to postgresql+psycopg2:// for SQLAlchemy
            if database_url.startswith('postgresql://'):
                database_url = database_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
            return database_url
        
        # Fallback to building URL from individual components
        user = os.getenv('DATABASE_USER', 'shawn')
        password = os.getenv('DATABASE_PASSWORD', 'password')
        host = os.getenv('DATABASE_HOST', 'localhost')
        port = os.getenv('DATABASE_PORT', '5432')
        database = os.getenv('DATABASE_NAME', 'mlb_betting_analytics')
        
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    
    def create_engine(self):
        """Create database engine with security and performance settings"""
        if self.engine is None:
            self.engine = create_engine(
                self.database_url,
                # Connection pooling for performance
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                # Security settings
                echo=False,  # Set to True only in development
                echo_pool=False,
                # Connection arguments for local development
                connect_args={
                    "connect_timeout": 10,
                    "application_name": "mlb_betting_analytics"
                }
            )
            
            # Add connection event listeners for monitoring
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                logger.info("Database connection established")
                
            @event.listens_for(self.engine, "checkout")
            def receive_checkout(dbapi_connection, connection_record, connection_proxy):
                logger.debug("Connection checked out from pool")
                
        return self.engine
    
    def create_session_factory(self):
        """Create session factory for database operations"""
        if self.SessionLocal is None:
            engine = self.create_engine()
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=engine
            )
        return self.SessionLocal
    
    def get_session(self):
        """Get database session with automatic cleanup"""
        SessionLocal = self.create_session_factory()
        session = SessionLocal()
        try:
            yield session
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

# Global database configuration instance
db_config = DatabaseConfig()

# Dependency for FastAPI/other frameworks
def get_db():
    """Database dependency for dependency injection"""
    return db_config.get_session()

# Initialize database tables
def init_database():
    """Initialize database tables and indexes"""
    try:
        engine = db_config.create_engine()
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False

def test_connection() -> bool:
    """Test database connection"""
    try:
        engine = db_config.create_engine()
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
            return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False