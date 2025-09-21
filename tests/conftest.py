"""
Test configuration for pytest
"""
import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Test configuration
import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment"""
    # Set test environment variables
    os.environ.update({
        'DEBUG': 'true',
        'DRY_RUN': 'true',
        'LOG_LEVEL': 'DEBUG'
    })
    
    yield
    
    # Cleanup after tests
    test_env_vars = ['DEBUG', 'DRY_RUN', 'LOG_LEVEL']
    for var in test_env_vars:
        os.environ.pop(var, None)


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    return {
        'ENABLE_ARXIV': True,
        'ENABLE_CROSSREF': True,
        'ENABLE_BIORXIV': False,
        'ENABLE_SEMANTIC_SCHOLAR': False,
        'KEYWORDS_INCLUDE': 'machine learning,AI,deep learning',
        'KEYWORDS_EXCLUDE': 'spam,advertisement',
        'MAX_PAPERS_PER_DAY': 5,
        'SUMMARIZER_MODE': 'rule_based',
        'SUMMARY_MIN_LENGTH': 150,
        'SUMMARY_MAX_LENGTH': 250,
        'TLDR_MAX_LENGTH': 2,
        'DRY_RUN': True,
        'DEBUG': True,
        'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/test',
        'POST_TIME': '20:00',
        'TIMEZONE': 'Asia/Bangkok',
        'RATE_LIMIT_ARXIV': 10,
        'RATE_LIMIT_CROSSREF': 50
    }