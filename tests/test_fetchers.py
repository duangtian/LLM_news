"""
Unit tests for fetchers
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from fetchers.base import PaperMetadata, BaseFetcher
from fetchers.arxiv import ArxivFetcher
from fetchers.crossref import CrossrefFetcher
from fetchers.manager import FetcherManager


class TestPaperMetadata:
    """Test PaperMetadata class"""
    
    def test_get_identifier_with_doi(self):
        paper = PaperMetadata(
            title="Test Paper",
            authors=["Author 1"],
            abstract="Test abstract",
            url="https://example.com",
            source="test",
            doi="10.1234/test"
        )
        assert paper.get_identifier() == "10.1234/test"
        assert paper.get_identifier_type() == "doi"
    
    def test_get_identifier_with_arxiv_id(self):
        paper = PaperMetadata(
            title="Test Paper",
            authors=["Author 1"],
            abstract="Test abstract",
            url="https://example.com",
            source="test",
            arxiv_id="2024.1234"
        )
        assert paper.get_identifier() == "2024.1234"
        assert paper.get_identifier_type() == "arxiv_id"
    
    def test_get_identifier_with_hash(self):
        paper = PaperMetadata(
            title="Test Paper",
            authors=["Author 1"],
            abstract="Test abstract",
            url="https://example.com",
            source="test",
            published_at=datetime(2024, 1, 1)
        )
        identifier = paper.get_identifier()
        assert len(identifier) == 32  # MD5 hash length
        assert paper.get_identifier_type() == "hash"


class TestBaseFetcher:
    """Test BaseFetcher class"""
    
    def test_is_enabled_true(self):
        config = {'ENABLE_TEST': True}
        
        class TestFetcher(BaseFetcher):
            def __init__(self, config):
                super().__init__(config)
                self.name = 'test'
            
            def fetch_papers(self, keywords, categories=None, hours_back=24, max_results=100):
                return []
            
            def test_connection(self):
                return True
        
        fetcher = TestFetcher(config)
        assert fetcher.is_enabled() == True
    
    def test_is_enabled_false(self):
        config = {'ENABLE_TEST': False}
        
        class TestFetcher(BaseFetcher):
            def __init__(self, config):
                super().__init__(config)
                self.name = 'test'
            
            def fetch_papers(self, keywords, categories=None, hours_back=24, max_results=100):
                return []
            
            def test_connection(self):
                return True
        
        fetcher = TestFetcher(config)
        assert fetcher.is_enabled() == False
    
    def test_clean_text(self):
        config = {}
        
        class TestFetcher(BaseFetcher):
            def __init__(self, config):
                super().__init__(config)
                self.name = 'test'
            
            def fetch_papers(self, keywords, categories=None, hours_back=24, max_results=100):
                return []
            
            def test_connection(self):
                return True
        
        fetcher = TestFetcher(config)
        
        # Test cleaning whitespace
        assert fetcher.clean_text("  hello   world  ") == "hello world"
        assert fetcher.clean_text("hello\\nworld\\n") == "hello world"
        assert fetcher.clean_text("") == ""
    
    def test_parse_authors_list(self):
        config = {}
        
        class TestFetcher(BaseFetcher):
            def __init__(self, config):
                super().__init__(config)
                self.name = 'test'
            
            def fetch_papers(self, keywords, categories=None, hours_back=24, max_results=100):
                return []
            
            def test_connection(self):
                return True
        
        fetcher = TestFetcher(config)
        
        # Test list input
        authors = ["Author 1", "Author 2"]
        assert fetcher.parse_authors(authors) == ["Author 1", "Author 2"]
        
        # Test string input
        assert fetcher.parse_authors("Author 1, Author 2") == ["Author 1", "Author 2"]
        assert fetcher.parse_authors("Author 1; Author 2") == ["Author 1", "Author 2"]
        assert fetcher.parse_authors("Author 1 and Author 2") == ["Author 1", "Author 2"]
        
        # Test empty input
        assert fetcher.parse_authors("") == []
        assert fetcher.parse_authors(None) == []


class TestArxivFetcher:
    """Test ArxivFetcher class"""
    
    @pytest.fixture
    def config(self):
        return {
            'ENABLE_ARXIV': True,
            'RATE_LIMIT_ARXIV': 10
        }
    
    @pytest.fixture
    def fetcher(self, config):
        return ArxivFetcher(config)
    
    def test_initialization(self, fetcher):
        assert fetcher.name == 'arxiv'
        assert fetcher.BASE_URL == "http://export.arxiv.org/api/query"
    
    def test_is_valid_category(self, fetcher):
        assert fetcher._is_valid_category('cs.AI') == True
        assert fetcher._is_valid_category('cs.LG') == True
        assert fetcher._is_valid_category('invalid') == True  # Allows custom categories
    
    @patch('fetchers.arxiv.requests.Session.get')
    def test_test_connection_success(self, mock_get, fetcher):
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<feed><entry></entry></feed>'
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        assert fetcher.test_connection() == True
    
    @patch('fetchers.arxiv.requests.Session.get')
    def test_test_connection_failure(self, mock_get, fetcher):
        # Mock failed response
        mock_get.side_effect = Exception("Connection failed")
        
        assert fetcher.test_connection() == False
    
    def test_build_query(self, fetcher):
        # Test with keywords and categories
        query = fetcher._build_query(['machine learning'], ['cs.AI'], 24)
        assert 'cat:cs.AI' in query
        assert 'machine learning' in query
        
        # Test with no parameters
        query = fetcher._build_query([], [], 24)
        assert 'cat:cs.AI' in query or 'cat:cs.LG' in query  # Should have fallback


class TestCrossrefFetcher:
    """Test CrossrefFetcher class"""
    
    @pytest.fixture
    def config(self):
        return {
            'ENABLE_CROSSREF': True,
            'RATE_LIMIT_CROSSREF': 50
        }
    
    @pytest.fixture
    def fetcher(self, config):
        return CrossrefFetcher(config)
    
    def test_initialization(self, fetcher):
        assert fetcher.name == 'crossref'
        assert fetcher.BASE_URL == "https://api.crossref.org/works"
    
    @patch('fetchers.crossref.requests.Session.get')
    def test_test_connection_success(self, mock_get, fetcher):
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {
                'items': []
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        assert fetcher.test_connection() == True
    
    @patch('fetchers.crossref.requests.Session.get')
    def test_test_connection_failure(self, mock_get, fetcher):
        # Mock failed response
        mock_get.side_effect = Exception("Connection failed")
        
        assert fetcher.test_connection() == False


class TestFetcherManager:
    """Test FetcherManager class"""
    
    @pytest.fixture
    def config(self):
        return {
            'ENABLE_ARXIV': True,
            'ENABLE_CROSSREF': True,
            'ENABLE_BIORXIV': False,
            'ENABLE_SEMANTIC_SCHOLAR': False,
            'RATE_LIMIT_ARXIV': 10,
            'RATE_LIMIT_CROSSREF': 50
        }
    
    @patch('fetchers.manager.create_arxiv_fetcher')
    @patch('fetchers.manager.create_crossref_fetcher')
    def test_initialization(self, mock_crossref, mock_arxiv, config):
        # Mock fetchers
        mock_arxiv_fetcher = Mock()
        mock_arxiv_fetcher.is_enabled.return_value = True
        mock_arxiv.return_value = mock_arxiv_fetcher
        
        mock_crossref_fetcher = Mock()
        mock_crossref_fetcher.is_enabled.return_value = True
        mock_crossref.return_value = mock_crossref_fetcher
        
        manager = FetcherManager(config)
        
        assert 'arxiv' in manager.fetchers
        assert 'crossref' in manager.fetchers
        assert len(manager.fetchers) == 2
    
    def test_get_enabled_fetchers(self, config):
        with patch('fetchers.manager.create_arxiv_fetcher') as mock_arxiv, \
             patch('fetchers.manager.create_crossref_fetcher') as mock_crossref:
            
            # Mock fetchers
            mock_arxiv_fetcher = Mock()
            mock_arxiv_fetcher.is_enabled.return_value = True
            mock_arxiv.return_value = mock_arxiv_fetcher
            
            mock_crossref_fetcher = Mock()
            mock_crossref_fetcher.is_enabled.return_value = True
            mock_crossref.return_value = mock_crossref_fetcher
            
            manager = FetcherManager(config)
            enabled = manager.get_enabled_fetchers()
            
            assert 'arxiv' in enabled
            assert 'crossref' in enabled


if __name__ == '__main__':
    pytest.main([__file__])