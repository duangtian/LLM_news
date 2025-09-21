"""
Google Scholar paper fetcher using scholarly library
"""
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re
from loguru import logger

try:
    from scholarly import scholarly, ProxyGenerator
    SCHOLARLY_AVAILABLE = True
except ImportError:
    SCHOLARLY_AVAILABLE = False
    logger.warning("scholarly library not available. Install with: pip install scholarly")

from .base import BaseFetcher, PaperMetadata


class GoogleScholarFetcher(BaseFetcher):
    """Fetcher for Google Scholar papers"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        if not SCHOLARLY_AVAILABLE:
            raise ImportError("scholarly library not available")
        
        self.source_name = "google_scholar"
        self.rate_limit = config.get('RATE_LIMIT_GOOGLE_SCHOLAR', 5)  # requests per second
        self.max_papers = config.get('MAX_PAPERS_GOOGLE_SCHOLAR', 20)
        self.days_back = config.get('GOOGLE_SCHOLAR_DAYS_BACK', 7)
        
        # Setup proxy if needed (Google Scholar blocks automated requests)
        self.use_proxy = config.get('GOOGLE_SCHOLAR_USE_PROXY', False)
        if self.use_proxy:
            self._setup_proxy()
        
        logger.debug(f"Google Scholar fetcher initialized with rate_limit={self.rate_limit}/s")
    
    def _setup_proxy(self):
        """Setup proxy for Google Scholar (recommended to avoid blocking)"""
        try:
            pg = ProxyGenerator()
            pg.FreeProxies()
            scholarly.use_proxy(pg)
            logger.info("Google Scholar proxy configured")
        except Exception as e:
            logger.warning(f"Failed to setup Google Scholar proxy: {e}")
    
    def fetch_papers(self, keywords: List[str], categories: List[str] = None, 
                    hours_back: int = 24, max_results: int = 100) -> List[PaperMetadata]:
        """Fetch papers from Google Scholar"""
        
        if not keywords:
            logger.warning("No keywords provided for Google Scholar search")
            return []
        
        try:
            papers = []
            
            # Create search query
            query = self._build_search_query(keywords)
            logger.info(f"Searching Google Scholar with query: {query}")
            
            # Search papers
            search_query = scholarly.search_pubs(query)
            
            count = 0
            for result in search_query:
                if count >= max_results:
                    break
                
                try:
                    paper = self._parse_scholar_result(result)
                    if paper and self._is_recent_paper(paper, hours_back):
                        papers.append(paper)
                        count += 1
                        logger.debug(f"Parsed paper: {paper.title[:50]}...")
                    
                    # Rate limiting
                    time.sleep(1.0 / self.rate_limit)
                    
                except Exception as e:
                    logger.warning(f"Error parsing Google Scholar result: {e}")
                    continue
            
            logger.info(f"Fetched {len(papers)} papers from Google Scholar")
            return papers
            
        except Exception as e:
            logger.error(f"Error fetching from Google Scholar: {e}")
            return []
    
    def _build_search_query(self, keywords: List[str]) -> str:
        """Build search query for Google Scholar"""
        
        # Combine keywords with OR
        keyword_query = " OR ".join(f'"{keyword}"' for keyword in keywords[:5])  # Limit to avoid too long queries
        
        # Add time constraint for recent papers
        current_year = datetime.now().year
        year_constraint = f"after:{current_year-1}"  # Papers from last year onwards
        
        # Combine query parts
        full_query = f"({keyword_query}) {year_constraint}"
        
        return full_query
    
    def _parse_scholar_result(self, result: Dict[str, Any]) -> Optional[PaperMetadata]:
        """Parse Google Scholar search result"""
        
        try:
            # Extract basic information
            title = result.get('title', '').strip()
            if not title:
                return None
            
            # Abstract (often called 'snippet' in Scholar)
            abstract = result.get('snippet', '').strip()
            if not abstract:
                abstract = result.get('abstract', '').strip()
            
            # Authors
            authors = []
            author_data = result.get('author', [])
            if isinstance(author_data, list):
                authors = [author.get('name', '') for author in author_data if author.get('name')]
            elif isinstance(author_data, str):
                authors = [author_data]
            
            # Publication info
            pub_info = result.get('venue', '') or result.get('journal', '') or result.get('booktitle', '')
            
            # URL
            url = result.get('url', '') or result.get('eprint_url', '')
            
            # Publication year
            pub_year = result.get('year')
            if pub_year:
                try:
                    pub_date = f"{pub_year}-01-01"  # Default to January 1st
                except:
                    pub_date = None
            else:
                pub_date = None
            
            # Citations count (for relevance scoring)
            citations = result.get('citations', 0)
            
            # Create metadata
            paper = PaperMetadata(
                title=title,
                authors=authors,
                abstract=abstract or f"Paper from {pub_info}",  # Fallback if no abstract
                url=url or f"https://scholar.google.com/scholar?q={title.replace(' ', '+')}",
                source=self.source_name,
                published_at=datetime.strptime(pub_date, "%Y-%m-%d") if pub_date else None,
                categories=[pub_info] if pub_info else [],
                tags=self._extract_keywords(title, abstract),
                metadata={
                    'venue': pub_info,
                    'citations': citations,
                    'year': pub_year
                }
            )
            
            return paper
            
        except Exception as e:
            logger.error(f"Error parsing Google Scholar result: {e}")
            return None
    
    def _is_recent_paper(self, paper: PaperMetadata, hours_back: int = 24) -> bool:
        """Check if paper is recent enough"""
        
        if not paper.published_at:
            # If no date, assume it's recent
            return True
        
        try:
            cutoff_date = datetime.now() - timedelta(hours=hours_back)
            return paper.published_at >= cutoff_date
            
        except:
            # If date parsing fails, assume it's recent
            return True
    
    def _extract_keywords(self, title: str, abstract: str) -> List[str]:
        """Extract keywords from title and abstract"""
        
        text = f"{title} {abstract}".lower()
        
        # Common AI/ML keywords to look for
        ai_keywords = [
            'machine learning', 'deep learning', 'neural network', 'artificial intelligence',
            'computer vision', 'natural language processing', 'nlp', 'transformers',
            'diffusion', 'gan', 'generative', 'classification', 'regression',
            'reinforcement learning', 'supervised learning', 'unsupervised learning',
            'convolutional', 'recurrent', 'attention', 'bert', 'gpt',
            'data mining', 'big data', 'analytics', 'algorithm'
        ]
        
        found_keywords = []
        for keyword in ai_keywords:
            if keyword in text:
                found_keywords.append(keyword)
        
        return found_keywords[:5]  # Limit to top 5
    
    def test_connection(self) -> bool:
        """Test Google Scholar connection"""
        
        try:
            # Try a simple search
            search_query = scholarly.search_pubs("machine learning")
            result = next(search_query, None)
            
            if result:
                logger.info("Google Scholar connection test successful")
                return True
            else:
                logger.warning("Google Scholar connection test returned no results")
                return False
                
        except Exception as e:
            logger.error(f"Google Scholar connection test failed: {e}")
            return False


def create_google_scholar_fetcher(config: Dict[str, Any]) -> GoogleScholarFetcher:
    """Factory function to create Google Scholar fetcher"""
    return GoogleScholarFetcher(config)