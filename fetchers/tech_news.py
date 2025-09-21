"""
Technology and AI news fetcher from multiple sources
"""
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import requests
from loguru import logger

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    logger.warning("feedparser not available. Install with: pip install feedparser")

from .base import BaseFetcher, PaperMetadata


class TechNewsFetcher(BaseFetcher):
    """Fetcher for technology and AI news from various sources"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        self.source_name = "tech_news"
        self.rate_limit = config.get('RATE_LIMIT_TECH_NEWS', 10)
        self.max_papers = config.get('MAX_PAPERS_TECH_NEWS', 25)
        self.days_back = config.get('TECH_NEWS_DAYS_BACK', 3)
        
        # Tech news RSS feeds
        self.tech_feeds = {
            'TechCrunch AI': 'https://techcrunch.com/category/artificial-intelligence/feed/',
            'MIT Technology Review': 'https://www.technologyreview.com/feed/',
            'Ars Technica': 'https://feeds.arstechnica.com/arstechnica/index',
            'IEEE Spectrum': 'https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss',
            'VentureBeat AI': 'https://venturebeat.com/ai/feed/',
            'AI News': 'https://www.artificialintelligence-news.com/feed/',
            'The Register': 'https://www.theregister.com/headlines.atom',
            'Wired Science': 'https://www.wired.com/feed/category/science/latest/rss',
            'Nature Technology': 'https://www.nature.com/subjects/electronic-engineering.rss',
            'Science Daily AI': 'https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml',
            # Medium RSS feeds for AI, tech, and space content
            'Medium AI': 'https://medium.com/feed/tag/artificial-intelligence',
            'Medium Machine Learning': 'https://medium.com/feed/tag/machine-learning',
            'Medium Technology': 'https://medium.com/feed/tag/technology',
            'Medium Data Science': 'https://medium.com/feed/tag/data-science',
            'Medium Space': 'https://medium.com/feed/tag/space',
            'Medium Blockchain': 'https://medium.com/feed/tag/blockchain',
            'Medium Programming': 'https://medium.com/feed/tag/programming'
        }
        
        # GitHub trending API for popular AI projects
        self.github_api_base = "https://api.github.com"
        
        logger.debug(f"Tech News fetcher initialized with {len(self.tech_feeds)} feeds (including Medium)")
    
    def _parse_date(self, date_string: str) -> Optional[datetime]:
        """Parse date string to datetime object"""
        if not date_string:
            return datetime.now()
        
        try:
            # Try multiple date formats
            for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                try:
                    return datetime.strptime(date_string[:len(fmt)], fmt)
                except ValueError:
                    continue
            return datetime.now()
        except:
            return datetime.now()
    
    def is_enabled(self) -> bool:
        """Check if tech news fetcher is enabled in config"""
        return self.config.get("ENABLE_TECH_NEWS", False)
    
    def fetch_papers(self, keywords: List[str], categories: List[str] = None,
                    hours_back: int = 24, max_results: int = 100) -> List[PaperMetadata]:
        """Fetch tech news and AI developments"""
        
        if not keywords:
            logger.warning("No keywords provided for tech news search")
            return []
        
        try:
            papers = []
            
            # Fetch from RSS feeds
            if FEEDPARSER_AVAILABLE:
                papers.extend(self._fetch_from_rss_feeds(keywords, hours_back))
            
            # Fetch trending GitHub projects
            papers.extend(self._fetch_github_trending(keywords, hours_back))
            
            # Sort by relevance and date
            papers = self._rank_by_relevance(papers, keywords)
            
            # Limit results
            papers = papers[:max_results]
            
            logger.info(f"Fetched {len(papers)} tech news items")
            return papers
            
        except Exception as e:
            logger.error(f"Error fetching tech news: {e}")
            return []
    
    def _fetch_from_rss_feeds(self, keywords: List[str], hours_back: int = 24) -> List[PaperMetadata]:
        """Fetch from technology RSS feeds"""
        
        papers = []
        
        for feed_name, feed_url in self.tech_feeds.items():
            try:
                logger.debug(f"Fetching from {feed_name}")
                
                feed = feedparser.parse(feed_url)
                
                if not hasattr(feed, 'entries'):
                    continue
                
                for entry in feed.entries[:5]:  # Limit per feed
                    try:
                        paper = self._parse_rss_entry(entry, feed_name, keywords, hours_back)
                        if paper:
                            papers.append(paper)
                    except Exception as e:
                        logger.warning(f"Error parsing entry from {feed_name}: {e}")
                        continue
                
                # Rate limiting between feeds
                time.sleep(1.0 / self.rate_limit)
                
            except Exception as e:
                logger.warning(f"Error fetching from {feed_name}: {e}")
                continue
        
        return papers
    
    def _parse_rss_entry(self, entry: Dict[str, Any], feed_name: str, keywords: List[str], hours_back: int = 24) -> Optional[PaperMetadata]:
        """Parse RSS entry into PaperMetadata"""
        
        try:
            title = entry.get('title', '').strip()
            summary = entry.get('summary', '').strip()
            link = entry.get('link', '')
            published = entry.get('published', '')
            authors = [author.get('name', '') for author in entry.get('authors', [])]
            
            if not authors:
                authors = [feed_name]
            
            # Check if recent
            if published:
                try:
                    # Try multiple date formats
                    for date_format in ['%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d']:
                        try:
                            pub_date = datetime.strptime(published[:25], date_format)
                            if (datetime.now(pub_date.tzinfo if pub_date.tzinfo else None) - pub_date).total_seconds() / 3600 > hours_back:
                                return None
                            break
                        except:
                            continue
                except:
                    pass  # If date parsing fails, include anyway
            
            # Check relevance to keywords
            text_to_check = f"{title} {summary}".lower()
            if not self._is_relevant_to_keywords(text_to_check, keywords):
                return None
            
            # Extract categories
            categories = self._extract_tech_categories(title, summary)
            
            # Generate meaningful abstract
            abstract = summary if summary else f"Technology news from {feed_name}: {title}"
            
            return PaperMetadata(
                title=title,
                authors=authors,
                abstract=abstract,
                url=link,
                source=self.source_name,
                published_at=self._parse_date(published),
                categories=categories,
                tags=self._extract_tech_keywords(title, summary)
            )
            
        except Exception as e:
            logger.warning(f"Error parsing RSS entry: {e}")
            return None
    
    def _fetch_github_trending(self, keywords: List[str], hours_back: int = 24) -> List[PaperMetadata]:
        """Fetch trending AI/tech projects from GitHub"""
        
        papers = []
        
        try:
            # Search for trending AI repositories
            ai_queries = [
                'artificial intelligence',
                'machine learning',
                'deep learning',
                'neural network',
                'computer vision',
                'natural language processing'
            ]
            
            for query in ai_queries[:3]:  # Limit queries
                try:
                    url = f"{self.github_api_base}/search/repositories"
                    params = {
                        'q': f'{query} stars:>100',
                        'sort': 'updated',
                        'order': 'desc',
                        'per_page': 5
                    }
                    
                    response = requests.get(url, params=params, timeout=20)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        for repo in data.get('items', []):
                            try:
                                paper = self._parse_github_repo(repo, keywords, hours_back)
                                if paper:
                                    papers.append(paper)
                            except Exception as e:
                                logger.warning(f"Error parsing GitHub repo: {e}")
                                continue
                    
                    time.sleep(1.0 / self.rate_limit)
                    
                except Exception as e:
                    logger.warning(f"Error searching GitHub for '{query}': {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Error fetching from GitHub: {e}")
        
        return papers
    
    def _parse_github_repo(self, repo: Dict[str, Any], keywords: List[str], hours_back: int = 24) -> Optional[PaperMetadata]:
        """Parse GitHub repository into PaperMetadata"""
        
        try:
            name = repo.get('name', '')
            full_name = repo.get('full_name', '')
            description = repo.get('description', '')
            html_url = repo.get('html_url', '')
            stars = repo.get('stargazers_count', 0)
            language = repo.get('language', '')
            updated_at = repo.get('updated_at', '')
            
            # Check if updated recently
            if updated_at:
                try:
                    update_date = datetime.strptime(updated_at[:19], '%Y-%m-%dT%H:%M:%S')
                    if (datetime.now() - update_date).total_seconds() / 3600 > hours_back * 2:  # More lenient for GitHub
                        return None
                except:
                    pass
            
            # Check relevance
            text_to_check = f"{name} {description}".lower()
            if not self._is_relevant_to_keywords(text_to_check, keywords):
                return None
            
            # Create title and abstract
            title = f"GitHub Project: {name}"
            abstract = f"{description} | Language: {language} | Stars: {stars} | Project: {full_name}"
            
            return PaperMetadata(
                title=title,
                authors=[full_name.split('/')[0] if '/' in full_name else 'GitHub User'],
                abstract=abstract,
                url=html_url,
                source=self.source_name,
                published_at=self._parse_date(updated_at),
                categories=['Open Source', 'Software', language] if language else ['Open Source', 'Software'],
                tags=self._extract_tech_keywords(name, description)
            )
            
        except Exception as e:
            logger.warning(f"Error parsing GitHub repo: {e}")
            return None
    
    def _is_relevant_to_keywords(self, text: str, keywords: List[str]) -> bool:
        """Check if content is relevant to any keyword"""
        
        # Check main keywords
        for keyword in keywords:
            if keyword.lower() in text:
                return True
        
        # Check tech-specific terms
        tech_terms = [
            'ai', 'artificial intelligence', 'machine learning', 'deep learning',
            'neural network', 'computer vision', 'nlp', 'robotics',
            'quantum computing', 'blockchain', 'cybersecurity', 'cloud computing',
            'iot', 'internet of things', 'automation', 'algorithm',
            'data science', 'big data', 'analytics'
        ]
        
        return any(term in text for term in tech_terms)
    
    def _extract_tech_categories(self, title: str, content: str) -> List[str]:
        """Extract technology categories"""
        
        text = f"{title} {content}".lower()
        categories = []
        
        category_map = {
            'artificial intelligence': 'AI',
            'machine learning': 'Machine Learning',
            'deep learning': 'Deep Learning',
            'computer vision': 'Computer Vision',
            'natural language': 'NLP',
            'robotics': 'Robotics',
            'quantum': 'Quantum Computing',
            'blockchain': 'Blockchain',
            'cybersecurity': 'Cybersecurity',
            'cloud': 'Cloud Computing',
            'iot': 'IoT',
            'automation': 'Automation',
            'data science': 'Data Science',
            'startup': 'Startup',
            'funding': 'Investment'
        }
        
        for term, category in category_map.items():
            if term in text:
                categories.append(category)
        
        return categories[:3] if categories else ['Technology']
    
    def _extract_tech_keywords(self, title: str, content: str) -> List[str]:
        """Extract technology keywords"""
        
        text = f"{title} {content}".lower()
        
        tech_keywords = [
            'artificial intelligence', 'machine learning', 'deep learning',
            'neural networks', 'computer vision', 'natural language processing',
            'robotics', 'automation', 'quantum computing', 'blockchain',
            'cybersecurity', 'cloud computing', 'iot', 'data science',
            'big data', 'analytics', 'algorithm', 'startup', 'venture capital'
        ]
        
        found_keywords = []
        for keyword in tech_keywords:
            if keyword in text:
                found_keywords.append(keyword)
        
        return found_keywords[:5]
    
    def _rank_by_relevance(self, papers: List[PaperMetadata], keywords: List[str]) -> List[PaperMetadata]:
        """Rank papers by relevance to keywords and recency"""
        
        def calculate_score(paper: PaperMetadata) -> float:
            score = 0.0
            text = f"{paper.title} {paper.abstract}".lower()
            
            # Keyword relevance (higher weight for exact matches)
            for keyword in keywords:
                if keyword.lower() in text:
                    score += 2.0
            
            # Category bonus
            if paper.categories:
                ai_categories = ['AI', 'Machine Learning', 'Deep Learning', 'Computer Vision', 'NLP']
                if any(cat in ai_categories for cat in paper.categories):
                    score += 1.0
            
            # Recency bonus
            try:
                if paper.published_at:
                    days_old = (datetime.now() - paper.published_at).days
                    if days_old <= 1:
                        score += 1.0
                    elif days_old <= 3:
                        score += 0.5
            except:
                pass
            
            # GitHub stars bonus
            if paper.title.startswith("GitHub Project:") and "Stars:" in paper.abstract:
                try:
                    # Extract stars from abstract (format: "... | Stars: 123 | ...")
                    stars_part = paper.abstract.split("Stars:")[1].split("|")[0].strip()
                    stars = int(stars_part)
                    if stars > 1000:
                        score += 1.0
                    elif stars > 100:
                        score += 0.5
                except:
                    pass
            
            return score
        
        # Sort by score (descending)
        papers.sort(key=calculate_score, reverse=True)
        return papers
    
    def test_connection(self) -> bool:
        """Test tech news sources connection"""
        
        try:
            # Test GitHub API
            response = requests.get(f"{self.github_api_base}/rate_limit", timeout=10)
            
            if response.status_code == 200:
                logger.info("Tech news sources connection test successful")
                return True
            else:
                logger.warning("Tech news connection test failed")
                return False
                
        except Exception as e:
            logger.error(f"Tech news connection test failed: {e}")
            return False


def create_tech_news_fetcher(config: Dict[str, Any]) -> TechNewsFetcher:
    """Factory function to create tech news fetcher"""
    return TechNewsFetcher(config)