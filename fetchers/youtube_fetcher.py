"""
YouTube video fetcher for LLM, AI, Space, and Tech content.
Uses YouTube RSS feeds (no API key needed) and optionally YouTube Data API v3.
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

from .base import BaseFetcher, PaperMetadata


# Curated YouTube channels: (channel_id, display_name, category)
YOUTUBE_CHANNELS = [
    # === LLM / Transformer / AI Research ===
    ("UCbmNph6atAoGfqLoCL_duAg", "Andrej Karpathy", "LLM"),
    ("UCWN3xxRkmTPmbKwht9FuE5A", "Siraj Raval", "AI"),
    ("UCZHmQk67mSJgfCCTn7xBfew", "Two Minute Papers", "AI Research"),
    ("UCVls1GmFKf6WlTraIb_IaJg", "Computerphile", "CS Education"),
    ("UC0RhatS1pyxInC00YKjjBqQ", "Marques Brownlee (MKBHD)", "Tech"),
    ("UCnUYZLuoy1rq1aVMwx4aTzw", "Grant Sanderson (3Blue1Brown)", "Math/AI"),
    ("UC4JX40jDee_tINbkjycV4Sg", "TED-Ed", "Education"),
    ("UCsooa4yRKGN_zEE8iknghZA", "TED Talks Technology", "Tech"),
    ("UCbfYPyITQ-7l4upoX8nvctg", "Two Minute Papers", "AI Research"),
    # === Space / NASA ===
    ("UCLA_DiR1FfKNvjuUpBHmylQ", "NASA", "Space"),
    ("UCVTomc35agH1SM6kCKzwW_g", "SpaceX", "Space"),
    ("UC6uKrU_WqJ1R2HMTY3LIx5Q", "Everyday Astronaut", "Space"),
    ("UCryGec9PdXoeJqGjdMe-cpg", "Scott Manley", "Space"),
    # === IT / Tech News ===
    ("UCXuqSBlHAE6Xw-yeJA0Tunw", "Linus Tech Tips", "Tech Hardware"),
    ("UCVjgXoeebW1HqzxYkMTiWsA", "Fireship", "Programming"),
    ("UCO1cgjhGzsSYb1rsB4bFe4Q", "Numberphile", "Math"),
    # === Academic / University Lectures ===
    ("UCYO_jab_esuFRV4b17AJtAw", "3Blue1Brown", "Math/ML"),
    ("UC12LqyqTQTEVFROwZ5_FbmQ", "MIT OpenCourseWare", "Academic"),
    ("UCBcRF18a7Qf58cCRy5xuWwQ", "MIT 6.S191", "Deep Learning"),
    ("UCPk8m_r6fkUSI9/dFnbg8Gg", "Stanford Online", "Academic"),
    ("UC9-y-6csu5WGm29I7JiwpnA", "Computerphile", "CS Education"),
]

# Focused search: only pull from channels with relevant tags
LLM_FOCUS_CHANNEL_IDS = {c[0] for c in YOUTUBE_CHANNELS}

# Additional: YouTube search RSS (no API key needed) for keyword-based discovery
YOUTUBE_SEARCH_TERMS = [
    "large language model 2025 2026",
    "transformer AI research",
    "LLM tutorial lecture",
    "GPT Claude Gemini new",
    "deep learning lecture university",
    "space launch 2025 2026",
    "NASA SpaceX new",
    "IT technology news 2026",
]


class YouTubeFetcher(BaseFetcher):
    """Fetches YouTube videos relevant to LLM, AI, Space, IT, and academic content."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.source_name = "youtube"
        self.api_key = config.get("YOUTUBE_API_KEY", "")
        self.max_results = config.get("MAX_PAPERS_YOUTUBE", 15)
        self.days_back = config.get("YOUTUBE_DAYS_BACK", 7)

        # RSS base (no API key needed)
        self.rss_base = "https://www.youtube.com/feeds/videos.xml?channel_id="

        logger.debug(f"YouTube fetcher initialized (api_key={'set' if self.api_key else 'not set'})")

    def is_enabled(self) -> bool:
        return self.config.get("ENABLE_YOUTUBE", False)

    def fetch_papers(self, keywords: List[str], categories: List[str] = None,
                     hours_back: int = 168, max_results: int = 20) -> List[PaperMetadata]:
        """Fetch YouTube videos via channel RSS feeds."""
        if not FEEDPARSER_AVAILABLE:
            logger.warning("feedparser not available, cannot fetch YouTube RSS")
            return []

        papers = []
        cutoff = datetime.utcnow() - timedelta(hours=max(hours_back, 168))  # min 7 days

        for channel_id, channel_name, category in YOUTUBE_CHANNELS:
            try:
                feed_url = f"{self.rss_base}{channel_id}"
                feed = feedparser.parse(feed_url)

                for entry in feed.entries[:5]:
                    try:
                        title = entry.get("title", "").strip()
                        link = entry.get("link", "").strip()
                        summary = entry.get("summary", "").strip()
                        published = entry.get("published", "")

                        pub_dt = self._parse_rss_date(published)
                        if pub_dt and pub_dt < cutoff:
                            continue

                        text = f"{title} {summary}".lower()
                        if not self._is_relevant(text, keywords, category):
                            continue

                        # Build a rich abstract
                        abstract = (
                            summary[:300] if summary
                            else f"[{category}] Video from {channel_name}: {title}"
                        )
                        # Prepend YouTube emoji so Discord knows it's a video
                        display_title = f"▶ {title}"

                        papers.append(PaperMetadata(
                            title=display_title,
                            authors=[channel_name],
                            abstract=abstract,
                            url=link,
                            source=self.source_name,
                            published_at=pub_dt or datetime.utcnow(),
                            categories=[category, "Video"],
                            tags=self._extract_tags(title, summary, category),
                        ))
                    except Exception as e:
                        logger.debug(f"Error parsing YouTube entry from {channel_name}: {e}")
                        continue

                time.sleep(0.3)

            except Exception as e:
                logger.warning(f"Error fetching YouTube channel {channel_name}: {e}")
                continue

        # If API key available, also search by keyword
        if self.api_key:
            papers.extend(self._fetch_via_api(keywords, hours_back))

        # Deduplicate by link
        seen_links = set()
        unique = []
        for p in papers:
            if p.url not in seen_links:
                seen_links.add(p.url)
                unique.append(p)

        unique = unique[:max_results]
        logger.info(f"Fetched {len(unique)} YouTube videos")
        return unique

    def _fetch_via_api(self, keywords: List[str], hours_back: int) -> List[PaperMetadata]:
        """Use YouTube Data API v3 to search for recent videos."""
        papers = []
        published_after = (datetime.utcnow() - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%SZ")

        search_queries = [
            "large language model",
            "transformer AI",
            "LLM GPT tutorial",
            "space launch NASA SpaceX",
            "deep learning lecture",
        ]

        for query in search_queries[:3]:
            try:
                url = "https://www.googleapis.com/youtube/v3/search"
                params = {
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "order": "date",
                    "publishedAfter": published_after,
                    "maxResults": 5,
                    "key": self.api_key,
                    "relevanceLanguage": "en",
                    "videoDuration": "medium",  # 4-20 min
                }
                resp = requests.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    for item in resp.json().get("items", []):
                        snippet = item.get("snippet", {})
                        vid_id = item.get("id", {}).get("videoId", "")
                        title = snippet.get("title", "").strip()
                        description = snippet.get("description", "").strip()
                        channel = snippet.get("channelTitle", "YouTube")
                        pub = snippet.get("publishedAt", "")

                        papers.append(PaperMetadata(
                            title=f"▶ {title}",
                            authors=[channel],
                            abstract=description[:300] or f"YouTube video: {title}",
                            url=f"https://www.youtube.com/watch?v={vid_id}",
                            source=self.source_name,
                            published_at=self._parse_rss_date(pub),
                            categories=["Video", "AI"],
                            tags=self._extract_tags(title, description, "AI"),
                        ))
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"YouTube API search error for '{query}': {e}")

        return papers

    def _parse_rss_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(date_str[:25], fmt[:len(date_str[:25])])
                # Strip timezone to naive UTC
                if dt.tzinfo is not None:
                    from datetime import timezone
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                return dt
            except Exception:
                continue
        return None

    def _is_relevant(self, text: str, keywords: List[str], category: str) -> bool:
        # Always include Space and Academic channels
        if category in ("Space", "Academic", "LLM", "AI Research", "Deep Learning"):
            return True
        focus = [
            "llm", "large language model", "transformer", "gpt", "claude", "gemini",
            "ai", "machine learning", "deep learning", "neural", "space", "nasa",
            "spacex", "rocket", "satellite", "quantum", "cybersecurity",
        ]
        return any(k in text for k in focus) or any(k.lower() in text for k in keywords)

    def _extract_tags(self, title: str, content: str, category: str) -> List[str]:
        text = f"{title} {content}".lower()
        tags = [category.lower()]
        keyword_map = {
            "llm": "LLM", "transformer": "transformer", "gpt": "GPT",
            "claude": "Claude", "gemini": "Gemini", "space": "space",
            "nasa": "NASA", "spacex": "SpaceX", "deep learning": "deep learning",
            "neural": "neural network", "quantum": "quantum", "lecture": "lecture",
        }
        for k, v in keyword_map.items():
            if k in text:
                tags.append(v)
        return list(set(tags))[:5]

    def test_connection(self) -> bool:
        try:
            # Test with a small known channel RSS
            url = f"{self.rss_base}UCLA_DiR1FfKNvjuUpBHmylQ"  # NASA channel
            resp = requests.get(url, timeout=10)
            ok = resp.status_code == 200
            if ok:
                logger.info("YouTube RSS connection test successful")
            return ok
        except Exception as e:
            logger.error(f"YouTube connection test failed: {e}")
            return False


def create_youtube_fetcher(config: Dict[str, Any]) -> YouTubeFetcher:
    return YouTubeFetcher(config)
