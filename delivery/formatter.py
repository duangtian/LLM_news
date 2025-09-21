"""
Discord message formatting for paper news
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
import pytz
from loguru import logger

from storage.models import PaperCreate, SummaryResponse


class DiscordFormatter:
    """Formats papers into Discord embed messages"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.timezone = pytz.timezone(config.get('TIMEZONE', 'Asia/Bangkok'))
        self.max_title_length = 256  # Discord embed title limit
        self.max_description_length = 4096  # Discord embed description limit
        self.max_field_value_length = 1024  # Discord embed field value limit
    
    def format_papers_as_embeds(self, 
                               papers_with_summaries: List[tuple[PaperCreate, SummaryResponse]]) -> List[Dict[str, Any]]:
        """Format papers as Discord embeds"""
        
        if not papers_with_summaries:
            return [self._create_no_papers_embed()]
        
        embeds = []
        
        # Create individual embeds for each paper
        for i, (paper, summary) in enumerate(papers_with_summaries):
            try:
                embed = self._create_paper_embed(paper, summary, i + 1)
                embeds.append(embed)
            except Exception as e:
                logger.error(f"Error formatting paper {paper.title[:50]}: {e}")
                continue
        
        # Add header embed if multiple papers
        if len(embeds) > 1:
            header_embed = self._create_header_embed(len(embeds))
            embeds.insert(0, header_embed)
        
        logger.info(f"Created {len(embeds)} Discord embeds")
        return embeds
    
    def _create_paper_embed(self, paper: PaperCreate, summary: SummaryResponse, position: int) -> Dict[str, Any]:
        """Create Discord embed for a single paper"""
        
        # Format title
        title = self._format_title(paper.title, position)
        
        # Format description (summary + TL;DR)
        description = self._format_description(summary.summary_thai, summary.tldr_thai)
        
        # Format authors
        authors_text = self._format_authors(paper.authors)
        
        # Format source and date
        source_text = self._format_source(paper.source, paper.published_at)
        
        # Format tags
        tags_text = self._format_tags(paper.tags, paper.categories)
        
        # Choose color based on source
        color = self._get_source_color(paper.source)
        
        # Build embed
        embed = {
            "title": title,
            "description": description,
            "url": paper.url,
            "color": color,
            "fields": [
                {
                    "name": "📝 ผู้แต่ง",
                    "value": authors_text,
                    "inline": True
                },
                {
                    "name": "📊 แหล่งที่มา",
                    "value": source_text,
                    "inline": True
                },
                {
                    "name": "🏷️ หมวดหมู่",
                    "value": tags_text,
                    "inline": False
                }
            ],
            "footer": {
                "text": f"สร้างอัตโนมัติ • {self._get_current_time_str()}"
            }
        }
        
        # Add thumbnail for arXiv papers
        if paper.source == "arxiv" and paper.arxiv_id:
            # Note: arXiv doesn't provide thumbnails, but we can use a generic science icon
            embed["thumbnail"] = {
                "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/ArXiv_web.svg/250px-ArXiv_web.svg.png"
            }
        
        return embed
    
    def _create_header_embed(self, paper_count: int) -> Dict[str, Any]:
        """Create header embed for multiple papers"""
        return {
            "title": "🔬 ข่าวงานวิจัย AI & ML ประจำวัน",
            "description": f"พบงานวิจัยน่าสนใจ **{paper_count}** เรื่องจากแหล่งข้อมูลต่างๆ",
            "color": 0x5865F2,  # Discord blurple
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "📅 วันที่",
                    "value": self._get_current_date_str(),
                    "inline": True
                },
                {
                    "name": "⏰ เวลา",
                    "value": self._get_current_time_str(),
                    "inline": True
                }
            ]
        }
    
    def _create_no_papers_embed(self) -> Dict[str, Any]:
        """Create embed when no papers found"""
        return {
            "title": "📋 ไม่พบงานวิจัยใหม่วันนี้",
            "description": "ไม่มีงานวิจัยที่ผ่านเกณฑ์การคัดกรองในวันนี้ ลองปรับคำค้นหาหรือหมวดหมู่ในการตั้งค่า",
            "color": 0xFFA500,  # Orange
            "footer": {
                "text": f"ตรวจสอบเมื่อ • {self._get_current_time_str()}"
            }
        }
    
    def _format_title(self, title: str, position: int) -> str:
        """Format paper title for embed"""
        # Add position number
        formatted_title = f"{position}. {title}"
        
        # Truncate if too long
        if len(formatted_title) > self.max_title_length:
            formatted_title = formatted_title[:self.max_title_length - 3] + "..."
        
        return formatted_title
    
    def _format_description(self, summary: str, tldr: str) -> str:
        """Format description with summary and TL;DR"""
        description = summary
        
        if tldr:
            description += f"\n\n**TL;DR:** {tldr}"
        
        # Truncate if too long
        if len(description) > self.max_description_length:
            description = description[:self.max_description_length - 3] + "..."
        
        return description
    
    def _format_authors(self, authors: List[str]) -> str:
        """Format authors list"""
        if not authors:
            return "ไม่ระบุผู้แต่ง"
        
        # Limit to first 3 authors
        display_authors = authors[:3]
        authors_text = ", ".join(display_authors)
        
        if len(authors) > 3:
            authors_text += f" และอีก {len(authors) - 3} คน"
        
        # Truncate if too long
        if len(authors_text) > self.max_field_value_length:
            authors_text = authors_text[:self.max_field_value_length - 3] + "..."
        
        return authors_text
    
    def _format_source(self, source: str, published_at: Optional[datetime]) -> str:
        """Format source and publication date"""
        source_map = {
            'arxiv': 'arXiv',
            'crossref': 'วารสารวิชาการ',
            'biorxiv': 'bioRxiv',
            'medrxiv': 'medRxiv'
        }
        
        source_name = source_map.get(source.lower(), source)
        
        if published_at:
            # Convert to local timezone
            if published_at.tzinfo is None:
                published_at = pytz.utc.localize(published_at)
            local_time = published_at.astimezone(self.timezone)
            date_str = local_time.strftime('%Y-%m-%d')
            return f"{source_name} ({date_str})"
        else:
            return source_name
    
    def _format_tags(self, tags: Optional[List[str]], categories: Optional[List[str]]) -> str:
        """Format tags and categories"""
        all_tags = []
        
        # Add categories
        if categories:
            all_tags.extend(categories[:3])  # Limit categories
        
        # Add tags
        if tags:
            all_tags.extend(tags[:3])  # Limit tags
        
        if not all_tags:
            return "ไม่มีหมวดหมู่"
        
        # Remove duplicates and limit total
        unique_tags = list(set(all_tags))[:5]
        tags_text = ", ".join(unique_tags)
        
        # Truncate if too long
        if len(tags_text) > self.max_field_value_length:
            tags_text = tags_text[:self.max_field_value_length - 3] + "..."
        
        return tags_text
    
    def _get_source_color(self, source: str) -> int:
        """Get color based on source"""
        colors = {
            'arxiv': 0xB31B1B,      # arXiv red
            'crossref': 0x2E8B57,   # Sea green
            'biorxiv': 0x4682B4,    # Steel blue
            'medrxiv': 0x9932CC,    # Dark orchid
        }
        return colors.get(source.lower(), 0x808080)  # Gray as default
    
    def _get_current_time_str(self) -> str:
        """Get current time as localized string"""
        now = datetime.utcnow()
        now_utc = pytz.utc.localize(now)
        local_time = now_utc.astimezone(self.timezone)
        return local_time.strftime('%H:%M น.')
    
    def _get_current_date_str(self) -> str:
        """Get current date as localized string"""
        now = datetime.utcnow()
        now_utc = pytz.utc.localize(now)
        local_time = now_utc.astimezone(self.timezone)
        
        # Thai month names
        thai_months = [
            'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
            'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'
        ]
        
        day = local_time.day
        month = thai_months[local_time.month - 1]
        year = local_time.year + 543  # Buddhist calendar
        
        return f"{day} {month} {year}"
    
    def format_error_embed(self, error_message: str) -> Dict[str, Any]:
        """Format error message as embed"""
        return {
            "title": "❌ เกิดข้อผิดพลาด",
            "description": f"ไม่สามารถดึงข้อมูลงานวิจัยได้:\n```{error_message}```",
            "color": 0xFF0000,  # Red
            "footer": {
                "text": f"เวลาที่เกิดข้อผิดพลาด • {self._get_current_time_str()}"
            }
        }
    
    def format_test_embed(self) -> Dict[str, Any]:
        """Format test message embed"""
        return {
            "title": "🧪 ทดสอบระบบ LLM News Bot",
            "description": "ระบบทำงานปกติ! การเชื่อมต่อ Discord สำเร็จ",
            "color": 0x00FF00,  # Green
            "fields": [
                {
                    "name": "📅 วันที่ทดสอบ",
                    "value": self._get_current_date_str(),
                    "inline": True
                },
                {
                    "name": "⏰ เวลาทดสอบ",
                    "value": self._get_current_time_str(),
                    "inline": True
                }
            ],
            "footer": {
                "text": "LLM News Bot • Test Mode"
            }
        }


def create_discord_formatter(config: Dict[str, Any]) -> DiscordFormatter:
    """Factory function to create Discord formatter"""
    return DiscordFormatter(config)