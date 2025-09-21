"""
Data normalization pipeline to standardize paper metadata from different sources
"""
import json
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger

from fetchers.base import PaperMetadata
from storage.models import PaperCreate


class DataNormalizer:
    """Normalizes paper metadata from different sources into standard format"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def normalize_papers(self, papers: List[PaperMetadata]) -> List[PaperCreate]:
        """Normalize a list of papers to standard format"""
        normalized = []
        
        for paper in papers:
            try:
                normalized_paper = self._normalize_single_paper(paper)
                if normalized_paper:
                    normalized.append(normalized_paper)
            except Exception as e:
                logger.error(f"Error normalizing paper {paper.title[:50]}: {e}")
                continue
        
        logger.info(f"Normalized {len(normalized)}/{len(papers)} papers")
        return normalized
    
    def _normalize_single_paper(self, paper: PaperMetadata) -> PaperCreate:
        """Normalize a single paper"""
        
        # Clean and validate title
        title = self._clean_title(paper.title)
        if not title or len(title) < 10:
            logger.debug(f"Skipping paper with invalid title: {paper.title}")
            return None
        
        # Clean and validate abstract
        abstract = self._clean_abstract(paper.abstract)

        # Allow shorter abstracts for news/technology sources (e.g., Medium RSS often brief)
        min_len_standard = 50
        min_len_news = 20
        is_news_source = paper.source in {"tech_news", "nasa"}

        min_required = min_len_news if is_news_source else min_len_standard

        if not abstract or len(abstract) < min_required:
            # Try to synthesize a fallback abstract from title if news source
            if is_news_source:
                synthesized = f"News: {title}" if title else "Technology/space news item"
                if len(synthesized) >= min_required:
                    abstract = synthesized
                else:
                    # Final fallback: duplicate title to reach minimum length guard
                    abstract = (title + " - " + title)[:min_len_news+5] if title else synthesized
            else:
                logger.debug(f"Skipping paper with short abstract: {title[:50]}")
                return None
        
        # Normalize authors
        authors = self._normalize_authors(paper.authors)
        if not authors:
            logger.debug(f"Skipping paper with no authors: {title[:50]}")
            return None
        
        # Normalize dates
        published_at = self._normalize_date(paper.published_at)
        
        # Normalize categories and tags
        categories = self._normalize_categories(paper.categories, paper.source)
        tags = self._extract_tags(paper)
        
        # Build URL
        url = self._normalize_url(paper.url, paper.doi, paper.arxiv_id)
        
        return PaperCreate(
            source=paper.source,
            doi=paper.doi,
            arxiv_id=paper.arxiv_id,
            title=title,
            authors=authors,
            abstract=abstract,
            url=url,
            published_at=published_at,
            tags=tags,
            categories=categories
        )
    
    def _clean_title(self, title: str) -> str:
        """Clean and normalize title"""
        if not title:
            return ""
        
        # Remove extra whitespace
        title = " ".join(title.strip().split())
        
        # Remove common prefixes/suffixes
        prefixes_to_remove = ['Title:', 'TITLE:', 'Paper:']
        for prefix in prefixes_to_remove:
            if title.startswith(prefix):
                title = title[len(prefix):].strip()
        
        # Limit length
        if len(title) > 300:
            title = title[:297] + "..."
        
        return title
    
    def _clean_abstract(self, abstract: str) -> str:
        """Clean and normalize abstract"""
        if not abstract:
            return ""
        
        # Remove extra whitespace and newlines
        abstract = " ".join(abstract.strip().split())
        
        # Remove common prefixes
        prefixes_to_remove = ['Abstract:', 'ABSTRACT:', 'Summary:']
        for prefix in prefixes_to_remove:
            if abstract.startswith(prefix):
                abstract = abstract[len(prefix):].strip()
        
        # Limit length
        if len(abstract) > 2000:
            abstract = abstract[:1997] + "..."
        
        return abstract
    
    def _normalize_authors(self, authors: List[str]) -> List[str]:
        """Normalize author names"""
        if not authors:
            return []
        
        normalized_authors = []
        for author in authors:
            if not author or not isinstance(author, str):
                continue
                
            # Clean author name
            author = author.strip()
            if not author:
                continue
            
            # Remove common prefixes
            prefixes = ['Dr.', 'Prof.', 'Professor', 'PhD', 'Ph.D.']
            for prefix in prefixes:
                if author.startswith(prefix):
                    author = author[len(prefix):].strip()
            
            # Limit length
            if len(author) > 100:
                author = author[:97] + "..."
            
            normalized_authors.append(author)
        
        # Limit number of authors to avoid database bloat
        return normalized_authors[:20]
    
    def _normalize_date(self, date: datetime) -> datetime:
        """Normalize publication date"""
        if not date:
            return None
        
        # Ensure it's a datetime object
        if isinstance(date, str):
            try:
                # Try common date formats
                for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ']:
                    try:
                        return datetime.strptime(date, fmt)
                    except ValueError:
                        continue
                logger.warning(f"Could not parse date: {date}")
                return None
            except Exception:
                return None
        
        return date
    
    def _normalize_categories(self, categories: List[str], source: str) -> List[str]:
        """Normalize categories based on source"""
        if not categories:
            return []
        
        normalized = []
        for cat in categories:
            if not cat or not isinstance(cat, str):
                continue
            
            cat = cat.strip()
            if not cat:
                continue
            
            # Source-specific normalization
            if source == "arxiv":
                # Keep arXiv categories as-is (they're already standardized)
                normalized.append(cat)
            elif source == "crossref":
                # Normalize Crossref subjects
                cat = self._normalize_crossref_subject(cat)
                if cat:
                    normalized.append(cat)
            else:
                # Generic normalization
                normalized.append(cat[:50])  # Limit length
        
        return normalized[:10]  # Limit number of categories
    
    def _normalize_crossref_subject(self, subject: str) -> str:
        """Normalize Crossref subject to more standard categories"""
        subject_mapping = {
            'Computer Science': 'cs',
            'Mathematics': 'math',
            'Physics': 'physics',
            'Biology': 'bio',
            'Medicine': 'med',
            'Engineering': 'eng',
            'Statistics': 'stat'
        }
        
        subject_lower = subject.lower()
        for key, value in subject_mapping.items():
            if key.lower() in subject_lower:
                return value
        
        return subject[:50]  # Return original if no mapping found
    
    def _extract_tags(self, paper: PaperMetadata) -> List[str]:
        """Extract relevant tags from paper content"""
        tags = []
        
        # Use existing tags if available
        if paper.tags:
            tags.extend(paper.tags)
        
        # Extract tags from title and abstract
        text = f"{paper.title} {paper.abstract}".lower()
        
        # Common ML/AI keywords to extract as tags
        keywords = [
            'machine learning', 'deep learning', 'neural network', 'artificial intelligence',
            'computer vision', 'natural language processing', 'nlp', 'transformers',
            'diffusion', 'gan', 'generative', 'classification', 'regression',
            'reinforcement learning', 'supervised', 'unsupervised', 'pytorch', 'tensorflow'
        ]
        
        for keyword in keywords:
            if keyword in text:
                tags.append(keyword)
        
        # Extract from categories
        if paper.categories:
            for cat in paper.categories:
                if cat.startswith('cs.'):
                    # Convert arXiv categories to readable tags
                    category_map = {
                        'cs.AI': 'artificial intelligence',
                        'cs.LG': 'machine learning',
                        'cs.CV': 'computer vision',
                        'cs.CL': 'computational linguistics',
                        'cs.NE': 'neural networks'
                    }
                    if cat in category_map:
                        tags.append(category_map[cat])
        
        # Remove duplicates and limit
        tags = list(set(tags))[:15]
        return tags
    
    def _normalize_url(self, url: str, doi: str, arxiv_id: str) -> str:
        """Normalize and prioritize URLs"""
        
        # Prioritize DOI URL if available
        if doi:
            return f"https://doi.org/{doi}"
        
        # Prioritize arXiv URL if available
        if arxiv_id:
            return f"https://arxiv.org/abs/{arxiv_id}"
        
        # Use provided URL
        if url:
            return url
        
        # Fallback
        return "https://example.com/paper-not-found"


def create_normalizer(config: Dict[str, Any]) -> DataNormalizer:
    """Factory function to create data normalizer"""
    return DataNormalizer(config)