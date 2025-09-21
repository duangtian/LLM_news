"""
Crossref paper fetcher using Crossref REST API
"""
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
from loguru import logger

from .base import BaseFetcher, PaperMetadata, FetcherError, NetworkError


class CrossrefFetcher(BaseFetcher):
    """Fetcher for papers from Crossref"""
    
    BASE_URL = "https://api.crossref.org/works"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'LLM-News-Bot/1.0 (mailto:your-email@example.com)'  # Crossref requires email
        })
        self.last_request_time = 0
    
    def fetch_papers(self, 
                    keywords: List[str],
                    categories: List[str] = None,
                    hours_back: int = 24,
                    max_results: int = 100) -> List[PaperMetadata]:
        """Fetch papers from Crossref"""
        
        if not self.is_enabled():
            logger.info("Crossref fetcher is disabled")
            return []
        
        try:
            papers = []
            
            # Crossref API returns max 1000 per request, but we'll paginate
            per_request = min(max_results, 100)
            offset = 0
            
            while len(papers) < max_results and offset < 500:  # Safety limit
                batch = self._fetch_batch(keywords, offset, per_request, hours_back)
                if not batch:
                    break
                
                papers.extend(batch)
                offset += per_request
                
                if len(batch) < per_request:
                    break  # No more papers available
                
                # Rate limiting
                self._wait_for_rate_limit()
            
            logger.info(f"Fetched {len(papers)} papers from Crossref")
            return papers[:max_results]
            
        except Exception as e:
            logger.error(f"Error fetching from Crossref: {e}")
            raise FetcherError(f"Crossref fetch failed: {e}")
    
    def _fetch_batch(self, keywords: List[str], offset: int, rows: int, hours_back: int) -> List[PaperMetadata]:
        """Fetch a batch of papers from Crossref"""
        
        # Build query parameters
        params = {
            'rows': rows,
            'offset': offset,
            'sort': 'published',  # Sort by publication date
            'order': 'desc',
            'filter': []
        }
        
        # Add date filter
        cutoff_date = datetime.utcnow() - timedelta(hours=hours_back)
        date_filter = f"from-pub-date:{cutoff_date.strftime('%Y-%m-%d')}"
        params['filter'].append(date_filter)
        
        # Add keyword query
        if keywords:
            # Search in title and abstract
            query_parts = []
            for keyword in keywords:
                query_parts.append(f'"{keyword}"')
            params['query'] = ' OR '.join(query_parts)
        
        # Convert filter list to string
        if params['filter']:
            params['filter'] = ','.join(params['filter'])
        else:
            del params['filter']
        
        try:
            self._wait_for_rate_limit()
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            
            return self._parse_response(response.json())
            
        except requests.RequestException as e:
            logger.error(f"Network error fetching Crossref batch: {e}")
            raise NetworkError(f"Crossref network error: {e}")
    
    def _parse_response(self, data: Dict[str, Any]) -> List[PaperMetadata]:
        """Parse Crossref API JSON response"""
        papers = []
        
        try:
            message = data.get('message', {})
            items = message.get('items', [])
            
            for item in items:
                paper = self._parse_item(item)
                if paper:
                    papers.append(paper)
            
            return papers
            
        except Exception as e:
            logger.error(f"Error parsing Crossref response: {e}")
            return []
    
    def _parse_item(self, item: Dict[str, Any]) -> Optional[PaperMetadata]:
        """Parse a single Crossref item"""
        try:
            # Extract title
            titles = item.get('title', [])
            if not titles:
                return None
            title = titles[0] if isinstance(titles, list) else str(titles)
            
            # Extract DOI
            doi = item.get('DOI')
            
            # Build URL
            url = f"https://doi.org/{doi}" if doi else item.get('URL', '')
            
            # Extract authors
            authors = []
            author_list = item.get('author', [])
            for author in author_list:
                if isinstance(author, dict):
                    given = author.get('given', '')
                    family = author.get('family', '')
                    if family:
                        full_name = f"{given} {family}".strip()
                        authors.append(full_name)
            
            # Extract abstract (often not available in Crossref)
            abstract = item.get('abstract', '')
            if not abstract:
                # Use title as fallback for abstract
                abstract = f"Paper titled: {title}"
            
            # Extract published date
            published_at = None
            pub_date = item.get('published-print') or item.get('published-online')
            if pub_date and 'date-parts' in pub_date:
                date_parts = pub_date['date-parts'][0]
                if len(date_parts) >= 3:
                    try:
                        published_at = datetime(date_parts[0], date_parts[1], date_parts[2])
                    except (ValueError, IndexError):
                        pass
            
            # Extract categories/subject
            categories = []
            subjects = item.get('subject', [])
            if subjects:
                categories = subjects if isinstance(subjects, list) else [subjects]
            
            # Clean text
            title = self.clean_text(title)
            abstract = self.clean_text(abstract)
            
            # Validate minimum requirements
            if not title or len(title) < 10:
                return None
            
            # Skip if abstract is too short (Crossref often lacks abstracts)
            if len(abstract) < 20:
                logger.debug(f"Skipping paper with short abstract: {title[:50]}")
                return None
            
            return PaperMetadata(
                title=title,
                authors=authors,
                abstract=abstract,
                url=url,
                source="crossref",
                doi=doi,
                published_at=published_at,
                categories=categories
            )
            
        except Exception as e:
            logger.error(f"Error parsing Crossref item: {e}")
            return None
    
    def _wait_for_rate_limit(self):
        """Implement rate limiting (Crossref allows 50 requests/second for polite pool)"""
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
        """Test Crossref API connection"""
        try:
            # Simple test query
            params = {
                'query': 'machine learning',
                'rows': 1
            }
            
            response = self.session.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if 'message' in data and 'items' in data['message']:
                logger.info("Crossref connection test successful")
                return True
            else:
                logger.error("Crossref returned unexpected response format")
                return False
                
        except Exception as e:
            logger.error(f"Crossref connection test failed: {e}")
            return False


def create_crossref_fetcher(config: Dict[str, Any]) -> CrossrefFetcher:
    """Factory function to create Crossref fetcher"""
    return CrossrefFetcher(config)