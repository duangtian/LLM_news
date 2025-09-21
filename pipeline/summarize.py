"""
Text summarization pipeline for converting papers to Thai news format
"""
import re
from typing import Dict, Any, Tuple
from loguru import logger

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from storage.models import PaperCreate, SummaryRequest, SummaryResponse


class BaseSummarizer:
    """Base class for summarizers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.min_length = int(config.get('SUMMARY_MIN_LENGTH', 150))
        self.max_length = int(config.get('SUMMARY_MAX_LENGTH', 250))
        self.tldr_max_sentences = int(config.get('TLDR_MAX_LENGTH', 2))
    
    def summarize(self, paper: PaperCreate) -> SummaryResponse:
        """Summarize paper to Thai news format"""
        raise NotImplementedError
    
    def _validate_summary(self, summary: str, tldr: str) -> Tuple[str, str]:
        """Validate and clean summary"""
        # Clean summary
        summary = self._clean_text(summary)
        tldr = self._clean_text(tldr)
        
        # Check length
        word_count = len(summary.split())
        if word_count < self.min_length or word_count > self.max_length:
            logger.warning(f"Summary length {word_count} outside range {self.min_length}-{self.max_length}")
        
        return summary, tldr
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = " ".join(text.strip().split())
        
        # Remove markdown-style formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Italic
        text = re.sub(r'`(.*?)`', r'\1', text)        # Code
        
        # Remove common unwanted phrases
        unwanted_phrases = [
            'TL;DR:', 'TLDR:', 'สรุป:', 'Summary:',
            'Abstract:', 'บทคัดย่อ:', 'ข่าวสรุป:'
        ]
        
        for phrase in unwanted_phrases:
            text = text.replace(phrase, '').strip()
        
        return text


class RuleBasedSummarizer(BaseSummarizer):
    """Rule-based summarizer using text processing techniques"""
    
    def summarize(self, paper: PaperCreate) -> SummaryResponse:
        """Create summary using rule-based approach"""
        try:
            # Extract key information
            title = paper.title
            abstract = paper.abstract
            authors = paper.authors[:3]  # Limit to first 3 authors
            
            # Create Thai summary using template
            summary = self._create_template_summary(title, abstract, authors, paper.source)
            tldr = self._create_template_tldr(title, abstract)
            
            # Validate
            summary, tldr = self._validate_summary(summary, tldr)
            
            return SummaryResponse(
                summary_thai=summary,
                tldr_thai=tldr,
                word_count=len(summary.split())
            )
            
        except Exception as e:
            logger.error(f"Error in rule-based summarization: {e}")
            # Fallback summary
            return self._create_fallback_summary(paper)
    
    def _create_template_summary(self, title: str, abstract: str, authors: list, source: str) -> str:
        """Create summary using templates"""
        
        # Extract key concepts from abstract
        key_concepts = self._extract_key_concepts(abstract)
        problem = self._extract_problem(abstract)
        method = self._extract_method(abstract)
        results = self._extract_results(abstract)
        
        # Build summary
        summary_parts = []
        
        # Opening
        if authors:
            author_text = ", ".join(authors[:2])
            if len(authors) > 2:
                author_text += " และคณะ"
            summary_parts.append(f"นักวิจัยจาก {author_text}")
        else:
            summary_parts.append("นักวิจัย")
        
        summary_parts.append(f"ได้นำเสนองานวิจัยเรื่อง \"{title}\"")
        
        # Problem statement
        if problem:
            summary_parts.append(f"ซึ่งเป็นการแก้ปัญหา{problem}")
        
        # Method
        if method:
            summary_parts.append(f"โดยใช้วิธี{method}")
        
        # Results
        if results:
            summary_parts.append(f"ผลการวิจัยพบว่า{results}")
        else:
            summary_parts.append("งานวิจัยนี้มีศักยภาพในการนำไปประยุกต์ใช้ในอนาคต")
        
        # Add source
        source_text = {
            'arxiv': 'arXiv',
            'crossref': 'วารสารวิชาการ',
            'biorxiv': 'bioRxiv',
            'medrxiv': 'medRxiv'
        }.get(source.lower(), source)
        
        summary_parts.append(f"งานวิจัยนี้ถูกเผยแพร่ใน {source_text}")
        
        return " ".join(summary_parts) + "."
    
    def _create_template_tldr(self, title: str, abstract: str) -> str:
        """Create short TL;DR"""
        key_result = self._extract_key_result(abstract)
        if key_result:
            return f"งานวิจัยใหม่เกี่ยวกับ {self._extract_main_topic(title)} {key_result}"
        else:
            topic = self._extract_main_topic(title)
            return f"งานวิจัยใหม่ในสาขา {topic} ที่น่าสนใจ"
    
    def _extract_key_concepts(self, text: str) -> list:
        """Extract key concepts from text"""
        # Common ML/AI keywords
        keywords = [
            'machine learning', 'deep learning', 'neural network', 'ai', 'artificial intelligence',
            'computer vision', 'natural language processing', 'nlp', 'transformers',
            'diffusion', 'gan', 'generative', 'classification', 'regression'
        ]
        
        found_concepts = []
        text_lower = text.lower()
        for keyword in keywords:
            if keyword in text_lower:
                found_concepts.append(keyword)
        
        return found_concepts[:3]  # Limit to top 3
    
    def _extract_problem(self, abstract: str) -> str:
        """Extract problem statement"""
        # Look for problem indicators
        problem_patterns = [
            r'problem[s]?\s+(.*?)[\.\,]',
            r'challenge[s]?\s+(.*?)[\.\,]',
            r'issue[s]?\s+(.*?)[\.\,]',
            r'difficulty\s+(.*?)[\.\,]'
        ]
        
        for pattern in problem_patterns:
            match = re.search(pattern, abstract, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:100]
        
        return ""
    
    def _extract_method(self, abstract: str) -> str:
        """Extract methodology"""
        method_patterns = [
            r'we propose\s+(.*?)[\.\,]',
            r'we present\s+(.*?)[\.\,]',
            r'we introduce\s+(.*?)[\.\,]',
            r'our method\s+(.*?)[\.\,]',
            r'approach\s+(.*?)[\.\,]'
        ]
        
        for pattern in method_patterns:
            match = re.search(pattern, abstract, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:100]
        
        return ""
    
    def _extract_results(self, abstract: str) -> str:
        """Extract results/findings"""
        result_patterns = [
            r'results show\s+(.*?)[\.\,]',
            r'we show\s+(.*?)[\.\,]',
            r'demonstrate[s]?\s+(.*?)[\.\,]',
            r'achieve[s]?\s+(.*?)[\.\,]',
            r'improve[s]?\s+(.*?)[\.\,]'
        ]
        
        for pattern in result_patterns:
            match = re.search(pattern, abstract, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:100]
        
        return ""
    
    def _extract_main_topic(self, title: str) -> str:
        """Extract main topic from title"""
        # Common topic mapping
        topic_map = {
            'machine learning': 'การเรียนรู้ของเครื่อง',
            'deep learning': 'การเรียนรู้เชิงลึก',
            'neural network': 'โครงข่ายประสาทเทียม',
            'computer vision': 'การมองเห็นด้วยคอมพิวเตอร์',
            'natural language': 'การประมวลผลภาษาธรรมชาติ',
            'artificial intelligence': 'ปัญญาประดิษฐ์',
            'diffusion': 'แบบจำลอง Diffusion',
            'transformers': 'โมเดล Transformers'
        }
        
        title_lower = title.lower()
        for eng, thai in topic_map.items():
            if eng in title_lower:
                return thai
        
        return "เทคโนโลยี AI"
    
    def _extract_key_result(self, abstract: str) -> str:
        """Extract key result for TL;DR"""
        # Look for percentage improvements, comparisons
        percentage_match = re.search(r'(\d+)%?\s*(improvement|better|increase|decrease)', abstract, re.IGNORECASE)
        if percentage_match:
            return f"ปรับปรุงประสิทธิภาพได้ {percentage_match.group(1)}%"
        
        # Look for "outperform" or "better than"
        if re.search(r'outperform|better than|superior to', abstract, re.IGNORECASE):
            return "ให้ผลลัพธ์ที่ดีกว่าวิธีเดิม"
        
        return ""
    
    def _create_fallback_summary(self, paper: PaperCreate) -> SummaryResponse:
        """Create fallback summary when main logic fails"""
        summary = f"งานวิจัยเรื่อง \"{paper.title}\" เป็นการศึกษาที่น่าสนใจในสาขาเทคโนโลยี โดยนำเสนอแนวทางใหม่ในการแก้ปัญหาที่เกี่ยวข้อง งานวิจัยนี้มีศักยภาพในการนำไปประยุกต์ใช้ในอนาคต"
        
        tldr = "งานวิจัยใหม่ที่น่าสนใจในสาขาเทคโนโลยี"
        
        return SummaryResponse(
            summary_thai=summary,
            tldr_thai=tldr,
            word_count=len(summary.split())
        )


class OpenAISummarizer(BaseSummarizer):
    """OpenAI-powered summarizer"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library not available")
        
        api_key = config.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not provided")
        
        self.client = openai.OpenAI(api_key=api_key)
        self.model = config.get('OPENAI_MODEL', 'gpt-4o-mini')
    
    def summarize(self, paper: PaperCreate) -> SummaryResponse:
        """Summarize using OpenAI"""
        try:
            prompt = self._build_prompt(paper)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            summary, tldr = self._parse_openai_response(content)
            
            # Validate
            summary, tldr = self._validate_summary(summary, tldr)
            
            return SummaryResponse(
                summary_thai=summary,
                tldr_thai=tldr,
                word_count=len(summary.split())
            )
            
        except Exception as e:
            logger.error(f"OpenAI summarization failed: {e}")
            # Fallback to rule-based
            fallback = RuleBasedSummarizer(self.config)
            return fallback.summarize(paper)
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for OpenAI"""
        return """คุณเป็นนักเขียนข่าววิทยาศาสตร์ที่เชี่ยวชาญในการสรุปงานวิจัยเป็นภาษาไทย 

กฎการเขียน:
1. เขียนภาษาไทยที่เข้าใจง่าย หลีกเลี่ยงศัพท์เทคนิคเกินไป
2. โทนเป็นกลาง ไม่เว่อร์ ไม่โปรโมต
3. ความยาว 150-250 คำ
4. ใส่บริบท: ปัญหาที่แก้ วิธีหลัก ผลลัพธ์ ข้อจำกัด
5. ระบุข้อจำกัดและความไม่แน่นอน
6. หลีกเลี่ยงคำว่า "ยืนยันแล้ว" หรือ "แน่นอน"

รูปแบบตอบ:
สรุป: [ข่าวสรุป 150-250 คำ]
TL;DR: [สรุปสั้น 1-2 ประโยค]"""
    
    def _build_prompt(self, paper: PaperCreate) -> str:
        """Build prompt for OpenAI"""
        authors_text = ", ".join(paper.authors[:3])
        if len(paper.authors) > 3:
            authors_text += " และคณะ"
        
        return f"""งานวิจัย: {paper.title}
ผู้แต่ง: {authors_text}
บทคัดย่อ: {paper.abstract}
แหล่ง: {paper.source}

กรุณาสรุปเป็นข่าวภาษาไทยตามรูปแบบที่กำหนด"""
    
    def _parse_openai_response(self, content: str) -> Tuple[str, str]:
        """Parse OpenAI response to extract summary and TL;DR"""
        lines = content.strip().split('\n')
        
        summary = ""
        tldr = ""
        
        current_section = None
        for line in lines:
            line = line.strip()
            if line.startswith('สรุป:'):
                current_section = 'summary'
                summary = line.replace('สรุป:', '').strip()
            elif line.startswith('TL;DR:'):
                current_section = 'tldr'
                tldr = line.replace('TL;DR:', '').strip()
            elif current_section == 'summary' and line:
                summary += ' ' + line
            elif current_section == 'tldr' and line:
                tldr += ' ' + line
        
        # Fallback parsing
        if not summary or not tldr:
            parts = content.split('TL;DR:')
            if len(parts) == 2:
                summary = parts[0].replace('สรุป:', '').strip()
                tldr = parts[1].strip()
            else:
                # Use full content as summary, generate simple TL;DR
                summary = content.replace('สรุป:', '').strip()
                tldr = "งานวิจัยใหม่ที่น่าสนใจในสาขาเทคโนโลジี"
        
        return summary, tldr


class AnthropicSummarizer(BaseSummarizer):
    """Anthropic Claude-powered summarizer"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic library not available")
        
        api_key = config.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not provided")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = config.get('ANTHROPIC_MODEL', 'claude-3-haiku-20240307')
    
    def summarize(self, paper: PaperCreate) -> SummaryResponse:
        """Summarize using Anthropic Claude"""
        try:
            prompt = self._build_prompt(paper)
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=400,
                temperature=0.3,
                system=self._get_system_prompt(),
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            summary, tldr = self._parse_anthropic_response(content)
            
            # Validate
            summary, tldr = self._validate_summary(summary, tldr)
            
            return SummaryResponse(
                summary_thai=summary,
                tldr_thai=tldr,
                word_count=len(summary.split())
            )
            
        except Exception as e:
            logger.error(f"Anthropic summarization failed: {e}")
            # Fallback to rule-based
            fallback = RuleBasedSummarizer(self.config)
            return fallback.summarize(paper)
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for Anthropic"""
        return """คุณเป็นนักเขียนข่าววิทยาศาสตร์ที่เชี่ยวชาญในการสรุปงานวิจัยเป็นภาษาไทย 

กฎการเขียน:
1. เขียนภาษาไทยที่เข้าใจง่าย หลีกเลี่ยงศัพท์เทคนิคเกินไป
2. โทนเป็นกลาง ไม่เว่อร์ ไม่โปรโมต
3. ความยาว 150-250 คำ
4. ใส่บริบท: ปัญหาที่แก้ วิธีหลัก ผลลัพธ์ ข้อจำกัด
5. ระบุข้อจำกัดและความไม่แน่นอน
6. หลีกเลี่ยงคำว่า "ยืนยันแล้ว" หรือ "แน่นอน"

รูปแบบตอบ:
สรุป: [ข่าวสรุป 150-250 คำ]
TL;DR: [สรุปสั้น 1-2 ประโยค]"""
    
    def _build_prompt(self, paper: PaperCreate) -> str:
        """Build prompt for Anthropic"""
        authors_text = ", ".join(paper.authors[:3])
        if len(paper.authors) > 3:
            authors_text += " และคณะ"
        
        return f"""งานวิจัย: {paper.title}
ผู้แต่ง: {authors_text}
บทคัดย่อ: {paper.abstract}
แหล่ง: {paper.source}

กรุณาสรุปเป็นข่าวภาษาไทยตามรูปแบบที่กำหนด"""
    
    def _parse_anthropic_response(self, content: str) -> Tuple[str, str]:
        """Parse Anthropic response to extract summary and TL;DR"""
        # Same parsing logic as OpenAI
        lines = content.strip().split('\n')
        
        summary = ""
        tldr = ""
        
        current_section = None
        for line in lines:
            line = line.strip()
            if line.startswith('สรุป:'):
                current_section = 'summary'
                summary = line.replace('สรุป:', '').strip()
            elif line.startswith('TL;DR:'):
                current_section = 'tldr'
                tldr = line.replace('TL;DR:', '').strip()
            elif current_section == 'summary' and line:
                summary += ' ' + line
            elif current_section == 'tldr' and line:
                tldr += ' ' + line
        
        # Fallback parsing
        if not summary or not tldr:
            parts = content.split('TL;DR:')
            if len(parts) == 2:
                summary = parts[0].replace('สรุป:', '').strip()
                tldr = parts[1].strip()
            else:
                summary = content.replace('สรุป:', '').strip()
                tldr = "งานวิจัยใหม่ที่น่าสนใจในสาขาเทคโนโลจี"
        
        return summary, tldr


class SummarizerFactory:
    """Factory for creating summarizers"""
    
    @staticmethod
    def create_summarizer(config: Dict[str, Any]) -> BaseSummarizer:
        """Create summarizer based on config"""
        mode_value = config.get('SUMMARIZER_MODE', 'rule_based')
        # Ensure mode is a string
        mode = str(mode_value).lower() if mode_value is not None else 'rule_based'
        
        if mode == 'openai' and OPENAI_AVAILABLE:
            try:
                return OpenAISummarizer(config)
            except Exception as e:
                logger.warning(f"Failed to create OpenAI summarizer: {e}, falling back to rule-based")
                return RuleBasedSummarizer(config)
        
        elif mode == 'anthropic' and ANTHROPIC_AVAILABLE:
            try:
                return AnthropicSummarizer(config)
            except Exception as e:
                logger.warning(f"Failed to create Anthropic summarizer: {e}, falling back to rule-based")
                return RuleBasedSummarizer(config)
        
        else:
            logger.info("Using rule-based summarizer")
            return RuleBasedSummarizer(config)


def create_summarizer(config: Dict[str, Any]) -> BaseSummarizer:
    """Factory function to create summarizer"""
    return SummarizerFactory.create_summarizer(config)