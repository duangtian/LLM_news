"""
arXiv paper fetcher using arXiv API
"""
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode
import requests
from loguru import logger

from .base import BaseFetcher, PaperMetadata, FetcherError, RateLimitError, NetworkError


class ArxivFetcher(BaseFetcher):
    """Fetcher for arXiv papers"""
    
    BASE_URL = "http://export.arxiv.org/api/query"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'LLM-News-Bot/1.0 (https://github.com/your-repo)'
        })
        self.last_request_time = 0
        
    def fetch_papers(self, 
                    keywords: List[str],
                    categories: List[str] = None,
                    hours_back: int = 24,
                    max_results: int = 100) -> List[PaperMetadata]:
        """Fetch papers from arXiv"""
        
        if not self.is_enabled():
            logger.info("arXiv fetcher is disabled")
            return []
        
        try:
            # Build search query
            query = self._build_query(keywords, categories, hours_back)
            
            # Make request with rate limiting
            papers = []
            start = 0
            per_request = min(max_results, 100)  # arXiv recommends max 100 per request
            
            while len(papers) < max_results and start < 500:  # Safety limit
                batch = self._fetch_batch(query, start, per_request)
                if not batch:
                    break
                    
                papers.extend(batch)
                start += per_request
                
                if len(batch) < per_request:
                    break  # No more papers available
                    
                # Rate limiting
                self._wait_for_rate_limit()
            
            logger.info(f"Fetched {len(papers)} papers from arXiv")
            return papers[:max_results]
            
        except Exception as e:
            logger.error(f"Error fetching from arXiv: {e}")
            raise FetcherError(f"arXiv fetch failed: {e}")
    
    def _build_query(self, keywords: List[str], categories: List[str], hours_back: int) -> str:
        """Build arXiv search query"""
        query_parts = []
        
        # Add category filters
        if categories:
            cat_filters = []
            for cat in categories:
                if self._is_valid_category(cat):
                    cat_filters.append(f"cat:{cat}")
            if cat_filters:
                query_parts.append("(" + " OR ".join(cat_filters) + ")")
        
        # Add keyword filters (search in title and abstract)
        if keywords:
            keyword_filters = []
            for keyword in keywords:
                # Search in title and abstract
                keyword_clean = keyword.replace('"', '').strip()
                keyword_filters.append(f'(ti:"{keyword_clean}" OR abs:"{keyword_clean}")')
            if keyword_filters:
                query_parts.append("(" + " OR ".join(keyword_filters) + ")")
        
        # Combine with AND
        if not query_parts:
            # Fallback to popular ML categories if no filters
            query_parts.append("(cat:cs.AI OR cat:cs.LG OR cat:cs.CL OR cat:cs.CV)")
        
        return " AND ".join(query_parts)
    
    def _fetch_batch(self, query: str, start: int, max_results: int) -> List[PaperMetadata]:
        """Fetch a batch of papers from arXiv"""
        params = {
            'search_query': query,
            'start': start,
            'max_results': max_results,
            'sortBy': 'lastUpdatedDate',  # Get recently updated papers
            'sortOrder': 'descending'
        }
        
        url = f"{self.BASE_URL}?{urlencode(params)}"
        
        try:
            self._wait_for_rate_limit()
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            return self._parse_response(response.text)
            
        except requests.RequestException as e:
            logger.error(f"Network error fetching arXiv batch: {e}")
            raise NetworkError(f"arXiv network error: {e}")
    
    def _parse_response(self, xml_content: str) -> List[PaperMetadata]:
        """Parse arXiv API XML response"""
        papers = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Check for errors
            if 'errors' in xml_content.lower() or 'error' in xml_content.lower():
                logger.warning("arXiv API returned error response")
                return []
            
            # Parse entries
            for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                paper = self._parse_entry(entry)
                if paper:
                    papers.append(paper)
            
            return papers
            
        except ET.ParseError as e:
            logger.error(f"Error parsing arXiv XML: {e}")
            return []
    
    def _parse_entry(self, entry) -> Optional[PaperMetadata]:
        """Parse a single arXiv entry"""
        try:
            # Extract basic information
            title = self._get_text(entry, '{http://www.w3.org/2005/Atom}title')
            if not title:
                return None
            
            abstract = self._get_text(entry, '{http://www.w3.org/2005/Atom}summary')
            url = self._get_text(entry, '{http://www.w3.org/2005/Atom}id')
            
            # Extract arXiv ID from URL
            arxiv_id = None
            if url:
                match = re.search(r'arxiv\.org/abs/([0-9]+\.[0-9]+)', url)
                if match:
                    arxiv_id = match.group(1)
            
            # Extract authors
            authors = []
            for author in entry.findall('{http://www.w3.org/2005/Atom}author'):
                name = self._get_text(author, '{http://www.w3.org/2005/Atom}name')
                if name:
                    authors.append(name)
            
            # Extract published date
            published_str = self._get_text(entry, '{http://www.w3.org/2005/Atom}published')
            published_at = None
            if published_str:
                try:
                    published_at = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                except ValueError:
                    pass
            
            # Extract categories
            categories = []
            for category in entry.findall('{http://arxiv.org/schemas/atom}primary_category'):
                cat = category.get('term')
                if cat:
                    categories.append(cat)
            
            # Clean text
            title = self.clean_text(title)
            abstract = self.clean_text(abstract)
            
            # Validate minimum requirements
            if not title or not abstract or len(abstract) < 50:
                return None
            
            return PaperMetadata(
                title=title,
                authors=authors,
                abstract=abstract,
                url=url,
                source="arxiv",
                arxiv_id=arxiv_id,
                published_at=published_at,
                categories=categories
            )
            
        except Exception as e:
            logger.error(f"Error parsing arXiv entry: {e}")
            return None
    
    def _get_text(self, element, tag: str) -> Optional[str]:
        """Safely get text from XML element"""
        found = element.find(tag)
        if found is not None and found.text:
            return found.text.strip()
        return None
    
    def _is_valid_category(self, category: str) -> bool:
        """Check if arXiv category is valid"""
        # Common arXiv categories (partial list)
        valid_categories = {
            'cs.AI', 'cs.LG', 'cs.CL', 'cs.CV', 'cs.NE', 'cs.RO', 'cs.IR',
            'stat.ML', 'math.ST', 'physics.data-an', 'q-bio.QM', 'eess.IV'
        }
        return category in valid_categories or '.' in category  # Allow custom categories
    
    def _wait_for_rate_limit(self):
        """Implement rate limiting"""
        rate_limit = self.get_rate_limit()  # requests per minute
        min_interval = 60.0 / rate_limit  # seconds between requests
        
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def test_connection(self) -> bool:
        """Test arXiv API connection"""
        try:
            # Simple test query
            params = {
                'search_query': 'cat:cs.AI',
                'start': 0,
                'max_results': 1
            }
            url = f"{self.BASE_URL}?{urlencode(params)}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Check if response contains expected XML structure
            if '<feed' in response.text and '<entry' in response.text:
                logger.info("arXiv connection test successful")
                return True
            else:
                logger.error("arXiv returned unexpected response format")
                return False
                
        except Exception as e:
            logger.error(f"arXiv connection test failed: {e}")
            return False


def create_arxiv_fetcher(config: Dict[str, Any]) -> ArxivFetcher:
    """Factory function to create arXiv fetcher"""
    return ArxivFetcher(config)