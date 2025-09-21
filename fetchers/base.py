"""
Base classes and interfaces for paper fetchers
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import hashlib


@dataclass
class PaperMetadata:
    """Standard paper metadata structure"""
    title: str
    authors: List[str]
    abstract: str
    url: str
    source: str
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    published_at: Optional[datetime] = None
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    
    def get_identifier(self) -> str:
        """Get unique identifier for deduplication"""
        if self.doi:
            return self.doi
        elif self.arxiv_id:
            return self.arxiv_id
        else:
            # Create hash from title + first author + year
            content = f"{self.title}{self.authors[0] if self.authors else ''}"
            if self.published_at:
                content += str(self.published_at.year)
            return hashlib.md5(content.encode()).hexdigest()
    
    def get_identifier_type(self) -> str:
        """Get identifier type for database"""
        if self.doi:
            return "doi"
        elif self.arxiv_id:
            return "arxiv_id"
        else:
            return "hash"


class BaseFetcher(ABC):
    """Base class for all paper fetchers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__.lower().replace('fetcher', '')
    
    @abstractmethod
    def fetch_papers(self, 
                    keywords: List[str],
                    categories: List[str] = None,
                    hours_back: int = 24,
                    max_results: int = 100) -> List[PaperMetadata]:
        """
        Fetch papers from the source
        
        Args:
            keywords: List of keywords to search for
            categories: List of categories to filter by (source-specific)
            hours_back: How many hours back to search
            max_results: Maximum number of results to return
            
        Returns:
            List of PaperMetadata objects
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """Test if the fetcher can connect to its source"""
        pass
    
    def is_enabled(self) -> bool:
        """Check if this fetcher is enabled in config"""
        # Handle special naming for google_scholar
        if 'google' in self.name.lower() and 'scholar' in self.name.lower():
            return self.config.get("ENABLE_GOOGLE_SCHOLAR", False)
        return self.config.get(f"ENABLE_{self.name.upper()}", False)
    
    def get_rate_limit(self) -> int:
        """Get rate limit for this fetcher"""
        return self.config.get(f"RATE_LIMIT_{self.name.upper()}", 10)
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        # Remove extra whitespace and newlines
        text = " ".join(text.strip().split())
        return text
    
    def parse_authors(self, authors_raw: Any) -> List[str]:
        """Parse authors from various formats to list of strings"""
        if isinstance(authors_raw, list):
            return [str(author).strip() for author in authors_raw if author]
        elif isinstance(authors_raw, str):
            # Split by common separators
            for sep in [', ', '; ', ' and ', ' & ']:
                if sep in authors_raw:
                    return [author.strip() for author in authors_raw.split(sep) if author.strip()]
            return [authors_raw.strip()] if authors_raw.strip() else []
        else:
            return []


class FetcherError(Exception):
    """Base exception for fetcher errors"""
    pass


class RateLimitError(FetcherError):
    """Raised when rate limit is exceeded"""
    pass


class NetworkError(FetcherError):
    """Raised for network-related errors"""
    pass


class APIError(FetcherError):
    """Raised for API-specific errors"""
    pass