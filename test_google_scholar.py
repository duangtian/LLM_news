#!/usr/bin/env python3
"""
Simple test script for Google Scholar fetcher
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetchers.google_scholar import GoogleScholarFetcher
from config import Config

def test_google_scholar():
    """Test Google Scholar fetcher with basic configuration"""
    
    print("🔍 Testing Google Scholar Fetcher...")
    
    try:
        # Create config
        config = Config()
        config_dict = config.get_all()
        
        # Override some settings for testing
        config_dict.update({
            'ENABLE_GOOGLE_SCHOLAR': True,
            'MAX_PAPERS_GOOGLE_SCHOLAR': 3,  # Small number for testing
            'RATE_LIMIT_GOOGLE_SCHOLAR': 3,  # Slower for safety
            'GOOGLE_SCHOLAR_USE_PROXY': False
        })
        
        print(f"📋 Configuration:")
        print(f"  - Max papers: {config_dict['MAX_PAPERS_GOOGLE_SCHOLAR']}")
        print(f"  - Rate limit: {config_dict['RATE_LIMIT_GOOGLE_SCHOLAR']}/s")
        print(f"  - Use proxy: {config_dict['GOOGLE_SCHOLAR_USE_PROXY']}")
        
        # Create fetcher
        fetcher = GoogleScholarFetcher(config_dict)
        
        # Test connection first
        print(f"\n🔗 Testing connection...")
        if fetcher.test_connection():
            print("✅ Connection successful!")
        else:
            print("❌ Connection failed!")
            return False
        
        # Test paper fetching
        print(f"\n📚 Fetching papers...")
        keywords = ['machine learning', 'deep learning']
        papers = fetcher.fetch_papers(keywords)
        
        print(f"📊 Results:")
        print(f"  - Keywords used: {keywords}")
        print(f"  - Papers found: {len(papers)}")
        
        # Show sample papers
        for i, paper in enumerate(papers[:2]):  # Show first 2
            print(f"\n📄 Paper {i+1}:")
            print(f"  Title: {paper.title[:60]}...")
            print(f"  Authors: {', '.join(paper.authors[:3])}")
            print(f"  Source: {paper.source}")
            print(f"  Keywords: {paper.keywords}")
        
        if papers:
            print("✅ Google Scholar fetcher working correctly!")
            return True
        else:
            print("⚠️  No papers found (might be normal)")
            return True
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure to install: pip install scholarly>=1.7.0")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_google_scholar()
    sys.exit(0 if success else 1)