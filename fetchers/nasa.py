"""
NASA and space-related content fetcher
"""
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import requests
from loguru import logger

from .base import BaseFetcher, PaperMetadata


class NASAFetcher(BaseFetcher):
    """Fetcher for NASA research and space technology content"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        self.source_name = "nasa"
        self.rate_limit = config.get('RATE_LIMIT_NASA', 10)  # requests per second
        self.max_papers = config.get('MAX_PAPERS_NASA', 30)
        self.days_back = config.get('NASA_DAYS_BACK', 7)
        
        # NASA APIs
        self.nasa_api_key = config.get('NASA_API_KEY', 'DEMO_KEY')
        self.techport_base_url = "https://api.nasa.gov/techport/api"
        self.nasa_news_url = "https://api.nasa.gov/planetary/apod"
        
        logger.debug(f"NASA fetcher initialized with rate_limit={self.rate_limit}/s")
    
    def fetch_papers(self, keywords: List[str], categories: List[str] = None,
                    hours_back: int = 24, max_results: int = 100) -> List[PaperMetadata]:
        """Fetch space and technology content from NASA"""
        
        if not keywords:
            logger.warning("No keywords provided for NASA search")
            return []
        
        try:
            papers = []
            
            # Fetch from multiple NASA sources
            papers.extend(self._fetch_from_techport(keywords, hours_back))
            papers.extend(self._fetch_from_nasa_news(keywords, hours_back))
            papers.extend(self._fetch_from_space_rss(hours_back))
            
            # Limit results
            papers = papers[:max_results]
            
            logger.info(f"Fetched {len(papers)} items from NASA sources")
            return papers
            
        except Exception as e:
            logger.error(f"Error fetching from NASA: {e}")
            return []
    
    def _fetch_from_techport(self, keywords: List[str], hours_back: int = 24) -> List[PaperMetadata]:
        """Fetch from NASA TechPort API"""
        
        papers = []
        try:
            # TechPort projects API
            url = f"{self.techport_base_url}/projects"
            params = {
                'api_key': self.nasa_api_key,
                'updatedSince': (datetime.now() - timedelta(hours=hours_back)).strftime('%Y-%m-%d')
            }
            
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                projects = data.get('projects', [])
                
                for project in projects[:10]:  # Limit to first 10
                    try:
                        project_id = project.get('projectId')
                        if project_id:
                            paper = self._fetch_project_details(project_id, keywords)
                            if paper:
                                papers.append(paper)
                                
                    except Exception as e:
                        logger.warning(f"Error processing TechPort project: {e}")
                        continue
            else:
                logger.warning(f"TechPort API returned status {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Error fetching from TechPort: {e}")
        
        return papers
    
    def _fetch_project_details(self, project_id: int, keywords: List[str]) -> Optional[PaperMetadata]:
        """Fetch detailed project information"""
        
        try:
            url = f"{self.techport_base_url}/projects/{project_id}"
            params = {'api_key': self.nasa_api_key}
            
            response = requests.get(url, params=params, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                project = data.get('project', {})
                
                title = project.get('title', '').strip()
                description = project.get('description', '').strip()
                
                # Check keyword relevance
                text_to_check = f"{title} {description}".lower()
                if not any(keyword.lower() in text_to_check for keyword in keywords):
                    return None
                
                # Extract information
                benefits = project.get('benefits', '')
                technology_areas = project.get('primaryTechnologyArea', {})
                start_date = project.get('startDate', '')
                end_date = project.get('endDate', '')
                
                # Build abstract
                abstract_parts = []
                if description:
                    abstract_parts.append(description)
                if benefits:
                    abstract_parts.append(f"Benefits: {benefits}")
                
                abstract = " ".join(abstract_parts)
                
                # Extract categories
                categories = []
                if technology_areas:
                    categories.append(technology_areas.get('name', ''))
                
                return PaperMetadata(
                    title=title,
                    authors=['NASA'],
                    abstract=abstract,
                    url=f"https://techport.nasa.gov/view/{project_id}",
                    source=self.source_name,
                    published_at=start_date or datetime.now().strftime('%Y-%m-%d'),
                    categories=categories,
                    tags=self._extract_space_keywords(title, abstract)
                )
                
        except Exception as e:
            logger.warning(f"Error fetching project details for {project_id}: {e}")
            return None
    
    def _fetch_from_nasa_news(self, keywords: List[str], hours_back: int = 24) -> List[PaperMetadata]:
        """Fetch from NASA news and APOD"""
        
        papers = []
        try:
            # Astronomy Picture of the Day
            params = {
                'api_key': self.nasa_api_key,
                'count': 5  # Get recent items
            }
            
            response = requests.get(self.nasa_news_url, params=params, timeout=20)
            
            if response.status_code == 200:
                items = response.json()
                if not isinstance(items, list):
                    items = [items]
                
                for item in items:
                    try:
                        title = item.get('title', '').strip()
                        explanation = item.get('explanation', '').strip()
                        url = item.get('url', '')
                        date = item.get('date', datetime.now().strftime('%Y-%m-%d'))
                        
                        # Check relevance
                        text_to_check = f"{title} {explanation}".lower()
                        space_keywords = ['space', 'astronomy', 'galaxy', 'planet', 'satellite', 'rocket']
                        
                        if any(keyword.lower() in text_to_check for keyword in space_keywords):
                            paper = PaperMetadata(
                                title=f"NASA APOD: {title}",
                                authors=['NASA'],
                                abstract=explanation,
                                url=item.get('hdurl', url),
                                source=self.source_name,
                                published_at=date,
                                categories=['Astronomy', 'Space Science'],
                                tags=self._extract_space_keywords(title, explanation)
                            )
                            papers.append(paper)
                        
                    except Exception as e:
                        logger.warning(f"Error processing NASA APOD item: {e}")
                        continue
        
        except Exception as e:
            logger.warning(f"Error fetching from NASA APOD: {e}")
        
        return papers
    
    def _fetch_from_space_rss(self, hours_back: int = 24) -> List[PaperMetadata]:
        """Fetch from space-related RSS feeds"""
        
        papers = []
        rss_feeds = [
            "https://www.nasa.gov/rss/dyn/breaking_news.rss",
            "https://www.space.com/feeds/all",
            "https://spacenews.com/feed/"
        ]
        
        try:
            import feedparser
            
            for feed_url in rss_feeds:
                try:
                    feed = feedparser.parse(feed_url)
                    
                    for entry in feed.entries[:5]:  # Limit per feed
                        try:
                            title = entry.get('title', '').strip()
                            summary = entry.get('summary', '').strip()
                            link = entry.get('link', '')
                            published = entry.get('published', '')
                            
                            # Check if recent
                            if published:
                                try:
                                    pub_date = datetime.strptime(published[:19], '%Y-%m-%dT%H:%M:%S')
                                    if (datetime.now() - pub_date).total_seconds() / 3600 > hours_back:
                                        continue
                                except:
                                    pass
                            
                            # Check space relevance
                            text_to_check = f"{title} {summary}".lower()
                            space_terms = ['space', 'rocket', 'satellite', 'nasa', 'spacex', 'mars', 'moon', 'iss']
                            
                            if any(term in text_to_check for term in space_terms):
                                paper = PaperMetadata(
                                    title=title,
                                    authors=[feed.feed.get('title', 'Space News')],
                                    abstract=summary or title,
                                    url=link,
                                    source=self.source_name,
                                    published_at=published[:10] if published else datetime.now().strftime('%Y-%m-%d'),
                                    categories=['Space News'],
                                    tags=self._extract_space_keywords(title, summary)
                                )
                                papers.append(paper)
                        
                        except Exception as e:
                            logger.warning(f"Error processing RSS entry: {e}")
                            continue
                
                except Exception as e:
                    logger.warning(f"Error parsing RSS feed {feed_url}: {e}")
                    continue
        
        except ImportError:
            logger.warning("feedparser library not available for RSS parsing")
        
        return papers
    
    def _extract_space_keywords(self, title: str, abstract: str) -> List[str]:
        """Extract space-related keywords from text"""
        
        text = f"{title} {abstract}".lower()
        space_keywords = [
            'spacecraft', 'satellite', 'rocket', 'mars', 'moon', 'asteroid',
            'planetary', 'solar system', 'telescope', 'observatory', 'mission',
            'launch', 'orbit', 'space station', 'exploration', 'astronaut',
            'robotics', 'autonomous systems', 'navigation', 'communication',
            'earth observation', 'climate monitoring', 'solar system'
        ]
        
        found_keywords = []
        for keyword in space_keywords:
            if keyword in text:
                found_keywords.append(keyword)
        
        return found_keywords[:5]
    
    def test_connection(self) -> bool:
        """Test NASA API connection"""
        
        try:
            # Test TechPort API
            url = f"{self.techport_base_url}/projects"
            params = {'api_key': self.nasa_api_key}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                logger.info("NASA API connection test successful")
                return True
            else:
                logger.warning(f"NASA API test returned status {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"NASA API connection test failed: {e}")
            return False


def create_nasa_fetcher(config: Dict[str, Any]) -> NASAFetcher:
    """Factory function to create NASA fetcher"""
    return NASAFetcher(config)