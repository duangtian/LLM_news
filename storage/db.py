"""
Database operations and connection management
"""
import os
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, and_, or_, desc, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from loguru import logger

from .models import Base, Paper, Post, PostItem, SeenPaper, Config, PaperCreate, SeenPaperCreate


class DatabaseManager:
    """Database manager class for all database operations"""
    
    def __init__(self, database_url: str = None):
        if database_url is None:
            database_url = os.getenv("DATABASE_URL", "sqlite:///llm_news.db")
        
        self.engine = create_engine(
            database_url,
            echo=str(os.getenv("DEBUG", "false")).lower() == "true"
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        logger.info(f"Database initialized: {database_url}")
    
    def init_database(self):
        """Create all tables"""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created successfully")
    
    def get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()
    
    def close(self):
        """Close database connection"""
        self.engine.dispose()


# Global database manager instance
db_manager = DatabaseManager()


def init_database():
    """Initialize database tables"""
    db_manager.init_database()


def get_db():
    """Dependency to get database session"""
    db = db_manager.get_session()
    try:
        yield db
    finally:
        db.close()


class PaperRepository:
    """Repository for Paper operations"""
    
    @staticmethod
    def create_paper(db: Session, paper_data: PaperCreate) -> Paper:
        """Create a new paper record"""
        try:
            # Convert lists to JSON strings for storage
            authors_json = json.dumps(paper_data.authors) if paper_data.authors else "[]"
            tags_json = json.dumps(paper_data.tags) if paper_data.tags else None
            categories_json = json.dumps(paper_data.categories) if paper_data.categories else None
            
            paper = Paper(
                source=paper_data.source,
                doi=paper_data.doi,
                arxiv_id=paper_data.arxiv_id,
                title=paper_data.title,
                authors=authors_json,
                abstract=paper_data.abstract,
                url=paper_data.url,
                published_at=paper_data.published_at,
                tags=tags_json,
                categories=categories_json
            )
            
            db.add(paper)
            db.commit()
            db.refresh(paper)
            logger.info(f"Created paper: {paper.title[:50]}...")
            return paper
            
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Failed to create paper: {e}")
            raise
    
    @staticmethod
    def get_paper_by_id(db: Session, paper_id: int) -> Optional[Paper]:
        """Get paper by ID"""
        return db.query(Paper).filter(Paper.id == paper_id).first()
    
    @staticmethod
    def get_papers_by_source(db: Session, source: str, limit: int = 100) -> List[Paper]:
        """Get papers by source"""
        return db.query(Paper).filter(Paper.source == source).order_by(desc(Paper.fetched_at)).limit(limit).all()
    
    @staticmethod
    def get_recent_papers(db: Session, hours: int = 24, limit: int = 100) -> List[Paper]:
        """Get papers fetched in the last N hours"""
        since = datetime.utcnow() - timedelta(hours=hours)
        return (
            db.query(Paper)
            .filter(Paper.fetched_at >= since)
            .order_by(desc(Paper.fetched_at))
            .limit(limit)
            .all()
        )
    
    @staticmethod
    def search_papers(db: Session, query: str, limit: int = 50) -> List[Paper]:
        """Search papers by title or abstract"""
        search_term = f"%{query}%"
        return (
            db.query(Paper)
            .filter(
                or_(
                    Paper.title.ilike(search_term),
                    Paper.abstract.ilike(search_term)
                )
            )
            .order_by(desc(Paper.published_at))
            .limit(limit)
            .all()
        )


class SeenPaperRepository:
    """Repository for SeenPaper operations"""
    
    @staticmethod
    def mark_as_seen(db: Session, seen_data: SeenPaperCreate) -> SeenPaper:
        """Mark a paper as seen"""
        try:
            seen = SeenPaper(
                identifier=seen_data.identifier,
                identifier_type=seen_data.identifier_type,
                source=seen_data.source,
                paper_id=seen_data.paper_id
            )
            
            db.add(seen)
            db.commit()
            db.refresh(seen)
            logger.debug(f"Marked as seen: {seen_data.identifier}")
            return seen
            
        except IntegrityError:
            # Already exists, that's fine
            db.rollback()
            return SeenPaperRepository.get_seen_paper(db, seen_data.identifier)
    
    @staticmethod
    def get_seen_paper(db: Session, identifier: str) -> Optional[SeenPaper]:
        """Check if paper was already seen"""
        return db.query(SeenPaper).filter(SeenPaper.identifier == identifier).first()
    
    @staticmethod
    def is_paper_seen(db: Session, identifier: str) -> bool:
        """Check if paper was already seen (boolean)"""
        return db.query(SeenPaper).filter(SeenPaper.identifier == identifier).first() is not None
    
    @staticmethod
    def cleanup_old_seen(db: Session, days: int = 30):
        """Remove seen records older than N days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = db.query(SeenPaper).filter(SeenPaper.seen_at < cutoff).delete()
        db.commit()
        logger.info(f"Cleaned up {deleted} old seen records")


class PostRepository:
    """Repository for Post operations"""
    
    @staticmethod
    def create_post(db: Session, channel_id: str, paper_ids: List[int]) -> Post:
        """Create a new post session"""
        post = Post(
            channel_id=channel_id,
            item_count=len(paper_ids),
            status="pending"
        )
        
        db.add(post)
        db.flush()  # Get the ID
        
        # Add post items
        for i, paper_id in enumerate(paper_ids):
            item = PostItem(
                post_id=post.id,
                paper_id=paper_id,
                position=i
            )
            db.add(item)
        
        db.commit()
        db.refresh(post)
        logger.info(f"Created post session with {len(paper_ids)} papers")
        return post
    
    @staticmethod
    def update_post_status(db: Session, post_id: int, status: str, error_message: str = None, discord_message_id: str = None):
        """Update post status"""
        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            post.status = status
            if error_message:
                post.error_message = error_message
            if discord_message_id:
                post.discord_message_id = discord_message_id
            db.commit()
            logger.info(f"Updated post {post_id} status to {status}")
    
    @staticmethod
    def get_post_by_id(db: Session, post_id: int) -> Optional[Post]:
        """Get post by ID with items"""
        return db.query(Post).filter(Post.id == post_id).first()
    
    @staticmethod
    def get_recent_posts(db: Session, days: int = 7) -> List[Post]:
        """Get recent posts"""
        since = datetime.utcnow() - timedelta(days=days)
        return (
            db.query(Post)
            .filter(Post.run_date >= since)
            .order_by(desc(Post.run_date))
            .all()
        )
    
    @staticmethod
    def update_post_item_summary(db: Session, post_id: int, paper_id: int, summary_thai: str, tldr_thai: str):
        """Update summary for a post item"""
        item = (
            db.query(PostItem)
            .filter(and_(PostItem.post_id == post_id, PostItem.paper_id == paper_id))
            .first()
        )
        if item:
            item.summary_thai = summary_thai
            item.tldr_thai = tldr_thai
            db.commit()
            logger.debug(f"Updated summary for post {post_id}, paper {paper_id}")


class ConfigRepository:
    """Repository for Config operations"""
    
    @staticmethod
    def set_config(db: Session, key: str, value: Any):
        """Set configuration value"""
        config = db.query(Config).filter(Config.key == key).first()
        value_str = json.dumps(value) if not isinstance(value, str) else value
        
        if config:
            config.value = value_str
            config.updated_at = datetime.utcnow()
        else:
            config = Config(key=key, value=value_str)
            db.add(config)
        
        db.commit()
        logger.debug(f"Set config {key} = {value}")
    
    @staticmethod
    def get_config(db: Session, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        config = db.query(Config).filter(Config.key == key).first()
        if config and config.value:
            try:
                return json.loads(config.value)
            except json.JSONDecodeError:
                return config.value
        return default
    
    @staticmethod
    def get_all_config(db: Session) -> Dict[str, Any]:
        """Get all configuration values"""
        configs = db.query(Config).all()
        result = {}
        for config in configs:
            try:
                result[config.key] = json.loads(config.value)
            except json.JSONDecodeError:
                result[config.key] = config.value
        return result


def get_database_stats(db: Session = None) -> Dict[str, int]:
    """Get database statistics"""
    if db is None:
        db = db_manager.get_session()
        should_close = True
    else:
        should_close = False
    
    try:
        stats = {
            "total_papers": db.query(Paper).count(),
            "papers_today": db.query(Paper).filter(
                Paper.fetched_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            ).count(),
            "total_posts": db.query(Post).count(),
            "successful_posts": db.query(Post).filter(Post.status == "success").count(),
            "failed_posts": db.query(Post).filter(Post.status == "failed").count(),
            "seen_papers": db.query(SeenPaper).count(),
        }
        
        # Add source breakdown
        source_stats = (
            db.query(Paper.source, func.count(Paper.id))
            .group_by(Paper.source)
            .all()
        )
        for source, count in source_stats:
            stats[f"papers_from_{source}"] = count
        
        return stats
    
    finally:
        if should_close:
            db.close()


def cleanup_database(db: Session = None, days: int = 30):
    """Clean up old database records"""
    if db is None:
        db = db_manager.get_session()
        should_close = True
    else:
        should_close = False
    
    try:
        # Clean up old seen papers
        SeenPaperRepository.cleanup_old_seen(db, days)
        
        # Clean up old failed posts (keep successful ones longer)
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted_posts = (
            db.query(Post)
            .filter(and_(Post.run_date < cutoff, Post.status == "failed"))
            .delete()
        )
        
        db.commit()
        logger.info(f"Cleaned up {deleted_posts} old failed posts")
        
    finally:
        if should_close:
            db.close()


# Convenience functions
def get_stats() -> Dict[str, int]:
    """Get database statistics (convenience function)"""
    return get_database_stats()


def mark_paper_seen(identifier: str, identifier_type: str, source: str, paper_id: int = None) -> bool:
    """Mark paper as seen (convenience function)"""
    db = db_manager.get_session()
    try:
        seen_data = SeenPaperCreate(
            identifier=identifier,
            identifier_type=identifier_type,
            source=source,
            paper_id=paper_id
        )
        SeenPaperRepository.mark_as_seen(db, seen_data)
        return True
    except Exception as e:
        logger.error(f"Failed to mark paper as seen: {e}")
        return False
    finally:
        db.close()


def is_paper_seen(identifier: str) -> bool:
    """Check if paper was seen (convenience function)"""
    db = db_manager.get_session()
    try:
        return SeenPaperRepository.is_paper_seen(db, identifier)
    finally:
        db.close()