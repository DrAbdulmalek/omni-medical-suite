"""
SQLAlchemy models for document processing.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, 
    Boolean, ForeignKey, JSON, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_path = Column(String(512))
    status = Column(String(20), default=DocumentStatus.UPLOADED.value)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    
    # OCR Results
    ocr_text_ar = Column(Text)
    ocr_text_en = Column(Text)
    fused_text = Column(Text)
    confidence_score = Column(Float)
    ocr_engines_used = Column(JSON, default=list)
    
    # Medical terms extraction
    medical_terms = Column(JSON, default=list)
    translated_terms = Column(JSON, default=list)
    
    # Processing metadata
    processing_time = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    corrections = relationship("Correction", back_populates="document")


class Correction(Base):
    __tablename__ = "corrections"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    
    original_text = Column(Text, nullable=False)
    corrected_text = Column(Text, nullable=False)
    context = Column(Text)
    
    confidence = Column(Float, default=0.0)
    auto_applied = Column(Boolean, default=False)
    
    # Promotion tracking
    frequency = Column(Integer, default=1)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    max_confidence = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    document = relationship("Document", back_populates="corrections")


class ProcessingTask(Base):
    __tablename__ = "processing_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), unique=True, nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"))
    
    status = Column(String(20), default="pending")
    engine = Column(String(50))
    
    result = Column(JSON)
    error = Column(Text)
    
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
