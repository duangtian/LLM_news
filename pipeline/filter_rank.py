"""
Content filtering and ranking pipeline for papers
"""
import re
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
from loguru import logger

from storage.models import PaperCreate


class ContentFilter:
    """Filters papers based on keywords, quality, and relevance"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.include_keywords = self._parse_keywords(config.get('KEYWORDS_INCLUDE', ''))
        self.exclude_keywords = self._parse_keywords(config.get('KEYWORDS_EXCLUDE', ''))
        self.min_abstract_length = int(config.get('SUMMARY_MIN_LENGTH', 50))
    
    def _parse_keywords(self, keywords_str: str) -> List[str]:
        """Parse comma-separated keywords"""
        if not keywords_str:
            return []
        return [kw.strip().lower() for kw in keywords_str.split(',') if kw.strip()]
    
    def filter_papers(self, papers: List[PaperCreate]) -> List[PaperCreate]:
        """Filter papers based on various criteria"""
        filtered = []
        
        for paper in papers:
            try:
                if self._should_include_paper(paper):
                    filtered.append(paper)
                else:
                    logger.debug(f"Filtered out: {paper.title[:50]}...")
            except Exception as e:
                logger.error(f"Error filtering paper {paper.title[:50]}: {e}")
                continue
        
        logger.info(f"Filtered {len(filtered)}/{len(papers)} papers")
        return filtered
    
    def _should_include_paper(self, paper: PaperCreate) -> bool:
        """Check if paper should be included"""
        
        # Basic quality checks
        if not self._passes_quality_check(paper):
            return False
        
        # Keyword filtering
        if not self._passes_keyword_filter(paper):
            return False
        
        # Category filtering
        if not self._passes_category_filter(paper):
            return False
        
        # Date filtering
        if not self._passes_date_filter(paper):
            return False
        
        return True
    
    def _passes_quality_check(self, paper: PaperCreate) -> bool:
        """Check basic quality criteria"""
        
        # Check minimum title length
        if not paper.title or len(paper.title) < 10:
            return False
        
        # Check minimum abstract length
        if not paper.abstract or len(paper.abstract) < self.min_abstract_length:
            return False
        
        # Check for authors
        if not paper.authors or len(paper.authors) == 0:
            return False
        
        # Check for spam indicators
        if self._is_spam(paper):
            return False
        
        return True
    
    def _is_spam(self, paper: PaperCreate) -> bool:
        """Check for spam indicators"""
        text = f"{paper.title} {paper.abstract}".lower()
        
        # Spam patterns
        spam_patterns = [
            r'buy now', r'click here', r'visit our website',
            r'special offer', r'limited time', r'act now',
            r'www\.', r'http[s]?://', r'contact us',
            r'advertisement', r'promotional'
        ]
        
        for pattern in spam_patterns:
            if re.search(pattern, text):
                logger.debug(f"Spam detected in: {paper.title[:50]}")
                return True
        
        # Check for excessive capitalization
        if len(paper.title) > 10 and sum(1 for c in paper.title if c.isupper()) / len(paper.title) > 0.5:
            return True
        
        return False
    
    def _passes_keyword_filter(self, paper: PaperCreate) -> bool:
        """Check keyword inclusion/exclusion"""
        text = f"{paper.title} {paper.abstract}".lower()
        
        # Check exclude keywords first
        if self.exclude_keywords:
            for keyword in self.exclude_keywords:
                if keyword in text:
                    logger.debug(f"Excluded by keyword '{keyword}': {paper.title[:50]}")
                    return False
        
        # Check include keywords
        if self.include_keywords:
            for keyword in self.include_keywords:
                if keyword in text:
                    return True
            logger.debug(f"No include keywords found: {paper.title[:50]}")
            return False
        
        # If no include keywords specified, pass by default
        return True
    
    def _passes_category_filter(self, paper: PaperCreate) -> bool:
        """Check category filtering"""
        # Always allow news sources regardless of academic category filters
        if paper.source in {"tech_news", "nasa"}:
            return True
        allowed_categories = self._parse_keywords(self.config.get('ARXIV_CATEGORIES', ''))
        
        if not allowed_categories:
            return True  # No category filtering
        
        if not paper.categories:
            return True  # No categories to filter on
        
        # Check if any category matches
        for category in paper.categories:
            if category.lower() in [cat.lower() for cat in allowed_categories]:
                return True
        
        logger.debug(f"No matching categories: {paper.title[:50]}")
        return False
    
    def _passes_date_filter(self, paper: PaperCreate) -> bool:
        """Check date filtering"""
        if not paper.published_at:
            return True  # No date to filter on
        
        # Only include papers from last 30 days
        cutoff = datetime.utcnow() - timedelta(days=30)
        if paper.published_at < cutoff:
            logger.debug(f"Too old: {paper.title[:50]}")
            return False
        
        return True


class PaperRanker:
    """Ranks papers by relevance and importance"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.include_keywords = self._parse_keywords(config.get('KEYWORDS_INCLUDE', ''))
    
    def _parse_keywords(self, keywords_str: str) -> List[str]:
        """Parse comma-separated keywords"""
        if not keywords_str:
            return []
        return [kw.strip().lower() for kw in keywords_str.split(',') if kw.strip()]
    
    def rank_papers(self, papers: List[PaperCreate]) -> List[Tuple[PaperCreate, float]]:
        """Rank papers by relevance score"""
        ranked = []
        
        for paper in papers:
            try:
                score = self._calculate_relevance_score(paper)
                ranked.append((paper, score))
            except Exception as e:
                logger.error(f"Error ranking paper {paper.title[:50]}: {e}")
                ranked.append((paper, 0.0))
        
        # Sort by score descending
        ranked.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"Ranked {len(ranked)} papers")
        return ranked
    
    def _calculate_relevance_score(self, paper: PaperCreate) -> float:
        """Calculate relevance score for a paper"""
        score = 0.0
        
        text = f"{paper.title} {paper.abstract}".lower()
        
        # Keyword relevance (40% of score)
        score += self._keyword_score(text) * 0.4
        
        # Recency bonus (20% of score)
        score += self._recency_score(paper.published_at) * 0.2
        
        # Quality indicators (20% of score)
        score += self._quality_score(paper) * 0.2
        
        # Source preference (10% of score) with slight boost for curated news sources so they aren't dominated by arxiv
        base_source_score = self._source_score(paper.source)
        if paper.source in {"tech_news", "nasa"}:
            base_source_score = min(1.0, base_source_score + 0.15)  # modest boost
        score += base_source_score * 0.1
        
        # Category bonus (10% of score)
        score += self._category_score(paper.categories) * 0.1

        # Tag/keyword emphasis: promote items explicitly about LLM / AI if tags captured
        try:
            if hasattr(paper, 'tags') and paper.tags:
                tags_l = [t.lower() for t in paper.tags]
                boost_terms = ['llm', 'large language model', 'gpt', 'artificial intelligence', 'machine learning']
                if any(term in tag for tag in tags_l for term in boost_terms):
                    score = min(1.0, score + 0.1)
        except Exception:
            pass
        
        return max(0.0, min(1.0, score))  # Clamp to [0, 1]
    
    def _keyword_score(self, text: str) -> float:
        """Score based on keyword matches"""
        if not self.include_keywords:
            return 0.5  # Neutral score if no keywords
        
        score = 0.0
        total_keywords = len(self.include_keywords)
        
        for keyword in self.include_keywords:
            # Count occurrences
            count = text.count(keyword)
            if count > 0:
                # Higher weight for title matches
                title_matches = text[:200].count(keyword)  # Approximate title
                keyword_score = min(1.0, count * 0.2 + title_matches * 0.3)
                score += keyword_score
        
        return score / total_keywords if total_keywords > 0 else 0.5
    
    def _recency_score(self, published_at: datetime) -> float:
        """Score based on publication recency"""
        if not published_at:
            return 0.3  # Neutral score if no date
        
        days_old = (datetime.utcnow() - published_at).days
        
        if days_old <= 1:
            return 1.0  # Brand new
        elif days_old <= 7:
            return 0.8  # Very recent
        elif days_old <= 30:
            return 0.6  # Recent
        elif days_old <= 90:
            return 0.4  # Somewhat recent
        else:
            return 0.2  # Old
    
    def _quality_score(self, paper: PaperCreate) -> float:
        """Score based on quality indicators"""
        score = 0.5  # Base score
        
        # Abstract length bonus
        if paper.abstract and len(paper.abstract) > 200:
            score += 0.2
        
        # Author count bonus (more authors often indicates collaboration)
        if paper.authors and len(paper.authors) > 1:
            score += min(0.2, len(paper.authors) * 0.05)
        
        # DOI availability bonus (indicates formal publication)
        if paper.doi:
            score += 0.1
        
        return min(1.0, score)
    
    def _source_score(self, source: str) -> float:
        """Score based on source preference"""
        source_weights = {
            'arxiv': 0.8,      # High quality, rapid publication
            'crossref': 0.6,   # Peer-reviewed but may be older
            'biorxiv': 0.7,    # Pre-prints but specialized
            'medRxiv': 0.7,    # Medical pre-prints
        }
        
        return source_weights.get(source.lower(), 0.5)
    
    def _category_score(self, categories: List[str]) -> float:
        """Score based on category preferences"""
        if not categories:
            return 0.5
        
        # Preferred categories
        preferred = ['cs.ai', 'cs.lg', 'cs.cl', 'cs.cv', 'stat.ml']
        
        for category in categories:
            if category.lower() in preferred:
                return 1.0
        
        # If it has categories but not preferred ones
        return 0.6


class FilterRankPipeline:
    """Combined filtering and ranking pipeline"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.filter = ContentFilter(config)
        self.ranker = PaperRanker(config)
        self.max_papers = int(config.get('MAX_PAPERS_PER_DAY', 5))
    
    def process_papers(self, papers: List[PaperCreate]) -> List[PaperCreate]:
        """Filter and rank papers, returning top N"""
        
        # Step 1: Filter papers
        filtered_papers = self.filter.filter_papers(papers)
        
        if not filtered_papers:
            logger.warning("No papers passed filtering")
            return []
        
        # Step 2: Rank papers
        ranked_papers = self.ranker.rank_papers(filtered_papers)
        
        # Step 3: Take top N with per-source quota adjustments so news items surface
        top_papers_scored = ranked_papers[:self.max_papers]

        # Enforce a minimum quota for tech/news sources (e.g., tech_news, nasa) if they exist
        min_news_quota = int(self.config.get('MIN_NEWS_QUOTA', 2))
        news_sources = {"tech_news", "nasa"}
        news_items = [ps for ps in ranked_papers if ps[0].source in news_sources]
        current_news = [p for p, s in top_papers_scored if p.source in news_sources]
        if len(current_news) < min_news_quota and news_items:
            needed = min_news_quota - len(current_news)
            # Add additional news items (skip ones already included)
            extra = []
            for paper, score in news_items:
                if paper not in current_news and paper not in [p for p, _ in top_papers_scored]:
                    extra.append((paper, score))
                if len(extra) >= needed:
                    break
            if extra:
                combined = top_papers_scored + extra
                # Re-trim to max_papers preferring higher scores overall
                combined.sort(key=lambda x: x[1], reverse=True)
                top_papers_scored = combined[:self.max_papers]
        
        # Log scores for debugging
        for i, (paper, score) in enumerate(top_papers_scored):
            logger.info(f"Rank {i+1}: {paper.title[:50]}... (score: {score:.3f})")
        
        return [paper for paper, score in top_papers_scored]


def create_filter_rank_pipeline(config: Dict[str, Any]) -> FilterRankPipeline:
    """Factory function to create filter-rank pipeline"""
    return FilterRankPipeline(config)