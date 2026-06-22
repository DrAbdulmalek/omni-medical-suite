"""
Medical Document Segmenter
===========================
Smart segmentation for medical documents, adapted from ai-fuel-engine.

Strategies:
    - size: Token-window sliding with overlap (binary search for boundaries)
    - semantic: Sentence similarity grouping
    - structure: Markdown/heading/paragraph-aware splitting
    - hybrid: structural → size enforcement → semantic refinement

Arabic-aware: Handles Arabic punctuation (٫ ؟ !), RTL text, mixed content.

Author: Dr. Abdulmalek
Version: 1.0.0
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """A segment of medical document text."""
    text: str
    chunk_id: int = 0
    token_count: int = 0
    start_char: int = 0
    end_char: int = 0
    language: str = "auto"  # "arabic", "english", "mixed", "auto"
    source_page: int = 0
    metadata: Dict = field(default_factory=dict)


class MedicalDocumentSegmenter:
    """
    Segments medical documents into chunks suitable for OCR training,
    benchmarking, or RAG ingestion.
    
    This is a DATA PREPARATION tool, not part of the core OCR pipeline.
    Use it when preparing datasets for training or evaluation.
    """
    
    def __init__(
        self,
        max_tokens: int = 512,
        min_tokens: int = 50,
        overlap_tokens: int = 64,
        strategy: str = "hybrid",
    ):
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.overlap_tokens = overlap_tokens
        self.strategy = strategy
        
        # Arabic sentence boundaries
        self._arabic_punctuation = r'[٫؟!。]'
        self._sentence_split_re = re.compile(
            r'(?<=[.!?।' + self._arabic_punctuation[1:-1] + r'])\s+'
        )
    
    def segment(self, text: str, **kwargs) -> List[TextChunk]:
        """Segment text using the configured strategy."""
        if self.strategy == "size":
            return self._segment_by_size(text)
        elif self.strategy == "semantic":
            return self._segment_by_semantic(text)
        elif self.strategy == "structure":
            return self._segment_by_structure(text)
        elif self.strategy == "hybrid":
            return self._segment_hybrid(text)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (Arabic ≈ 3.5 chars/token, English ≈ 4.0)."""
        arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
        other_chars = len(text) - arabic_chars
        return int(arabic_chars / 3.5 + other_chars / 4.0)
    
    def _detect_language(self, text: str) -> str:
        """Detect if text is Arabic, English, or mixed."""
        arabic = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
        english = sum(1 for c in text if c.isalpha() and ('a' <= c.lower() <= 'z'))
        total_alpha = arabic + english
        if total_alpha == 0:
            return "other"
        if arabic / total_alpha > 0.8:
            return "arabic"
        elif english / total_alpha > 0.8:
            return "english"
        return "mixed"
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences, Arabic-aware."""
        sentences = self._sentence_split_re.split(text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _segment_by_size(self, text: str) -> List[TextChunk]:
        """Segment by token window with overlap."""
        sentences = self._split_sentences(text)
        if not sentences:
            return [self._make_chunk(text, 0, 0, len(text))]
        
        chunks = []
        current_sentences = []
        current_tokens = 0
        char_start = 0
        
        for sent in sentences:
            sent_tokens = self._estimate_tokens(sent)
            
            if current_tokens + sent_tokens > self.max_tokens and current_sentences:
                # Emit current chunk
                chunk_text = ' '.join(current_sentences)
                chunk = self._make_chunk(chunk_text, len(chunks), char_start, char_start + len(chunk_text))
                chunks.append(chunk)
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_sentences)
                overlap_tokens = self._estimate_tokens(overlap_text)
                current_sentences = [overlap_text, sent] if overlap_text else [sent]
                current_tokens = overlap_tokens + sent_tokens
                char_start = text.find(sent, char_start)
            else:
                current_sentences.append(sent)
                current_tokens += sent_tokens
        
        # Final chunk
        if current_sentences:
            chunk_text = ' '.join(current_sentences)
            chunk = self._make_chunk(chunk_text, len(chunks), char_start, char_start + len(chunk_text))
            chunks.append(chunk)
        
        return self._merge_small_chunks(chunks)
    
    def _segment_by_semantic(self, text: str) -> List[TextChunk]:
        """Segment by sentence similarity grouping (simplified without ML)."""
        sentences = self._split_sentences(text)
        if not sentences:
            return [self._make_chunk(text, 0, 0, len(text))]
        
        # Group sentences by shared medical keywords
        groups = []
        current_group = [sentences[0]]
        
        for i in range(1, len(sentences)):
            if self._sentences_related(current_group, sentences[i]):
                current_group.append(sentences[i])
            else:
                groups.append(current_group)
                current_group = [sentences[i]]
        
        if current_group:
            groups.append(current_group)
        
        # Create chunks from groups, splitting large ones
        chunks = []
        for group in groups:
            group_text = ' '.join(group)
            if self._estimate_tokens(group_text) <= self.max_tokens:
                chunks.append(self._make_chunk(group_text, len(chunks)))
            else:
                # Fall back to size-based for this group
                sub_chunks = self._segment_by_size(group_text)
                for sc in sub_chunks:
                    sc.chunk_id = len(chunks)
                    chunks.append(sc)
        
        return self._merge_small_chunks(chunks)
    
    def _segment_by_structure(self, text: str) -> List[TextChunk]:
        """Segment by document structure (headings, lists, paragraphs)."""
        chunks = []
        lines = text.split('\n')
        current_section = []
        char_pos = 0
        
        def flush_section():
            if not current_section:
                return
            section_text = '\n'.join(current_section).strip()
            if section_text:
                chunks.append(self._make_chunk(section_text, len(chunks)))
            current_section.clear()
        
        for line in lines:
            stripped = line.strip()
            
            # Detect headings
            if re.match(r'^(#{1,6}\s|[\d]+[.)]\s|[-*]\s)', stripped):
                flush_section()
                current_section.append(stripped)
                char_pos += len(line) + 1
                continue
            
            # Detect blank lines (paragraph separator)
            if not stripped:
                flush_section()
                char_pos += len(line) + 1
                continue
            
            current_section.append(stripped)
            char_pos += len(line) + 1
            
            # Flush if too large
            section_text = '\n'.join(current_section)
            if self._estimate_tokens(section_text) > self.max_tokens:
                flush_section()
        
        flush_section()
        return self._merge_small_chunks(chunks)
    
    def _segment_hybrid(self, text: str) -> List[TextChunk]:
        """Hybrid: structure → size enforcement → semantic merge of small chunks."""
        # Pass 1: Structural segmentation
        chunks = self._segment_by_structure(text)
        
        # Pass 2: Split any oversized chunks
        final_chunks = []
        for chunk in chunks:
            if chunk.token_count > self.max_tokens:
                sub_chunks = self._segment_by_size(chunk.text)
                for sc in sub_chunks:
                    sc.chunk_id = len(final_chunks)
                    sc.source_page = chunk.source_page
                    final_chunks.append(sc)
            else:
                chunk.chunk_id = len(final_chunks)
                final_chunks.append(chunk)
        
        # Pass 3: Merge very small chunks
        final_chunks = self._merge_small_chunks(final_chunks)
        
        return final_chunks
    
    def _sentences_related(self, group: List[str], new_sentence: str) -> bool:
        """Check if a sentence is topically related to the current group (keyword-based)."""
        # Medical keyword overlap heuristic
        medical_keywords = set(re.findall(
            r'(?:ال)?(?:مريض|علاج|جراحة|تشخيص|دواء|مختبر|أشعة|مستشفى|طبيب|تمريض|حالة|حرجة|مستقرة|غرفة|عمليات|عناية|مركزة|طوارئ|قسم|نسائية|قلب|عظام|أطفال|أعصاب|جلدية|بولية|صدر|عيون|أنف|أذن|حنجرة|مخبر|صيدلية|وصفة|فحص|نتيجة|طبيعي|مرتفع|منخفض|معدل|ضغط|سكر|كوليسترول| creatinine|urea|cbc|hba1c|esr|crp|wbc|rbc|plt|hgb)',
            ' '.join(group) + ' ' + new_sentence,
            re.IGNORECASE
        ))
        
        # Also check English medical terms
        en_keywords = set(re.findall(
            r'(?:patient|treatment|surgery|diagnosis|drug|lab|radiology|hospital|doctor|nurse|icu|er|emergency|cardiology|orthopedic|pediatric|neurology|oncology|pathology|dose|mg|ml|hr|bp|spo2)',
            ' '.join(group) + ' ' + new_sentence,
            re.IGNORECASE
        ))
        
        total_keywords = len(medical_keywords) + len(en_keywords)
        
        # If group already has medical context and new sentence shares keywords
        if total_keywords >= 2:
            return True
        
        # If new sentence is short, likely part of current context
        if self._estimate_tokens(new_sentence) < 15:
            return True
        
        return False
    
    def _get_overlap_text(self, sentences: List[str], max_overlap_tokens: int = 0) -> str:
        """Get tail sentences for overlap."""
        if not sentences:
            return ""
        max_overlap_tokens = max_overlap_tokens or self.overlap_tokens
        
        overlap = []
        tokens = 0
        for sent in reversed(sentences[:-1]):  # Skip the last (already in next chunk)
            sent_tokens = self._estimate_tokens(sent)
            if tokens + sent_tokens > max_overlap_tokens:
                break
            overlap.insert(0, sent)
            tokens += sent_tokens
        
        return ' '.join(overlap)
    
    def _make_chunk(self, text: str, chunk_id: int, start: int = 0, end: int = 0) -> TextChunk:
        """Create a TextChunk with computed metadata."""
        return TextChunk(
            text=text,
            chunk_id=chunk_id,
            token_count=self._estimate_tokens(text),
            start_char=start,
            end_char=end or len(text),
            language=self._detect_language(text),
            metadata={
                "strategy": self.strategy,
                "max_tokens": self.max_tokens,
            }
        )
    
    def _merge_small_chunks(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """Merge chunks that are too small."""
        if not chunks:
            return chunks
        
        merged = []
        buffer = []
        buffer_tokens = 0
        
        for chunk in chunks:
            if chunk.token_count < self.min_tokens:
                buffer.append(chunk)
                buffer_tokens += chunk.token_count
            else:
                # Flush buffer first
                if buffer:
                    merged_text = ' '.join(c.text for c in buffer)
                    merged_chunk = self._make_chunk(
                        merged_text, len(merged),
                        buffer[0].start_char, buffer[-1].end_char
                    )
                    merged_chunk.source_page = buffer[0].source_page
                    merged.append(merged_chunk)
                    buffer = []
                    buffer_tokens = 0
                
                chunk.chunk_id = len(merged)
                merged.append(chunk)
        
        # Flush remaining buffer
        if buffer:
            merged_text = ' '.join(c.text for c in buffer)
            merged_chunk = self._make_chunk(
                merged_text, len(merged),
                buffer[0].start_char, buffer[-1].end_char
            )
            merged_chunk.source_page = buffer[0].source_page
            merged.append(merged_chunk)
        
        return merged