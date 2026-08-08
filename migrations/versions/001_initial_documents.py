"""Initial migration: All tables including RBAC, documents, jobs

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
    # ==================== users ====================
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, nullable=False),
        sa.Column('username', sa.String(50), unique=True, nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(100), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('bio', sa.String(500), nullable=True),
        sa.Column('default_role', sa.String(20), nullable=False, server_default='user'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_failed_login', sa.DateTime(), nullable=True),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.Column('last_password_change', sa.DateTime(), nullable=True),
        sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('mfa_secret', sa.String(255), nullable=True),
        sa.Column('preferred_language', sa.String(10), server_default='en'),
        sa.Column('timezone', sa.String(50), server_default='UTC'),
        sa.Column('theme', sa.String(20), server_default='light'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_uuid', 'users', ['uuid'])
    op.create_index('ix_users_status', 'users', ['status'])

    # ==================== refresh_tokens ====================
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('token_hash', sa.String(255), unique=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('jti', sa.String(36), unique=True, nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('device_info', sa.JSON(), nullable=True),
        sa.Column('device_fingerprint', sa.String(255), nullable=True),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_reason', sa.String(255), nullable=True),
        sa.Column('revoked_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('ix_refresh_tokens_jti', 'refresh_tokens', ['jti'])

    # ==================== permissions ====================
    op.create_table(
        'permissions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('codename', sa.String(100), unique=True, nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_sensitive', sa.Boolean(), nullable=False, server_default='0'),
    )
    op.create_index('ix_permissions_codename', 'permissions', ['codename'])
    op.create_index('ix_permissions_category', 'permissions', ['category'])

    # ==================== roles ====================
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(50), unique=True, nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('level', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_assignable', sa.Boolean(), nullable=False, server_default='1'),
    )
    op.create_index('ix_roles_name', 'roles', ['name'])
    op.create_index('ix_roles_level', 'roles', ['level'])

    # ==================== role_permissions ====================
    op.create_table(
        'role_permissions',
        sa.Column('role_id', sa.Integer(), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_id', sa.Integer(), sa.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('assigned_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_role_permissions_role', 'role_permissions', ['role_id'])
    op.create_index('ix_role_permissions_permission', 'role_permissions', ['permission_id'])

    # ==================== user_role_assignments ====================
    op.create_table(
        'user_role_assignments',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('role_id', sa.Integer(), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('assigned_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
    )
    op.create_index('ix_user_role_assignments_user', 'user_role_assignments', ['user_id'])
    op.create_index('ix_user_role_assignments_active', 'user_role_assignments', ['is_active'])

    # ==================== user_permission_assignments ====================
    op.create_table(
        'user_permission_assignments',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_id', sa.Integer(), sa.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('is_denied', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('assigned_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
    )
    op.create_index('ix_user_perm_assignments_user', 'user_permission_assignments', ['user_id'])

    # ==================== audit_logs ====================
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(100), nullable=False),
        sa.Column('entity_id', sa.String(50), nullable=True),
        sa.Column('user_roles', sa.JSON(), nullable=True),
        sa.Column('user_permissions', sa.JSON(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('old_values', sa.JSON(), nullable=True),
        sa.Column('new_values', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('request_id', sa.String(36), nullable=True),
        sa.Column('session_id', sa.String(36), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('error_message', sa.String(1000), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])

    # ==================== jobs ====================
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, nullable=False),
        sa.Column('job_type', sa.String(100), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('description', sa.String(1000), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('error_data', sa.JSON(), nullable=True),
        sa.Column('input_files', sa.JSON(), nullable=True),
        sa.Column('output_files', sa.JSON(), nullable=True),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assigned_to', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('last_error', sa.String(2000), nullable=True),
        sa.Column('required_permission', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_jobs_uuid', 'jobs', ['uuid'])
    op.create_index('ix_jobs_status', 'jobs', ['status'])
    op.create_index('ix_jobs_owner_id', 'jobs', ['owner_id'])
    op.create_index('ix_jobs_job_type', 'jobs', ['job_type'])

    # ==================== user_sessions ====================
    op.create_table(
        'user_sessions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(255), unique=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('last_activity', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'])
    op.create_index('ix_user_sessions_session_id', 'user_sessions', ['session_id'])

    # ==================== documents ====================
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('original_path', sa.String(512), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, server_default='uploaded'),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('ocr_text_ar', sa.Text(), nullable=True),
        sa.Column('ocr_text_en', sa.Text(), nullable=True),
        sa.Column('fused_text', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('ocr_engines_used', sa.JSON(), nullable=True),
        sa.Column('medical_terms', sa.JSON(), nullable=True),
        sa.Column('translated_terms', sa.JSON(), nullable=True),
        sa.Column('processing_time', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_documents_id', 'documents', ['id'])

    # ==================== corrections ====================
    op.create_table(
        'corrections',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id'), nullable=True),
        sa.Column('original_text', sa.Text(), nullable=False),
        sa.Column('corrected_text', sa.Text(), nullable=False),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('auto_applied', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('frequency', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('first_seen', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('last_seen', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('max_confidence', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_corrections_id', 'corrections', ['id'])
    op.create_index('ix_corrections_document_id', 'corrections', ['document_id'])

    # ==================== processing_tasks ====================
    op.create_table(
        'processing_tasks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('task_id', sa.String(100), unique=True, nullable=False),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id'), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, server_default='pending'),
        sa.Column('engine', sa.String(50), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_processing_tasks_id', 'processing_tasks', ['id'])
    op.create_index('ix_processing_tasks_task_id', 'processing_tasks', ['task_id'], unique=True)


def downgrade() -> None:
    op.drop_table('processing_tasks')
    op.drop_table('corrections')
    op.drop_table('documents')
    op.drop_table('user_sessions')
    op.drop_table('jobs')
    op.drop_table('audit_logs')
    op.drop_table('user_permission_assignments')
    op.drop_table('user_role_assignments')
    op.drop_table('role_permissions')
    op.drop_table('roles')
    op.drop_table('permissions')
    op.drop_table('refresh_tokens')
    op.drop_table('users')