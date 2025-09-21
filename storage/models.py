"""
Data models for LLM News Bot using SQLAlchemy ORM
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

Base = declarative_base()


class Paper(Base):
    """Table for storing paper metadata"""
    __tablename__ = "papers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)  # arxiv, crossref, biorxiv, etc.
    doi = Column(String(255), nullable=True, index=True)
    arxiv_id = Column(String(50), nullable=True, index=True)
    title = Column(Text, nullable=False)
    authors = Column(Text, nullable=False)  # JSON array as string
    abstract = Column(Text, nullable=True)
    url = Column(String(500), nullable=False)
    published_at = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    tags = Column(Text, nullable=True)  # JSON array as string
    categories = Column(Text, nullable=True)  # arXiv categories, etc.
    
    # Relationship to posts
    posts = relationship("PostItem", back_populates="paper")


class Post(Base):
    """Table for storing post sessions"""
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_date = Column(DateTime, default=datetime.utcnow)
    channel_id = Column(String(50), nullable=False)
    item_count = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending, success, failed, partial
    error_message = Column(Text, nullable=True)
    discord_message_id = Column(String(50), nullable=True)
    
    # Relationship to post items
    items = relationship("PostItem", back_populates="post")


class PostItem(Base):
    """Table for tracking which papers were posted in which posts"""
    __tablename__ = "post_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False)
    summary_thai = Column(Text, nullable=True)
    tldr_thai = Column(Text, nullable=True)
    position = Column(Integer, default=0)  # Order in the post
    
    # Relationships
    post = relationship("Post", back_populates="items")
    paper = relationship("Paper", back_populates="posts")


class SeenPaper(Base):
    """Table for deduplication - tracking papers we've already processed"""
    __tablename__ = "seen_papers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    identifier = Column(String(255), nullable=False, unique=True, index=True)  # DOI, arXiv ID, or hash
    identifier_type = Column(String(20), nullable=False)  # doi, arxiv_id, hash
    source = Column(String(50), nullable=False)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=True)
    seen_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    paper = relationship("Paper")


class Config(Base):
    """Table for storing runtime configuration"""
    __tablename__ = "config"
    
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


# Pydantic models for data validation and API
class PaperCreate(BaseModel):
    source: str
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    title: str
    authors: List[str]
    abstract: Optional[str] = None
    url: str
    published_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None


class PaperResponse(BaseModel):
    id: int
    source: str
    doi: Optional[str]
    arxiv_id: Optional[str]
    title: str
    authors: List[str]
    abstract: Optional[str]
    url: str
    published_at: Optional[datetime]
    fetched_at: datetime
    tags: Optional[List[str]]
    categories: Optional[List[str]]
    
    class Config:
        from_attributes = True


class PostCreate(BaseModel):
    channel_id: str
    papers: List[int]  # Paper IDs


class PostResponse(BaseModel):
    id: int
    run_date: datetime
    channel_id: str
    item_count: int
    status: str
    error_message: Optional[str]
    discord_message_id: Optional[str]
    
    class Config:
        from_attributes = True


class PostItemResponse(BaseModel):
    id: int
    paper: PaperResponse
    summary_thai: Optional[str]
    tldr_thai: Optional[str]
    position: int
    
    class Config:
        from_attributes = True


class SeenPaperCreate(BaseModel):
    identifier: str
    identifier_type: str  # doi, arxiv_id, hash
    source: str
    paper_id: Optional[int] = None


class SummaryRequest(BaseModel):
    title: str
    abstract: str
    authors: List[str]
    url: str
    min_length: int = Field(default=150, ge=50)
    max_length: int = Field(default=250, le=500)


class SummaryResponse(BaseModel):
    summary_thai: str
    tldr_thai: str
    word_count: int