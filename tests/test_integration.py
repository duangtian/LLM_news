"""
Integration tests for the full pipeline
"""
import pytest
from unittest.mock import Mock, patch
import tempfile
import os

from app import LLMNewsBot
from config import Config
from storage.db import init_database


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Set environment variable for test database
    os.environ['DATABASE_URL'] = f'sqlite:///{path}'
    
    # Initialize database
    init_database()
    
    yield path
    
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def test_config():
    """Create test configuration"""
    return {
        'ENABLE_ARXIV': True,
        'ENABLE_CROSSREF': False,
        'ENABLE_BIORXIV': False,
        'ENABLE_SEMANTIC_SCHOLAR': False,
        'KEYWORDS_INCLUDE': 'machine learning,AI',
        'KEYWORDS_EXCLUDE': 'spam',
        'MAX_PAPERS_PER_DAY': 2,
        'SUMMARIZER_MODE': 'rule_based',
        'SUMMARY_MIN_LENGTH': 50,
        'SUMMARY_MAX_LENGTH': 200,
        'DRY_RUN': True,
        'DEBUG': True,
        'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/test',
        'POST_TIME': '20:00',
        'TIMEZONE': 'Asia/Bangkok'
    }


class TestLLMNewsBotIntegration:
    """Integration tests for LLMNewsBot"""
    
    @patch('config.Config')
    def test_bot_initialization(self, mock_config_class, test_config, temp_db):
        """Test bot initialization"""
        # Mock config
        mock_config = Mock()
        mock_config.get_all.return_value = test_config
        mock_config.get.side_effect = lambda key, default=None: test_config.get(key, default)
        mock_config.get_keywords_include.return_value = ['machine learning', 'AI']
        mock_config.get_arxiv_categories.return_value = ['cs.AI', 'cs.LG']
        mock_config_class.return_value = mock_config
        
        with patch('app.get_config', return_value=mock_config):
            bot = LLMNewsBot()
            assert bot.config == mock_config
    
    @patch('fetchers.arxiv.ArxivFetcher.fetch_papers')
    @patch('fetchers.arxiv.ArxivFetcher.test_connection')
    @patch('delivery.discord_post.DiscordWebhookPoster.post_embeds')
    def test_run_daily_pipeline_success(self, mock_discord_post, mock_test_connection, 
                                       mock_fetch_papers, test_config, temp_db):
        """Test successful pipeline run"""
        
        # Mock fetcher responses
        mock_test_connection.return_value = True
        mock_fetch_papers.return_value = [
            # Mock paper data would go here
        ]
        
        # Mock Discord response
        mock_discord_post.return_value = {
            'success': True,
            'message_ids': ['123456'],
            'embed_count': 1
        }
        
        with patch('config.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_all.return_value = test_config
            mock_config.get.side_effect = lambda key, default=None: test_config.get(key, default)
            mock_config.get_keywords_include.return_value = ['machine learning', 'AI']
            mock_config.get_arxiv_categories.return_value = ['cs.AI', 'cs.LG']
            mock_get_config.return_value = mock_config
            
            bot = LLMNewsBot()
            bot.initialize_components()
            
            # Run pipeline
            result = bot.run_daily_pipeline()
            
            assert result['success'] == True
            assert 'runtime_seconds' in result
    
    @patch('fetchers.manager.FetcherManager.fetch_all_papers')
    @patch('delivery.discord_post.DiscordPoster.post_error')
    def test_run_daily_pipeline_failure(self, mock_post_error, mock_fetch_papers, 
                                       test_config, temp_db):
        """Test pipeline failure handling"""
        
        # Mock fetcher failure
        mock_fetch_papers.side_effect = Exception("Fetcher failed")
        
        # Mock error posting
        mock_post_error.return_value = {
            'success': True,
            'message_id': '123456'
        }
        
        with patch('config.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_all.return_value = test_config
            mock_config.get.side_effect = lambda key, default=None: test_config.get(key, default)
            mock_config.get_keywords_include.return_value = ['machine learning', 'AI']
            mock_config.get_arxiv_categories.return_value = ['cs.AI', 'cs.LG']
            mock_get_config.return_value = mock_config
            
            bot = LLMNewsBot()
            bot.initialize_components()
            
            # Run pipeline
            result = bot.run_daily_pipeline()
            
            assert result['success'] == False
            assert 'error' in result
            assert 'runtime_seconds' in result
    
    def test_test_all_connections(self, test_config, temp_db):
        """Test connection testing"""
        
        with patch('config.get_config') as mock_get_config, \
             patch('fetchers.manager.FetcherManager.test_all_connections') as mock_test_fetchers, \
             patch('delivery.discord_post.DiscordPoster.test_connection') as mock_test_discord:
            
            mock_config = Mock()
            mock_config.get_all.return_value = test_config
            mock_config.get.side_effect = lambda key, default=None: test_config.get(key, default)
            mock_get_config.return_value = mock_config
            
            # Mock connection results
            mock_test_fetchers.return_value = {'arxiv': True}
            mock_test_discord.return_value = True
            
            bot = LLMNewsBot()
            bot.initialize_components()
            
            results = bot.test_all_connections()
            
            assert 'arxiv' in results
            assert 'discord' in results
            assert 'database' in results
    
    def test_get_status(self, test_config, temp_db):
        """Test status reporting"""
        
        with patch('config.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_all.return_value = test_config
            mock_config.get.side_effect = lambda key, default=None: test_config.get(key, default)
            mock_config.get_enabled_sources.return_value = ['arxiv']
            mock_get_config.return_value = mock_config
            
            bot = LLMNewsBot()
            
            status = bot.get_status()
            
            assert 'timestamp' in status
            assert 'config' in status
            assert 'database' in status
            assert status['config']['enabled_sources'] == ['arxiv']


class TestConfigIntegration:
    """Integration tests for configuration"""
    
    def test_config_validation_success(self):
        """Test successful config validation"""
        
        # Set valid environment variables
        os.environ.update({
            'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/test',
            'ENABLE_ARXIV': 'true',
            'POST_TIME': '20:00',
            'MAX_PAPERS_PER_DAY': '5'
        })
        
        try:
            config = Config()
            assert config.get('DISCORD_WEBHOOK_URL') == 'https://discord.com/api/webhooks/test'
            assert config.get('ENABLE_ARXIV') == True
            assert config.get('MAX_PAPERS_PER_DAY') == 5
        finally:
            # Cleanup environment
            for key in ['DISCORD_WEBHOOK_URL', 'ENABLE_ARXIV', 'POST_TIME', 'MAX_PAPERS_PER_DAY']:
                os.environ.pop(key, None)
    
    def test_config_validation_failure(self):
        """Test config validation failure"""
        
        # Set invalid environment variables
        os.environ.update({
            'POST_TIME': 'invalid_time',
            'MAX_PAPERS_PER_DAY': '0'
        })
        
        try:
            with pytest.raises(ValueError):
                Config()
        finally:
            # Cleanup environment
            for key in ['POST_TIME', 'MAX_PAPERS_PER_DAY']:
                os.environ.pop(key, None)


class TestDatabaseIntegration:
    """Integration tests for database operations"""
    
    def test_database_initialization(self, temp_db):
        """Test database initialization"""
        # Database should be initialized by fixture
        assert os.path.exists(temp_db)
    
    def test_database_stats(self, temp_db):
        """Test database statistics"""
        from storage.db import get_database_stats
        
        stats = get_database_stats()
        
        assert 'total_papers' in stats
        assert 'papers_today' in stats
        assert 'total_posts' in stats
        assert isinstance(stats['total_papers'], int)


if __name__ == '__main__':
    pytest.main([__file__])