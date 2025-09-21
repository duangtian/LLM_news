"""
Unit tests for pipeline components
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from storage.models import PaperCreate, SummaryResponse
from pipeline.normalize import DataNormalizer
from pipeline.filter_rank import ContentFilter, PaperRanker, FilterRankPipeline
from pipeline.summarize import RuleBasedSummarizer, SummarizerFactory
from fetchers.base import PaperMetadata


class TestDataNormalizer:
    """Test DataNormalizer class"""
    
    @pytest.fixture
    def config(self):
        return {
            'SUMMARY_MIN_LENGTH': 150,
            'SUMMARY_MAX_LENGTH': 250
        }
    
    @pytest.fixture
    def normalizer(self, config):
        return DataNormalizer(config)
    
    def test_clean_title(self, normalizer):
        # Test basic cleaning
        assert normalizer._clean_title("  Test Title  ") == "Test Title"
        assert normalizer._clean_title("Title: Test Paper") == "Test Paper"
        assert normalizer._clean_title("TITLE: Test Paper") == "Test Paper"
        
        # Test long title truncation
        long_title = "A" * 350
        cleaned = normalizer._clean_title(long_title)
        assert len(cleaned) <= 300
        assert cleaned.endswith("...")
    
    def test_clean_abstract(self, normalizer):
        # Test basic cleaning
        assert normalizer._clean_abstract("  Test abstract  ") == "Test abstract"
        assert normalizer._clean_abstract("Abstract: Test content") == "Test content"
        
        # Test long abstract truncation
        long_abstract = "A" * 2100
        cleaned = normalizer._clean_abstract(long_abstract)
        assert len(cleaned) <= 2000
        assert cleaned.endswith("...")
    
    def test_normalize_authors(self, normalizer):
        # Test normal authors
        authors = ["John Doe", "Jane Smith"]
        assert normalizer._normalize_authors(authors) == ["John Doe", "Jane Smith"]
        
        # Test author cleaning
        authors_with_titles = ["Dr. John Doe", "Prof. Jane Smith"]
        normalized = normalizer._normalize_authors(authors_with_titles)
        assert "John Doe" in normalized
        assert "Jane Smith" in normalized
        
        # Test empty authors
        assert normalizer._normalize_authors([]) == []
        assert normalizer._normalize_authors(None) == []
    
    def test_normalize_single_paper(self, normalizer):
        paper = PaperMetadata(
            title="Test Paper Title",
            authors=["John Doe", "Jane Smith"],
            abstract="This is a test abstract that is long enough to pass validation requirements.",
            url="https://example.com/paper",
            source="test",
            doi="10.1234/test"
        )
        
        normalized = normalizer._normalize_single_paper(paper)
        
        assert normalized is not None
        assert normalized.title == "Test Paper Title"
        assert len(normalized.authors) == 2
        assert normalized.doi == "10.1234/test"
        assert normalized.source == "test"
    
    def test_normalize_single_paper_invalid(self, normalizer):
        # Test paper with short abstract
        paper = PaperMetadata(
            title="Test Paper Title",
            authors=["John Doe"],
            abstract="Short",  # Too short
            url="https://example.com/paper",
            source="test"
        )
        
        normalized = normalizer._normalize_single_paper(paper)
        assert normalized is None


class TestContentFilter:
    """Test ContentFilter class"""
    
    @pytest.fixture
    def config(self):
        return {
            'KEYWORDS_INCLUDE': 'machine learning,AI,deep learning',
            'KEYWORDS_EXCLUDE': 'spam,advertisement',
            'SUMMARY_MIN_LENGTH': 50
        }
    
    @pytest.fixture
    def filter(self, config):
        return ContentFilter(config)
    
    def test_parse_keywords(self, filter):
        keywords = filter._parse_keywords("machine learning, AI, deep learning")
        assert "machine learning" in keywords
        assert "ai" in keywords
        assert "deep learning" in keywords
    
    def test_passes_quality_check(self, filter):
        # Valid paper
        paper = PaperCreate(
            source="test",
            title="Valid Paper Title",
            authors=["Author 1"],
            abstract="This is a valid abstract that is long enough to pass validation.",
            url="https://example.com"
        )
        assert filter._passes_quality_check(paper) == True
        
        # Invalid paper (short title)
        paper_invalid = PaperCreate(
            source="test",
            title="Short",  # Too short
            authors=["Author 1"],
            abstract="This is a valid abstract that is long enough to pass validation.",
            url="https://example.com"
        )
        assert filter._passes_quality_check(paper_invalid) == False
    
    def test_passes_keyword_filter(self, filter):
        # Paper with include keyword
        paper_valid = PaperCreate(
            source="test",
            title="Machine Learning Paper",
            authors=["Author 1"],
            abstract="This paper discusses machine learning techniques.",
            url="https://example.com"
        )
        assert filter._passes_keyword_filter(paper_valid) == True
        
        # Paper with exclude keyword
        paper_excluded = PaperCreate(
            source="test",
            title="Spam Paper",
            authors=["Author 1"],
            abstract="This is spam content.",
            url="https://example.com"
        )
        assert filter._passes_keyword_filter(paper_excluded) == False
    
    def test_is_spam(self, filter):
        # Normal paper
        paper_normal = PaperCreate(
            source="test",
            title="Normal Research Paper",
            authors=["Author 1"],
            abstract="This is a normal research paper about machine learning.",
            url="https://example.com"
        )
        assert filter._is_spam(paper_normal) == False
        
        # Spam paper
        paper_spam = PaperCreate(
            source="test",
            title="BUY NOW! SPECIAL OFFER!",
            authors=["Spammer"],
            abstract="Click here to buy our special offer!",
            url="https://spam.com"
        )
        assert filter._is_spam(paper_spam) == True


class TestPaperRanker:
    """Test PaperRanker class"""
    
    @pytest.fixture
    def config(self):
        return {
            'KEYWORDS_INCLUDE': 'machine learning,AI,deep learning'
        }
    
    @pytest.fixture
    def ranker(self, config):
        return PaperRanker(config)
    
    def test_keyword_score(self, ranker):
        # Text with keywords
        text_with_keywords = "machine learning and deep learning techniques"
        score = ranker._keyword_score(text_with_keywords)
        assert score > 0
        
        # Text without keywords
        text_without_keywords = "completely unrelated content"
        score = ranker._keyword_score(text_without_keywords)
        assert score >= 0
    
    def test_recency_score(self, ranker):
        # Recent paper
        recent_date = datetime.utcnow()
        score = ranker._recency_score(recent_date)
        assert score == 1.0
        
        # Old paper
        old_date = datetime(2020, 1, 1)
        score = ranker._recency_score(old_date)
        assert score < 1.0
        
        # No date
        score = ranker._recency_score(None)
        assert score == 0.3
    
    def test_source_score(self, ranker):
        # arXiv source
        score = ranker._source_score('arxiv')
        assert score == 0.8
        
        # Unknown source
        score = ranker._source_score('unknown')
        assert score == 0.5
    
    def test_calculate_relevance_score(self, ranker):
        paper = PaperCreate(
            source="arxiv",
            title="Machine Learning Paper",
            authors=["Author 1"],
            abstract="This paper discusses machine learning and deep learning techniques.",
            url="https://example.com",
            published_at=datetime.utcnow()
        )
        
        score = ranker._calculate_relevance_score(paper)
        assert 0 <= score <= 1
        assert score > 0.5  # Should be high due to keywords and recency


class TestRuleBasedSummarizer:
    """Test RuleBasedSummarizer class"""
    
    @pytest.fixture
    def config(self):
        return {
            'SUMMARY_MIN_LENGTH': 150,
            'SUMMARY_MAX_LENGTH': 250,
            'TLDR_MAX_LENGTH': 2
        }
    
    @pytest.fixture
    def summarizer(self, config):
        return RuleBasedSummarizer(config)
    
    def test_summarize(self, summarizer):
        paper = PaperCreate(
            source="arxiv",
            title="Deep Learning for Computer Vision",
            authors=["John Doe", "Jane Smith"],
            abstract="This paper presents a new deep learning approach for computer vision tasks. We propose a novel neural network architecture that achieves state-of-the-art results on standard benchmarks.",
            url="https://arxiv.org/abs/2024.1234"
        )
        
        result = summarizer.summarize(paper)
        
        assert isinstance(result, SummaryResponse)
        assert len(result.summary_thai) > 0
        assert len(result.tldr_thai) > 0
        assert result.word_count > 0
    
    def test_extract_main_topic(self, summarizer):
        # Test machine learning
        title = "Machine Learning for Image Recognition"
        topic = summarizer._extract_main_topic(title)
        assert topic == "การเรียนรู้ของเครื่อง"
        
        # Test computer vision
        title = "Computer Vision Applications in Healthcare"
        topic = summarizer._extract_main_topic(title)
        assert topic == "การมองเห็นด้วยคอมพิวเตอร์"
        
        # Test unknown topic
        title = "Unknown Topic Paper"
        topic = summarizer._extract_main_topic(title)
        assert topic == "เทคโนโลยี AI"
    
    def test_clean_text(self, summarizer):
        # Test markdown removal
        text = "This is **bold** and *italic* text with `code`"
        cleaned = summarizer._clean_text(text)
        assert "**" not in cleaned
        assert "*" not in cleaned
        assert "`" not in cleaned
        
        # Test unwanted phrase removal
        text = "TL;DR: This is a summary"
        cleaned = summarizer._clean_text(text)
        assert "TL;DR:" not in cleaned


class TestSummarizerFactory:
    """Test SummarizerFactory class"""
    
    def test_create_rule_based_summarizer(self):
        config = {
            'SUMMARIZER_MODE': 'rule_based',
            'SUMMARY_MIN_LENGTH': 150,
            'SUMMARY_MAX_LENGTH': 250
        }
        
        summarizer = SummarizerFactory.create_summarizer(config)
        assert isinstance(summarizer, RuleBasedSummarizer)
    
    def test_create_openai_summarizer_fallback(self):
        config = {
            'SUMMARIZER_MODE': 'openai',
            'SUMMARY_MIN_LENGTH': 150,
            'SUMMARY_MAX_LENGTH': 250
            # No API key provided - should fallback to rule-based
        }
        
        summarizer = SummarizerFactory.create_summarizer(config)
        assert isinstance(summarizer, RuleBasedSummarizer)


class TestFilterRankPipeline:
    """Test FilterRankPipeline class"""
    
    @pytest.fixture
    def config(self):
        return {
            'KEYWORDS_INCLUDE': 'machine learning,AI',
            'KEYWORDS_EXCLUDE': 'spam',
            'MAX_PAPERS_PER_DAY': 3,
            'SUMMARY_MIN_LENGTH': 50
        }
    
    @pytest.fixture
    def pipeline(self, config):
        return FilterRankPipeline(config)
    
    def test_process_papers(self, pipeline):
        papers = [
            PaperCreate(
                source="test",
                title="Machine Learning Paper 1",
                authors=["Author 1"],
                abstract="This paper discusses machine learning techniques and their applications in various domains.",
                url="https://example.com/1",
                published_at=datetime.utcnow()
            ),
            PaperCreate(
                source="test",
                title="AI Research Paper 2",
                authors=["Author 2"],
                abstract="This paper presents new artificial intelligence algorithms for solving complex problems.",
                url="https://example.com/2",
                published_at=datetime.utcnow()
            ),
            PaperCreate(
                source="test",
                title="Spam Paper",
                authors=["Spammer"],
                abstract="This is spam content that should be filtered out by the system.",
                url="https://spam.com",
                published_at=datetime.utcnow()
            )
        ]
        
        result = pipeline.process_papers(papers)
        
        # Should filter out spam and return top papers
        assert len(result) <= 3
        assert all("spam" not in paper.title.lower() for paper in result)


if __name__ == '__main__':
    pytest.main([__file__])