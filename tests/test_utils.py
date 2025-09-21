"""
Database utilities for testing
"""
import os
import tempfile
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from storage.models import Base
from storage.db import DatabaseManager


class TestDatabaseManager:
    """Database manager for testing with temporary database"""
    
    def __init__(self):
        # Create temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        self.database_url = f"sqlite:///{self.temp_db.name}"
        self.engine = create_engine(self.database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create all tables
        Base.metadata.create_all(bind=self.engine)
        
        # Initialize database manager
        self.db_manager = DatabaseManager(database_url=self.database_url)
    
    def get_session(self) -> Generator:
        """Get database session for testing"""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    def cleanup(self):
        """Clean up temporary database"""
        try:
            self.engine.dispose()
            os.unlink(self.temp_db.name)
        except (OSError, AttributeError):
            pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


def create_test_paper_data():
    """Create test paper data for testing"""
    return {
        'arxiv_id': 'test.123',
        'title': 'Test Paper on Machine Learning',
        'abstract': 'This is a test abstract about machine learning and artificial intelligence.',
        'authors': ['Test Author 1', 'Test Author 2'],
        'published_date': '2024-01-15',
        'url': 'https://arxiv.org/abs/test.123',
        'source': 'arxiv',
        'categories': ['cs.AI', 'cs.LG'],
        'keywords': ['machine learning', 'artificial intelligence']
    }


def create_test_post_data():
    """Create test post data for testing"""
    return {
        'title': 'ข่าววิจัย AI วันที่ 15 มกราคม 2024',
        'content': 'สรุปงานวิจัยที่น่าสนใจในด้าน AI และ Machine Learning',
        'post_date': '2024-01-15',
        'total_papers': 3,
        'discord_message_id': '123456789',
        'status': 'posted'
    }