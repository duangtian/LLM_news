"""
Configuration management for LLM News Bot
"""
import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration manager for the application"""
    
    def __init__(self):
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables"""
        
        config = {
            # === Discord Configuration ===
            'DISCORD_BOT_TOKEN': os.getenv('DISCORD_BOT_TOKEN'),
            'DISCORD_WEBHOOK_URL': os.getenv('DISCORD_WEBHOOK_URL'),
            'DISCORD_CHANNEL_ID': os.getenv('DISCORD_CHANNEL_ID'),
            
            # === Data Sources Configuration ===
            'ENABLE_ARXIV': self._get_bool('ENABLE_ARXIV', True),
            'ENABLE_CROSSREF': self._get_bool('ENABLE_CROSSREF', True),
            'ENABLE_BIORXIV': self._get_bool('ENABLE_BIORXIV', False),
            'ENABLE_SEMANTIC_SCHOLAR': self._get_bool('ENABLE_SEMANTIC_SCHOLAR', False),
            'ENABLE_GOOGLE_SCHOLAR': self._get_bool('ENABLE_GOOGLE_SCHOLAR', False),
            'ENABLE_NASA': self._get_bool('ENABLE_NASA', False),
            'ENABLE_TECH_NEWS': self._get_bool('ENABLE_TECH_NEWS', False),
            
            # API Keys
            'SEMANTIC_SCHOLAR_API_KEY': os.getenv('SEMANTIC_SCHOLAR_API_KEY'),
            'NASA_API_KEY': os.getenv('NASA_API_KEY', 'DEMO_KEY'),
            
            # === Google Scholar Configuration ===
            'RATE_LIMIT_GOOGLE_SCHOLAR': self._get_int('RATE_LIMIT_GOOGLE_SCHOLAR', 5),
            'MAX_PAPERS_GOOGLE_SCHOLAR': self._get_int('MAX_PAPERS_GOOGLE_SCHOLAR', 20),
            'GOOGLE_SCHOLAR_DAYS_BACK': self._get_int('GOOGLE_SCHOLAR_DAYS_BACK', 7),
            'GOOGLE_SCHOLAR_USE_PROXY': self._get_bool('GOOGLE_SCHOLAR_USE_PROXY', False),
            
            # === NASA Configuration ===
            'RATE_LIMIT_NASA': self._get_int('RATE_LIMIT_NASA', 10),
            'MAX_PAPERS_NASA': self._get_int('MAX_PAPERS_NASA', 30),
            'NASA_DAYS_BACK': self._get_int('NASA_DAYS_BACK', 7),
            
            # === Tech News Configuration ===
            'RATE_LIMIT_TECH_NEWS': self._get_int('RATE_LIMIT_TECH_NEWS', 15),
            'MAX_PAPERS_TECH_NEWS': self._get_int('MAX_PAPERS_TECH_NEWS', 25),
            'TECH_NEWS_DAYS_BACK': self._get_int('TECH_NEWS_DAYS_BACK', 3),
            
            # === Content Filtering ===
            'KEYWORDS_INCLUDE': os.getenv('KEYWORDS_INCLUDE', 'LLM,diffusion,machine learning,AI,deep learning,neural network'),
            'KEYWORDS_EXCLUDE': os.getenv('KEYWORDS_EXCLUDE', 'survey,review only,obsolete'),
            'ARXIV_CATEGORIES': os.getenv('ARXIV_CATEGORIES', 'cs.AI,cs.CL,cs.LG,cs.CV,stat.ML'),
            
            # === Summarization Configuration ===
            'SUMMARIZER_MODE': os.getenv('SUMMARIZER_MODE', 'rule_based'),
            'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
            'OPENAI_MODEL': os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
            'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
            'ANTHROPIC_MODEL': os.getenv('ANTHROPIC_MODEL', 'claude-3-haiku-20240307'),
            
            # === Scheduling ===
            'POST_TIME': os.getenv('POST_TIME', '20:00'),
            'TIMEZONE': os.getenv('TIMEZONE', 'Asia/Bangkok'),
            
            # === Limits ===
            'MAX_PAPERS_PER_DAY': self._get_int('MAX_PAPERS_PER_DAY', 5),
            'RATE_LIMIT_ARXIV': self._get_int('RATE_LIMIT_ARXIV', 10),
            'RATE_LIMIT_CROSSREF': self._get_int('RATE_LIMIT_CROSSREF', 50),
            
            # === Database ===
            'DATABASE_URL': os.getenv('DATABASE_URL', 'sqlite:///llm_news.db'),
            
            # === Logging ===
            'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO'),
            'LOG_FILE': os.getenv('LOG_FILE', 'logs/llm_news.log'),
            
            # === Content Guidelines ===
            'SUMMARY_MIN_LENGTH': self._get_int('SUMMARY_MIN_LENGTH', 150),
            'SUMMARY_MAX_LENGTH': self._get_int('SUMMARY_MAX_LENGTH', 250),
            'TLDR_MAX_LENGTH': self._get_int('TLDR_MAX_LENGTH', 2),
            
            # === Error Handling ===
            'MAX_RETRIES': self._get_int('MAX_RETRIES', 3),
            'RETRY_DELAYS': os.getenv('RETRY_DELAYS', '60,300,900'),
            
            # === Development ===
            'DRY_RUN': self._get_bool('DRY_RUN', False),
            'DEBUG': self._get_bool('DEBUG', False),
        }
        
        return config
    
    def _get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean value from environment"""
        value = os.getenv(key)
        if value is None:
            return default
        return str(value).lower() in ('true', '1', 'yes', 'on')
    
    def _get_int(self, key: str, default: int = 0) -> int:
        """Get integer value from environment"""
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            logger.warning(f"Invalid integer value for {key}, using default {default}")
            return default
    
    def _get_float(self, key: str, default: float = 0.0) -> float:
        """Get float value from environment"""
        try:
            return float(os.getenv(key, str(default)))
        except ValueError:
            logger.warning(f"Invalid float value for {key}, using default {default}")
            return default
    
    def _get_list(self, key: str, default: List[str] = None) -> List[str]:
        """Get list value from environment (comma-separated)"""
        if default is None:
            default = []
        
        value = os.getenv(key, ','.join(default))
        if not value:
            return default
        
        return [item.strip() for item in value.split(',') if item.strip()]
    
    def _validate_config(self):
        """Validate configuration values"""
        errors = []
        
        # Check Discord configuration
        if not self.config['DISCORD_WEBHOOK_URL'] and not self.config['DISCORD_BOT_TOKEN']:
            errors.append("Either DISCORD_WEBHOOK_URL or DISCORD_BOT_TOKEN must be provided")
        
        if self.config['DISCORD_BOT_TOKEN'] and not self.config['DISCORD_CHANNEL_ID']:
            errors.append("DISCORD_CHANNEL_ID is required when using DISCORD_BOT_TOKEN")
        
        # Check data sources
        enabled_sources = [
            self.config['ENABLE_ARXIV'],
            self.config['ENABLE_CROSSREF'],
            self.config['ENABLE_BIORXIV'],
            self.config['ENABLE_SEMANTIC_SCHOLAR'],
            self.config['ENABLE_GOOGLE_SCHOLAR'],
            self.config['ENABLE_NASA'],
            self.config['ENABLE_TECH_NEWS']
        ]
        
        if not any(enabled_sources):
            errors.append("At least one data source must be enabled")
        
        # Check summarizer configuration
        summarizer_mode = self.config['SUMMARIZER_MODE'].lower()
        if summarizer_mode == 'openai' and not self.config['OPENAI_API_KEY']:
            errors.append("OPENAI_API_KEY is required when SUMMARIZER_MODE is 'openai'")
        
        if summarizer_mode == 'anthropic' and not self.config['ANTHROPIC_API_KEY']:
            errors.append("ANTHROPIC_API_KEY is required when SUMMARIZER_MODE is 'anthropic'")
        
        # Check time format
        try:
            time_parts = self.config['POST_TIME'].split(':')
            if len(time_parts) != 2:
                raise ValueError("Invalid time format")
            hour, minute = int(time_parts[0]), int(time_parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Invalid time range")
        except ValueError:
            errors.append(f"Invalid POST_TIME format: {self.config['POST_TIME']} (should be HH:MM)")
        
        # Check limits
        if self.config['MAX_PAPERS_PER_DAY'] <= 0:
            errors.append("MAX_PAPERS_PER_DAY must be positive")
        
        if self.config['SUMMARY_MIN_LENGTH'] >= self.config['SUMMARY_MAX_LENGTH']:
            errors.append("SUMMARY_MIN_LENGTH must be less than SUMMARY_MAX_LENGTH")
        
        if errors:
            error_msg = "Configuration validation failed:\\n" + "\\n".join(f"- {error}" for error in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info("Configuration validation passed")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values"""
        return self.config.copy()
    
    def get_keywords_include(self) -> List[str]:
        """Get include keywords as list"""
        return self._get_list('KEYWORDS_INCLUDE')
    
    def get_keywords_exclude(self) -> List[str]:
        """Get exclude keywords as list"""
        return self._get_list('KEYWORDS_EXCLUDE')
    
    def get_arxiv_categories(self) -> List[str]:
        """Get arXiv categories as list"""
        return self._get_list('ARXIV_CATEGORIES')
    
    def get_retry_delays(self) -> List[int]:
        """Get retry delays as list of integers"""
        delays_str = self.config['RETRY_DELAYS']
        try:
            return [int(delay.strip()) for delay in delays_str.split(',')]
        except ValueError:
            logger.warning("Invalid RETRY_DELAYS format, using defaults")
            return [60, 300, 900]
    
    def get_post_time_parts(self) -> tuple[int, int]:
        """Get post time as (hour, minute) tuple"""
        hour, minute = self.config['POST_TIME'].split(':')
        return int(hour), int(minute)
    
    def is_dry_run(self) -> bool:
        """Check if running in dry run mode"""
        return self.config['DRY_RUN']
    
    def is_debug(self) -> bool:
        """Check if debug mode is enabled"""
        return self.config['DEBUG']
    
    def get_enabled_sources(self) -> List[str]:
        """Get list of enabled data sources"""
        sources = []
        
        if self.config['ENABLE_ARXIV']:
            sources.append('arxiv')
        if self.config['ENABLE_CROSSREF']:
            sources.append('crossref')
        if self.config['ENABLE_BIORXIV']:
            sources.append('biorxiv')
        if self.config['ENABLE_SEMANTIC_SCHOLAR']:
            sources.append('semantic_scholar')
        if self.config['ENABLE_GOOGLE_SCHOLAR']:
            sources.append('google_scholar')
        if self.config['ENABLE_NASA']:
            sources.append('nasa')
        if self.config['ENABLE_TECH_NEWS']:
            sources.append('tech_news')
        
        return sources
    
    def update(self, key: str, value: Any):
        """Update configuration value (runtime only, not persistent)"""
        self.config[key] = value
        logger.debug(f"Updated config {key} = {value}")
    
    def print_config_summary(self):
        """Print configuration summary for debugging"""
        logger.info("=== Configuration Summary ===")
        
        # Discord
        discord_method = "Webhook" if self.config['DISCORD_WEBHOOK_URL'] else "Bot"
        logger.info(f"Discord: {discord_method}")
        
        # Data sources
        enabled_sources = self.get_enabled_sources()
        logger.info(f"Data Sources: {', '.join(enabled_sources)}")
        
        # Summarizer
        logger.info(f"Summarizer: {self.config['SUMMARIZER_MODE']}")
        
        # Scheduling
        logger.info(f"Schedule: {self.config['POST_TIME']} {self.config['TIMEZONE']}")
        
        # Limits
        logger.info(f"Max Papers: {self.config['MAX_PAPERS_PER_DAY']}")
        
        # Mode
        mode = []
        if self.config['DRY_RUN']:
            mode.append("DRY_RUN")
        if self.config['DEBUG']:
            mode.append("DEBUG")
        if mode:
            logger.info(f"Mode: {', '.join(mode)}")
        
        logger.info("=== End Configuration ===")


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get global configuration instance"""
    return config


def reload_config():
    """Reload configuration from environment"""
    global config
    load_dotenv(override=True)  # Reload .env file
    config = Config()
    logger.info("Configuration reloaded")


# Convenience functions
def get(key: str, default: Any = None) -> Any:
    """Get configuration value (convenience function)"""
    return config.get(key, default)


def is_dry_run() -> bool:
    """Check if in dry run mode (convenience function)"""
    return config.is_dry_run()


def is_debug() -> bool:
    """Check if in debug mode (convenience function)"""
    return config.is_debug()


def get_enabled_sources() -> List[str]:
    """Get enabled sources (convenience function)"""
    return config.get_enabled_sources()


if __name__ == "__main__":
    # Print configuration when run directly
    config.print_config_summary()