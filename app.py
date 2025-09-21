"""
Main application for LLM News Bot
"""
import argparse
import sys
import os
import time
import json
from datetime import datetime
from typing import List, Dict, Any
import pytz
from loguru import logger
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import get_config, is_dry_run, is_debug
from storage.db import init_database, get_database_stats, cleanup_database, db_manager, SeenPaperRepository
from storage.models import PaperCreate, SummaryResponse, SeenPaperCreate, Paper
from fetchers.manager import create_fetcher_manager
from pipeline.normalize import create_normalizer
from pipeline.filter_rank import create_filter_rank_pipeline
from pipeline.summarize import create_summarizer
from delivery.discord_post import create_discord_poster


class LLMNewsBot:
    """Main bot class that orchestrates the entire pipeline"""
    
    def __init__(self):
        self.config = get_config()
        self.setup_logging()
        
        # Initialize components
        self.fetcher_manager = None
        self.normalizer = None
        self.filter_rank_pipeline = None
        self.summarizer = None
        self.discord_poster = None
        
        # Initialize database
        init_database()
        
        logger.info("LLM News Bot initialized")
    
    def setup_logging(self):
        """Setup logging configuration"""
        
        # Remove default handler
        logger.remove()
        
        # Console handler
        log_level = self.config.get('LOG_LEVEL', 'INFO')
        if is_debug():
            log_level = 'DEBUG'
        
        logger.add(
            sys.stderr,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True
        )
        
        # File handler
        log_file = self.config.get('LOG_FILE', 'logs/llm_news.log')
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        logger.add(
            log_file,
            level='DEBUG',
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="1 day",
            retention="30 days",
            compression="zip"
        )
        
        logger.info(f"Logging configured: {log_level} level")
    
    def initialize_components(self):
        """Initialize all pipeline components"""
        try:
            config_dict = self.config.get_all()
            
            # Initialize components
            self.fetcher_manager = create_fetcher_manager(config_dict)
            self.normalizer = create_normalizer(config_dict)
            self.filter_rank_pipeline = create_filter_rank_pipeline(config_dict)
            self.summarizer = create_summarizer(config_dict)
            self.discord_poster = create_discord_poster(config_dict)
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
    
    def run_daily_pipeline(self) -> Dict[str, Any]:
        """Run the daily news pipeline"""
        
        start_time = time.time()
        logger.info("=== Starting daily pipeline ===")
        
        if not self.fetcher_manager:
            self.initialize_components()
        
        try:
            # Step 1: Fetch papers
            logger.info("Step 1: Fetching papers...")
            papers = self.fetch_papers()
            
            if not papers:
                logger.warning("No papers fetched, skipping pipeline")
                result = self.discord_poster.post_embeds([self.discord_poster.formatter.format_no_papers_embed()])
                return {
                    'success': True,
                    'papers_fetched': 0,
                    'papers_processed': 0,
                    'discord_result': result,
                    'runtime_seconds': time.time() - start_time
                }
            
            # Step 2: Normalize papers
            logger.info("Step 2: Normalizing papers...")
            pre_norm_news = sum(1 for p in papers if getattr(p, 'source', '') in {"tech_news", "nasa"})
            normalized_papers = self.normalizer.normalize_papers(papers)
            post_norm_news = sum(1 for p in normalized_papers if getattr(p, 'source', '') in {"tech_news", "nasa"})
            logger.info(f"News items (tech_news+nasa) before normalization: {pre_norm_news}, after normalization: {post_norm_news}")
            
            # Step 3: Filter and rank papers
            logger.info("Step 3: Filtering and ranking papers...")
            top_papers = self.filter_rank_pipeline.process_papers(normalized_papers)
            post_filter_news = sum(1 for p in top_papers if getattr(p, 'source', '') in {"tech_news", "nasa"})
            logger.info(f"News items after filtering/ranking: {post_filter_news}")
            
            if not top_papers:
                logger.warning("No papers passed filtering, posting empty message")
                result = self.discord_poster.post_embeds([self.discord_poster.formatter.format_no_papers_embed()])
                return {
                    'success': True,
                    'papers_fetched': len(papers),
                    'papers_processed': 0,
                    'discord_result': result,
                    'runtime_seconds': time.time() - start_time
                }
            
            # Step 4: Summarize papers
            logger.info("Step 4: Summarizing papers...")
            papers_with_summaries = []
            
            for paper in top_papers:
                try:
                    summary = self.summarizer.summarize(paper)
                    papers_with_summaries.append((paper, summary))
                except Exception as e:
                    logger.error(f"Failed to summarize paper {paper.title[:50]}: {e}")
                    continue
            
            if not papers_with_summaries:
                logger.error("Failed to summarize any papers")
                result = self.discord_poster.post_error("ไม่สามารถสรุปงานวิจัยได้")
                return {
                    'success': False,
                    'error': 'Summarization failed',
                    'papers_fetched': len(papers),
                    'papers_processed': 0,
                    'discord_result': result,
                    'runtime_seconds': time.time() - start_time
                }
            
            # Step 5: Store papers in database
            logger.info("Step 5: Storing papers in database...")
            self.store_papers(top_papers)
            
            # Step 6: Post to Discord
            logger.info("Step 6: Posting to Discord...")
            discord_result = self.discord_poster.post_papers(papers_with_summaries)
            
            runtime = time.time() - start_time
            
            if discord_result.get('success'):
                logger.info(f"Pipeline completed successfully in {runtime:.2f}s")
                return {
                    'success': True,
                    'papers_fetched': len(papers),
                    'papers_processed': len(papers_with_summaries),
                    'discord_result': discord_result,
                    'runtime_seconds': runtime
                }
            else:
                logger.error(f"Discord posting failed: {discord_result.get('error')}")
                return {
                    'success': False,
                    'error': discord_result.get('error'),
                    'papers_fetched': len(papers),
                    'papers_processed': len(papers_with_summaries),
                    'discord_result': discord_result,
                    'runtime_seconds': runtime
                }
            
        except Exception as e:
            runtime = time.time() - start_time
            logger.error(f"Pipeline failed after {runtime:.2f}s: {e}")
            
            # Try to post error to Discord
            try:
                error_result = self.discord_poster.post_error(str(e))
            except Exception as discord_error:
                logger.error(f"Failed to post error to Discord: {discord_error}")
                error_result = {'success': False, 'error': str(discord_error)}
            
            return {
                'success': False,
                'error': str(e),
                'papers_fetched': 0,
                'papers_processed': 0,
                'discord_result': error_result,
                'runtime_seconds': runtime
            }
    
    def fetch_papers(self) -> List:
        """Fetch papers from all enabled sources"""
        
        keywords = self.config.get_keywords_include()
        categories = self.config.get_arxiv_categories()
        max_per_source = self.config.get('MAX_PAPERS_PER_DAY', 5) * 2  # Fetch more than we need
        
        logger.info(f"Fetching papers with keywords: {keywords}")
        logger.info(f"Target categories: {categories}")
        
        papers = self.fetcher_manager.fetch_all_papers(
            keywords=keywords,
            categories=categories,
            hours_back=24,
            max_results_per_source=max_per_source
        )
        
        logger.info(f"Fetched {len(papers)} papers total")
        return papers
    
    def store_papers(self, papers: List[PaperCreate]):
        """Store papers in database with deduplication"""
        
        db = db_manager.get_session()
        try:
            stored_count = 0
            
            for paper_data in papers:
                # Check if already seen
                identifier = paper_data.doi or paper_data.arxiv_id or f"hash_{hash(paper_data.title)}"
                if SeenPaperRepository.is_paper_seen(db, identifier):
                    logger.debug(f"Paper already seen: {paper_data.title[:50]}")
                    continue

                # Persist Paper row first (minimal fields)
                paper_row = Paper(
                    source=paper_data.source,
                    doi=paper_data.doi,
                    arxiv_id=paper_data.arxiv_id,
                    title=paper_data.title,
                    authors=json.dumps(paper_data.authors),
                    abstract=paper_data.abstract,
                    url=paper_data.url,
                    published_at=paper_data.published_at,
                    tags=json.dumps(paper_data.tags) if paper_data.tags else None,
                    categories=json.dumps(paper_data.categories) if paper_data.categories else None
                )
                db.add(paper_row)
                db.flush()  # get paper_row.id

                # Mark as seen
                seen_data = SeenPaperCreate(
                    identifier=identifier,
                    identifier_type='doi' if paper_data.doi else ('arxiv_id' if paper_data.arxiv_id else 'hash'),
                    source=paper_data.source,
                    paper_id=paper_row.id
                )
                SeenPaperRepository.mark_as_seen(db, seen_data)

                stored_count += 1

            db.commit()
            
            logger.info(f"Stored {stored_count} new papers")
            
        except Exception as e:
            logger.error(f"Error storing papers: {e}")
        finally:
            db.close()
    
    def test_all_connections(self) -> Dict[str, bool]:
        """Test all external connections"""
        
        if not self.fetcher_manager:
            self.initialize_components()
        
        results = {}
        
        # Test fetchers
        logger.info("Testing fetcher connections...")
        fetcher_results = self.fetcher_manager.test_all_connections()
        results.update(fetcher_results)
        
        # Test Discord
        logger.info("Testing Discord connection...")
        discord_ok = self.discord_poster.test_connection()
        results['discord'] = discord_ok
        
        # Test database
        logger.info("Testing database connection...")
        try:
            stats = get_database_stats()
            results['database'] = True
            logger.info(f"Database OK - {stats['total_papers']} papers stored")
        except Exception as e:
            logger.error(f"Database test failed: {e}")
            results['database'] = False
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """Get system status"""
        
        status = {
            'timestamp': datetime.utcnow().isoformat(),
            'config': {
                'dry_run': is_dry_run(),
                'debug': is_debug(),
                'enabled_sources': self.config.get_enabled_sources(),
                'summarizer_mode': self.config.get('SUMMARIZER_MODE'),
                'max_papers': self.config.get('MAX_PAPERS_PER_DAY'),
                'post_time': self.config.get('POST_TIME'),
                'timezone': self.config.get('TIMEZONE')
            }
        }
        
        # Add database stats
        try:
            status['database'] = get_database_stats()
        except Exception as e:
            status['database'] = {'error': str(e)}
        
        # Add connection tests
        try:
            status['connections'] = self.test_all_connections()
        except Exception as e:
            status['connections'] = {'error': str(e)}
        
        return status


def run_scheduler():
    """Run the scheduled version of the bot"""
    
    bot = LLMNewsBot()
    config = get_config()
    
    # Setup scheduler
    scheduler = BlockingScheduler(timezone=pytz.timezone(config.get('TIMEZONE')))
    
    # Get schedule time
    hour, minute = config.get_post_time_parts()
    
    # Add job
    scheduler.add_job(
        func=bot.run_daily_pipeline,
        trigger=CronTrigger(hour=hour, minute=minute),
        id='daily_news',
        name='Daily News Pipeline',
        max_instances=1,
        replace_existing=True
    )
    
    logger.info(f"Scheduler started - will run daily at {hour:02d}:{minute:02d} {config.get('TIMEZONE')}")
    logger.info("Press Ctrl+C to stop")
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        scheduler.shutdown()


def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(description='LLM News Bot')
    parser.add_argument('--run-once', action='store_true', help='Run pipeline once and exit')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode (no actual posting)')
    parser.add_argument('--test-connections', action='store_true', help='Test all connections')
    parser.add_argument('--test-discord', action='store_true', help='Test Discord connection only')
    parser.add_argument('--test-fetcher', help='Test specific fetcher (arxiv, crossref)')
    parser.add_argument('--status', action='store_true', help='Show system status')
    parser.add_argument('--logs', action='store_true', help='Show recent logs')
    parser.add_argument('--cleanup-db', type=int, metavar='DAYS', help='Clean up database records older than N days')
    parser.add_argument('--init-db', action='store_true', help='Initialize database tables')
    
    args = parser.parse_args()
    
    # Handle special commands first
    if args.init_db:
        print("Initializing database...")
        init_database()
        print("Database initialized successfully")
        return
    
    if args.cleanup_db:
        print(f"Cleaning up database records older than {args.cleanup_db} days...")
        cleanup_database(days=args.cleanup_db)
        print("Database cleanup completed")
        return
    
    if args.logs:
        log_file = get_config().get('LOG_FILE', 'logs/llm_news.log')
        if os.path.exists(log_file):
            print(f"Recent logs from {log_file}:")
            print("-" * 50)
            # Show last 50 lines
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines[-50:]:
                    print(line.rstrip())
        else:
            print(f"Log file not found: {log_file}")
        return
    
    # Create bot instance
    try:
        bot = LLMNewsBot()
        
        # Override config for dry-run
        if args.dry_run:
            bot.config.update('DRY_RUN', True)
            logger.info("Dry-run mode enabled")
        
    except Exception as e:
        print(f"Failed to initialize bot: {e}")
        sys.exit(1)
    
    # Handle commands
    try:
        if args.status:
            status = bot.get_status()
            print("=== System Status ===")
            for key, value in status.items():
                print(f"{key}: {value}")
        
        elif args.test_connections:
            print("Testing all connections...")
            results = bot.test_all_connections()
            print("Connection test results:")
            for service, ok in results.items():
                status = "✓" if ok else "✗"
                print(f"  {status} {service}")
        
        elif args.test_discord:
            print("Testing Discord connection...")
            bot.initialize_components()
            ok = bot.discord_poster.test_connection()
            if ok:
                print("✓ Discord connection successful")
                # Send test message
                result = bot.discord_poster.post_test_message()
                if result.get('success'):
                    print("✓ Test message sent successfully")
                else:
                    print(f"✗ Test message failed: {result.get('error')}")
            else:
                print("✗ Discord connection failed")
        
        elif args.test_fetcher:
            print(f"Testing {args.test_fetcher} fetcher...")
            bot.initialize_components()
            fetcher = bot.fetcher_manager.get_fetcher(args.test_fetcher)
            if fetcher:
                ok = fetcher.test_connection()
                print(f"{'✓' if ok else '✗'} {args.test_fetcher} connection")
                
                if ok:
                    # Try a small fetch
                    print("Attempting small fetch...")
                    papers = fetcher.fetch_papers(['AI'], max_results=3)
                    print(f"Fetched {len(papers)} papers")
                    for i, paper in enumerate(papers[:3], 1):
                        print(f"  {i}. {paper.title[:60]}...")
            else:
                print(f"Fetcher '{args.test_fetcher}' not found")
        
        elif args.run_once:
            print("Running pipeline once...")
            result = bot.run_daily_pipeline()
            
            print("Pipeline completed:")
            print(f"  Success: {result['success']}")
            print(f"  Papers fetched: {result['papers_fetched']}")
            print(f"  Papers processed: {result['papers_processed']}")
            print(f"  Runtime: {result['runtime_seconds']:.2f}s")
            
            if not result['success']:
                print(f"  Error: {result.get('error')}")
                sys.exit(1)
        
        else:
            # Run scheduler
            print("Starting scheduler...")
            bot.config.print_config_summary()
            run_scheduler()
    
    except KeyboardInterrupt:
        print("\\nInterrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()