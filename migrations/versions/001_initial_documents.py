"""Initial migration: documents, corrections, processing_tasks tables

Revision ID: 001_initial
Revises: None
Create Date: 2026-07-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==================== documents ====================
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('original_path', sa.String(512), nullable=True),
        sa.Column('status', sa.String(20), nullable=True,
                   server_default='uploaded'),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),

        # OCR Results
        sa.Column('ocr_text_ar', sa.Text(), nullable=True),
        sa.Column('ocr_text_en', sa.Text(), nullable=True),
        sa.Column('fused_text', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('ocr_engines_used', sa.JSON(), nullable=True,
                   server_default='[]'),

        # Medical terms extraction
        sa.Column('medical_terms', sa.JSON(), nullable=True,
                   server_default='[]'),
        sa.Column('translated_terms', sa.JSON(), nullable=True,
                   server_default='[]'),

        # Processing metadata
        sa.Column('processing_time', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(),
                   server_default=sa.func.now(),
                   onupdate=sa.func.now()),
    )
    op.create_index('ix_documents_id', 'documents', ['id'])

    # ==================== corrections ====================
    op.create_table(
        'corrections',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('document_id', sa.Integer(),
                   sa.ForeignKey('documents.id'), nullable=True),
        sa.Column('original_text', sa.Text(), nullable=False),
        sa.Column('corrected_text', sa.Text(), nullable=False),
        sa.Column('context', sa.Text(), nullable=True),

        sa.Column('confidence', sa.Float(), nullable=True,
                   server_default='0.0'),
        sa.Column('auto_applied', sa.Boolean(), nullable=True,
                   server_default='0'),

        # Promotion tracking
        sa.Column('frequency', sa.Integer(), nullable=True,
                   server_default='1'),
        sa.Column('first_seen', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('last_seen', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('max_confidence', sa.Float(), nullable=True,
                   server_default='0.0'),

        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_corrections_id', 'corrections', ['id'])
    op.create_index('ix_corrections_document_id', 'corrections',
                    ['document_id'])

    # ==================== processing_tasks ====================
    op.create_table(
        'processing_tasks',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('task_id', sa.String(100), unique=True, nullable=False),
        sa.Column('document_id', sa.Integer(),
                   sa.ForeignKey('documents.id'), nullable=True),
        sa.Column('status', sa.String(20), nullable=True,
                   server_default='pending'),
        sa.Column('engine', sa.String(50), nullable=True),

        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),

        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_processing_tasks_id', 'processing_tasks', ['id'])
    op.create_index('ix_processing_tasks_task_id', 'processing_tasks',
                    ['task_id'], unique=True)


def downgrade() -> None:
    op.drop_table('processing_tasks')
    op.drop_table('corrections')
    op.drop_table('documents')