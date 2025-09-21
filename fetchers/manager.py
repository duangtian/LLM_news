"""
Fetcher manager to coordinate all paper fetchers
"""
from typing import List, Dict, Any, Optional
from loguru import logger

from .base import BaseFetcher, PaperMetadata
from .arxiv import create_arxiv_fetcher
from .crossref import create_crossref_fetcher

try:
    from .google_scholar import create_google_scholar_fetcher
    GOOGLE_SCHOLAR_AVAILABLE = True
except ImportError:
    GOOGLE_SCHOLAR_AVAILABLE = False
    logger.warning("Google Scholar fetcher not available (scholarly library missing)")

try:
    from .nasa import create_nasa_fetcher
    NASA_AVAILABLE = True
except ImportError:
    NASA_AVAILABLE = False
    logger.warning("NASA fetcher not available")

try:
    from .tech_news import create_tech_news_fetcher
    TECH_NEWS_AVAILABLE = True
except ImportError:
    TECH_NEWS_AVAILABLE = False
    logger.warning("Tech News fetcher not available")


class FetcherManager:
    """Manages multiple paper fetchers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.fetchers: Dict[str, BaseFetcher] = {}
        self._initialize_fetchers()
    
    def _initialize_fetchers(self):
        """Initialize all available fetchers"""
        fetcher_factories = {
            'arxiv': create_arxiv_fetcher,
            'crossref': create_crossref_fetcher,
        }
        
        # Add Google Scholar if available
        if GOOGLE_SCHOLAR_AVAILABLE:
            fetcher_factories['google_scholar'] = create_google_scholar_fetcher
            
        # Add NASA if available
        if NASA_AVAILABLE:
            fetcher_factories['nasa'] = create_nasa_fetcher
            
        # Add Tech News if available
        if TECH_NEWS_AVAILABLE:
            fetcher_factories['tech_news'] = create_tech_news_fetcher
        
        for name, factory in fetcher_factories.items():
            try:
                fetcher = factory(self.config)
                if fetcher.is_enabled():
                    self.fetchers[name] = fetcher
                    logger.info(f"Initialized {name} fetcher")
                else:
                    logger.info(f"{name} fetcher is disabled")
            except Exception as e:
                logger.error(f"Failed to initialize {name} fetcher: {e}")
    
    def fetch_all_papers(self,
                        keywords: List[str],
                        categories: List[str] = None,
                        hours_back: int = 24,
                        max_results_per_source: int = 50) -> List[PaperMetadata]:
        """Fetch papers from all enabled sources"""
        
        all_papers = []
        
        for name, fetcher in self.fetchers.items():
            try:
                logger.info(f"Fetching papers from {name}...")
                papers = fetcher.fetch_papers(
                    keywords=keywords,
                    categories=categories,
                    hours_back=hours_back,
                    max_results=max_results_per_source
                )
                
                all_papers.extend(papers)
                logger.info(f"Fetched {len(papers)} papers from {name}")
                
            except Exception as e:
                logger.error(f"Error fetching from {name}: {e}")
                continue
        
        logger.info(f"Total papers fetched: {len(all_papers)}")
        return all_papers
    
    def test_all_connections(self) -> Dict[str, bool]:
        """Test connections to all fetchers"""
        results = {}
        
        for name, fetcher in self.fetchers.items():
            try:
                results[name] = fetcher.test_connection()
            except Exception as e:
                logger.error(f"Error testing {name}: {e}")
                results[name] = False
        
        return results
    
    def get_enabled_fetchers(self) -> List[str]:
        """Get list of enabled fetcher names"""
        return list(self.fetchers.keys())
    
    def get_fetcher(self, name: str) -> Optional[BaseFetcher]:
        """Get specific fetcher by name"""
        return self.fetchers.get(name)


def create_fetcher_manager(config: Dict[str, Any]) -> FetcherManager:
    """Factory function to create fetcher manager"""
    return FetcherManager(config)