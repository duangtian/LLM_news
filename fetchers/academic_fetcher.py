"""
Academic paper fetcher focused on LLM / Transformer research.
Sources:
  - arXiv (cs.CL, cs.AI, cs.LG, stat.ML)  — keyword-based, recent papers
  - HuggingFace Daily Papers (RSS)
  - Semantic Scholar (open API, no key needed)
  - Papers With Code (API)
Designed for ป.ตรี–เอก level academic content.
"""
import time
import threading
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


# arXiv categories most relevant to LLM / Transformer / AI
ARXIV_LLM_CATEGORIES = [
    "cs.CL",   # Computation and Language
    "cs.AI",   # Artificial Intelligence
    "cs.LG",   # Machine Learning
    "stat.ML", # Statistics - Machine Learning
    "cs.CV",   # Computer Vision
    "cs.IR",   # Information Retrieval
    "cs.RO",   # Robotics
]

# HuggingFace Papers RSS and Papers With Code
HF_PAPERS_RSS = "https://huggingface.co/papers.rss"
PAPERS_WITH_CODE_API = "https://paperswithcode.com/api/v1/papers/"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"

# Keywords for filtering relevance
LLM_KEYWORDS = [
    "large language model", "LLM", "transformer", "attention mechanism",
    "GPT", "BERT", "T5", "llama", "mistral", "claude", "gemini",
    "reinforcement learning from human feedback", "RLHF", "instruction tuning",
    "fine-tuning", "prompt engineering", "in-context learning", "chain of thought",
    "retrieval augmented generation", "RAG", "multimodal", "vision language",
    "diffusion model", "generative AI", "foundation model", "pre-trained model",
    "neural scaling", "emergent abilities", "alignment", "hallucination",
    "benchmark", "evaluation", "reasoning", "code generation", "agent",
]


class AcademicFetcher(BaseFetcher):
    """Fetches academic papers focusing on LLM/Transformer research."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.source_name = "academic"
        self.max_results = config.get("MAX_PAPERS_ACADEMIC", 20)
        self.days_back = config.get("ACADEMIC_DAYS_BACK", 7)
        self.semantic_scholar_key = config.get("SEMANTIC_SCHOLAR_API_KEY", "")
        logger.debug("Academic (LLM-focus) fetcher initialized")

    def is_enabled(self) -> bool:
        return self.config.get("ENABLE_ACADEMIC", True)

    def fetch_papers(self, keywords: List[str], categories: List[str] = None,
                     hours_back: int = 168, max_results: int = 20) -> List[PaperMetadata]:
        papers = []

        # 1. arXiv – recent LLM papers
        papers.extend(self._fetch_arxiv_llm(hours_back))

        # 2. HuggingFace Daily Papers
        papers.extend(self._fetch_huggingface_papers())

        # 3. Papers With Code – trending papers
        papers.extend(self._fetch_papers_with_code())

        # 4. Semantic Scholar search
        papers.extend(self._fetch_semantic_scholar(keywords))

        # Deduplicate by title (first 60 chars)
        seen = set()
        unique = []
        for p in papers:
            key = p.title[:60].lower()
            if key not in seen:
                seen.add(key)
                unique.append(p)

        unique = unique[:max_results]
        logger.info(f"Fetched {len(unique)} academic papers (LLM focus)")
        return unique

    # ------------------------------------------------------------------ #
    #  arXiv – query by LLM keywords, filter to recent papers             #
    # ------------------------------------------------------------------ #
    def _fetch_arxiv_llm(self, hours_back: int) -> List[PaperMetadata]:
        papers = []
        try:
            query_terms = [
                "large language model",
                "transformer attention",
                "LLM fine-tuning",
                "retrieval augmented generation",
                "multimodal language model",
            ]
            query = " OR ".join(f'ti:"{t}"' for t in query_terms[:3])
            cat_filter = " OR ".join(f"cat:{c}" for c in ARXIV_LLM_CATEGORIES[:4])

            url = "https://export.arxiv.org/api/query"
            params = {
                "search_query": f"({query}) AND ({cat_filter})",
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": 15,
                "start": 0,
            }
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code != 200:
                logger.warning(f"arXiv LLM query returned {resp.status_code}")
                return []

            if not FEEDPARSER_AVAILABLE:
                return []

            feed = feedparser.parse(resp.text)
            cutoff = datetime.utcnow() - timedelta(hours=max(hours_back, 168))

            for entry in feed.entries:
                try:
                    title = entry.get("title", "").replace("\n", " ").strip()
                    abstract = entry.get("summary", "").replace("\n", " ").strip()
                    link = entry.get("link", "")
                    published = entry.get("published", "")

                    pub_dt = self._parse_date(published)
                    if pub_dt and pub_dt < cutoff:
                        continue

                    authors = [a.get("name", "") for a in entry.get("authors", [])]
                    arxiv_id = link.split("/abs/")[-1] if "/abs/" in link else None

                    # Tags from categories
                    tags_raw = entry.get("tags", [])
                    cats = [t.get("term", "") for t in tags_raw]

                    papers.append(PaperMetadata(
                        title=f"📄 {title}",
                        authors=authors or ["arXiv"],
                        abstract=abstract,
                        url=link,
                        source=self.source_name,
                        published_at=pub_dt,
                        categories=cats or ["cs.CL"],
                        tags=self._extract_llm_tags(title, abstract),
                        arxiv_id=arxiv_id,
                    ))
                except Exception as e:
                    logger.debug(f"arXiv entry parse error: {e}")
                    continue

        except Exception as e:
            logger.warning(f"arXiv LLM fetch error: {e}")

        logger.debug(f"arXiv LLM: {len(papers)} papers")
        return papers

    # ------------------------------------------------------------------ #
    #  HuggingFace Daily Papers                                           #
    # ------------------------------------------------------------------ #
    def _fetch_huggingface_papers(self) -> List[PaperMetadata]:
        papers = []
        if not FEEDPARSER_AVAILABLE:
            return []
        try:
            feed_result = [None]

            def _parse(out=feed_result):
                try:
                    out[0] = feedparser.parse(HF_PAPERS_RSS)
                except Exception:
                    out[0] = None

            t = threading.Thread(target=_parse, daemon=True)
            t.start()
            t.join(timeout=15)
            if t.is_alive():
                logger.warning("HuggingFace Papers RSS timeout — skipping")
                return []

            feed = feed_result[0]
            if feed is None:
                return []

            for entry in feed.entries[:10]:
                try:
                    title = entry.get("title", "").strip()
                    summary = entry.get("summary", "").strip()
                    link = entry.get("link", "")
                    published = entry.get("published", "")
                    pub_dt = self._parse_date(published)

                    # HF papers are always LLM-relevant — include all
                    papers.append(PaperMetadata(
                        title=f"🤗 {title}",
                        authors=["HuggingFace Papers"],
                        abstract=summary[:400] or f"HuggingFace highlighted paper: {title}",
                        url=link,
                        source=self.source_name,
                        published_at=pub_dt,
                        categories=["LLM", "AI Research"],
                        tags=self._extract_llm_tags(title, summary),
                    ))
                except Exception as e:
                    logger.debug(f"HF entry error: {e}")
                    continue
        except Exception as e:
            logger.warning(f"HuggingFace papers fetch error: {e}")

        logger.debug(f"HuggingFace Papers: {len(papers)} papers")
        return papers

    # ------------------------------------------------------------------ #
    #  Papers With Code – trending                                        #
    # ------------------------------------------------------------------ #
    def _fetch_papers_with_code(self) -> List[PaperMetadata]:
        papers = []
        try:
            resp = requests.get(
                PAPERS_WITH_CODE_API,
                params={"items_per_page": 10, "ordering": "-arxiv_id"},
                timeout=20,
            )
            if resp.status_code != 200:
                return []

            for item in resp.json().get("results", []):
                try:
                    title = item.get("title", "").strip()
                    abstract = item.get("abstract", "").strip()
                    url = item.get("url_abs") or item.get("paper_url", "")
                    published = item.get("published", "") or item.get("arxiv_id", "")

                    if not self._is_llm_relevant(title, abstract):
                        continue

                    pub_dt = self._parse_date(published) if published else None

                    papers.append(PaperMetadata(
                        title=f"💻 {title}",
                        authors=item.get("authors", ["Papers With Code"]),
                        abstract=abstract[:400] or f"Paper with code: {title}",
                        url=url or f"https://paperswithcode.com",
                        source=self.source_name,
                        published_at=pub_dt,
                        categories=["Papers With Code", "LLM"],
                        tags=self._extract_llm_tags(title, abstract),
                    ))
                except Exception as e:
                    logger.debug(f"PwC entry error: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Papers With Code fetch error: {e}")

        logger.debug(f"Papers With Code: {len(papers)} papers")
        return papers

    # ------------------------------------------------------------------ #
    #  Semantic Scholar                                                   #
    # ------------------------------------------------------------------ #
    def _fetch_semantic_scholar(self, keywords: List[str]) -> List[PaperMetadata]:
        papers = []
        try:
            query = " ".join(kw for kw in keywords[:5] if kw)
            if not query:
                query = "large language model transformer"

            headers = {}
            if self.semantic_scholar_key:
                headers["x-api-key"] = self.semantic_scholar_key

            resp = requests.get(
                SEMANTIC_SCHOLAR_API,
                params={
                    "query": query,
                    "fields": "title,abstract,authors,year,externalIds,url,publicationDate",
                    "limit": 10,
                    "sort": "relevance",
                },
                headers=headers,
                timeout=20,
            )
            if resp.status_code != 200:
                logger.debug(f"Semantic Scholar returned {resp.status_code}")
                return []

            for item in resp.json().get("data", []):
                try:
                    title = item.get("title", "").strip()
                    abstract = item.get("abstract", "") or ""
                    abstract = abstract.strip()
                    pub_date = item.get("publicationDate", "") or str(item.get("year", ""))
                    authors = [a.get("name", "") for a in item.get("authors", [])]
                    url = item.get("url", "")
                    ext_ids = item.get("externalIds", {})
                    arxiv_id = ext_ids.get("ArXiv")
                    doi = ext_ids.get("DOI")

                    if not abstract or not self._is_llm_relevant(title, abstract):
                        continue

                    pub_dt = self._parse_date(pub_date) if pub_date else None

                    papers.append(PaperMetadata(
                        title=f"📚 {title}",
                        authors=authors or ["Semantic Scholar"],
                        abstract=abstract[:400],
                        url=url or f"https://api.semanticscholar.org/",
                        source=self.source_name,
                        published_at=pub_dt,
                        categories=["Academic", "LLM"],
                        tags=self._extract_llm_tags(title, abstract),
                        arxiv_id=arxiv_id,
                        doi=doi,
                    ))
                except Exception as e:
                    logger.debug(f"Semantic Scholar entry error: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Semantic Scholar fetch error: {e}")

        logger.debug(f"Semantic Scholar: {len(papers)} papers")
        return papers

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #
    def _is_llm_relevant(self, title: str, abstract: str) -> bool:
        text = f"{title} {abstract}".lower()
        return any(kw.lower() in text for kw in LLM_KEYWORDS[:20])

    def _extract_llm_tags(self, title: str, content: str) -> List[str]:
        text = f"{title} {content}".lower()
        tag_map = {
            "llm": "LLM", "transformer": "Transformer", "gpt": "GPT",
            "bert": "BERT", "llama": "LLaMA", "mistral": "Mistral",
            "rlhf": "RLHF", "fine-tun": "Fine-tuning", "rag": "RAG",
            "multimodal": "Multimodal", "diffusion": "Diffusion",
            "alignment": "Alignment", "reasoning": "Reasoning",
            "agent": "Agent", "benchmark": "Benchmark",
            "code": "Code Generation", "retrieval": "Retrieval",
        }
        tags = []
        for k, v in tag_map.items():
            if k in text:
                tags.append(v)
        return tags[:6]

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        for fmt in (
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d",
            "%Y",
        ):
            try:
                dt = datetime.strptime(date_str[:len(fmt)], fmt)
                if dt.tzinfo is not None:
                    from datetime import timezone
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                return dt
            except Exception:
                continue
        return None

    def test_connection(self) -> bool:
        try:
            resp = requests.get(HF_PAPERS_RSS, timeout=10)
            ok = resp.status_code == 200
            if ok:
                logger.info("Academic fetcher (HuggingFace) connection OK")
            return ok
        except Exception as e:
            logger.error(f"Academic fetcher connection test failed: {e}")
            return False


def create_academic_fetcher(config: Dict[str, Any]) -> AcademicFetcher:
    return AcademicFetcher(config)
