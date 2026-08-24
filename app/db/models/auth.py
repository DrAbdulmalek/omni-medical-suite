# app/db/models/auth.py - Updated with complete RBAC
"""
Authentication Database Models - Complete RBAC Implementation
"""
import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    EDITOR = "editor"
    USER = "user"
    VIEWER = "viewer"
    GUEST = "guest"

class UserStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    BANNED = "banned"

class PermissionCategory(StrEnum):
    USER_MANAGEMENT = "user_management"
    AUTHENTICATION = "authentication"
    CONTENT_MANAGEMENT = "content_management"
    JOB_MANAGEMENT = "job_management"
    OCR_PROCESSING = "ocr_processing"
    TRAINING = "training"
    DATASET_MANAGEMENT = "dataset_management"
    MODEL_MANAGEMENT = "model_management"
    SYSTEM_ADMIN = "system_admin"
    AUDIT = "audit"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    avatar_url = Column(String(500))
    bio = Column(String(500))
    default_role = Column(String(20), default=UserRole.USER, nullable=False)
    status = Column(String(20), default=UserStatus.ACTIVE, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    last_failed_login = Column(DateTime(timezone=True))
    locked_until = Column(DateTime(timezone=True))
    last_password_change = Column(DateTime(timezone=True))
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(255))
    preferred_language = Column(String(10), default="en")
    timezone = Column(String(50), default="UTC")
    theme = Column(String(20), default="light")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login = Column(DateTime(timezone=True))

    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")
    jobs = relationship("Job", back_populates="owner")
    user_roles = relationship("UserRoleAssignment", back_populates="user")
    user_permissions = relationship("UserPermissionAssignment", back_populates="user")
    owned_datasets = relationship("Dataset", back_populates="owner")
    owned_models = relationship("Model", back_populates="owner")
    sessions = relationship("UserSession", back_populates="user")

    __table_args__ = (
        Index('ix_users_email', 'email'),
        Index('ix_users_username', 'username'),
        Index('ix_users_uuid', 'uuid'),
        Index('ix_users_status', 'status'),
        Index('ix_users_created_at', 'created_at'),
    )

    @property
    def roles(self) -> list[UserRole]:
        return [ura.role.name for ura in self.user_roles]

    @property
    def permissions(self) -> list[str]:
        permissions = set()
        for ura in self.user_roles:
            for rp in ura.role.role_permissions:
                permissions.add(rp.permission.codename)
        for upa in self.user_permissions:
            permissions.add(upa.permission.codename)
        return list(permissions)

    @property
    def is_active(self) -> bool:
        if self.status != UserStatus.ACTIVE:
            return False
        return not (self.locked_until and self.locked_until > datetime.now(timezone.utc))

    def has_permission(self, permission_codename: str) -> bool:
        return permission_codename in self.permissions

    def has_role(self, role_name: str) -> bool:
        return role_name in self.roles

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', roles={self.roles})>"

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    jti = Column(String(36), unique=True, index=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    device_info = Column(JSON)
    device_fingerprint = Column(String(255))
    is_revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime(timezone=True))
    revoked_reason = Column(String(255))
    revoked_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_used_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="refresh_tokens")
    revoker = relationship("User", foreign_keys=[revoked_by])

    __table_args__ = (
        Index('ix_refresh_tokens_user_id', 'user_id'),
        Index('ix_refresh_tokens_jti', 'jti'),
        Index('ix_refresh_tokens_token_hash', 'token_hash'),
        Index('ix_refresh_tokens_expires', 'expires_at'),
        Index('ix_refresh_tokens_revoked', 'is_revoked'),
    )

    def is_active(self) -> bool:
        return not self.is_revoked and self.expires_at > datetime.now(timezone.utc)

    def revoke(self, reason: str = "User logout", revoked_by: int | None = None) -> None:
        self.is_revoked = True
        self.revoked_at = datetime.now(timezone.utc)
        self.revoked_reason = reason
        self.revoked_by = revoked_by
