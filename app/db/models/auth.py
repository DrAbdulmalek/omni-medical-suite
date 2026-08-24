# app/db/models/auth.py
"""Authentication and RBAC database models.

The authentication hardening must preserve the complete model surface used by
existing routers and Alembic metadata. Security-sensitive timestamps are
timezone-aware UTC values; legacy migration columns are normalized by the
follow-up migration.
"""
from __future__ import annotations

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
    user_roles = relationship("UserRoleAssignment", back_populates="user")
    user_permissions = relationship("UserPermissionAssignment", back_populates="user")

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_username", "username"),
        Index("ix_users_uuid", "uuid"),
        Index("ix_users_status", "status"),
        Index("ix_users_created_at", "created_at"),
    )

    @property
    def roles(self) -> list[str]:
        return [assignment.role.name for assignment in self.user_roles if assignment.is_active]

    @property
    def permissions(self) -> list[str]:
        permissions: set[str] = set()
        for assignment in self.user_roles:
            if assignment.is_active:
                permissions.update(rp.permission.codename for rp in assignment.role.role_permissions)
        for assignment in self.user_permissions:
            if assignment.is_active:
                if assignment.is_denied:
                    permissions.discard(assignment.permission.codename)
                else:
                    permissions.add(assignment.permission.codename)
        return sorted(permissions)

    @property
    def is_active(self) -> bool:
        if self.status != UserStatus.ACTIVE:
            return False
        return not (self.locked_until and self.locked_until > datetime.now(timezone.utc))

    def has_permission(self, permission_codename: str) -> bool:
        return self.is_superuser or permission_codename in self.permissions

    def has_role(self, role_name: str) -> bool:
        return role_name in self.roles


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    jti = Column(String(36), unique=True, index=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    device_info = Column(JSON)
    device_fingerprint = Column(String(255))
    is_revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime(timezone=True))
    revoked_reason = Column(String(255))
    revoked_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_used_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="refresh_tokens", foreign_keys=[user_id])
    revoker = relationship("User", foreign_keys=[revoked_by])

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_jti", "jti"),
        Index("ix_refresh_tokens_token_hash", "token_hash"),
        Index("ix_refresh_tokens_expires", "expires_at"),
        Index("ix_refresh_tokens_revoked", "is_revoked"),
    )

    def is_active(self) -> bool:
        return not self.is_revoked and self.expires_at > datetime.now(timezone.utc)

    def revoke(self, reason: str = "User logout", revoked_by: int | None = None) -> None:
        self.is_revoked = True
        self.revoked_at = datetime.now(timezone.utc)
        self.revoked_reason = reason
        self.revoked_by = revoked_by


class Permission(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    codename = Column(String(100), unique=True, nullable=False)
    description = Column(String(500))
    category = Column(String(50), nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    is_sensitive = Column(Boolean, default=False, nullable=False)
    role_permissions = relationship("RolePermission", back_populates="permission")
    user_permissions = relationship("UserPermissionAssignment", back_populates="permission")

    __table_args__ = (
        Index("ix_permissions_codename", "codename"),
        Index("ix_permissions_category", "category"),
    )


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(500))
    level = Column(Integer, default=0, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    is_assignable = Column(Boolean, default=True, nullable=False)
    role_permissions = relationship("RolePermission", back_populates="role")
    user_roles = relationship("UserRoleAssignment", back_populates="role")

    __table_args__ = (Index("ix_roles_name", "name"), Index("ix_roles_level", "level"))


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
    assigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    role = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")

    __table_args__ = (
        Index("ix_role_permissions_role", "role_id"),
        Index("ix_role_permissions_permission", "permission_id"),
    )


class UserRoleAssignment(Base):
    __tablename__ = "user_role_assignments"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    assigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True, nullable=False)
    user = relationship("User", back_populates="user_roles", foreign_keys=[user_id])
    role = relationship("Role", back_populates="user_roles")

    __table_args__ = (
        Index("ix_user_role_assignments_user", "user_id"),
        Index("ix_user_role_assignments_role", "role_id"),
        Index("ix_user_role_assignments_active", "is_active"),
    )


class UserPermissionAssignment(Base):
    __tablename__ = "user_permission_assignments"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
    is_denied = Column(Boolean, default=False, nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True, nullable=False)
    user = relationship("User", back_populates="user_permissions", foreign_keys=[user_id])
    permission = relationship("Permission", back_populates="user_permissions")

    __table_args__ = (
        Index("ix_user_perm_assignments_user", "user_id"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(50))
    user_roles = Column(JSON)
    user_permissions = Column(JSON)
    details = Column(JSON)
    old_values = Column(JSON)
    new_values = Column(JSON)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    request_id = Column(String(36))
    session_id = Column(String(36))
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(String(1000))
    error_code = Column(String(50))
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_timestamp", "timestamp"),
    )


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()), nullable=False)
    job_type = Column(String(100), nullable=False)
    title = Column(String(255))
    description = Column(String(1000))
    status = Column(String(50), default="pending", nullable=False)
    progress = Column(Integer, default=0, nullable=False)
    result = Column(JSON)
    input_data = Column(JSON)
    output_data = Column(JSON)
    error_data = Column(JSON)
    input_files = Column(JSON)
    output_files = Column(JSON)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    assigned_to = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    priority = Column(Integer, default=0, nullable=False)
    scheduled_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    last_error = Column(String(2000))
    required_permission = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    data = Column(JSON)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_activity = Column(DateTime(timezone=True))
    user = relationship("User")


# Compatibility hook. Role/permission seeding is now performed by explicit setup code.
def create_default_roles_and_permissions(session):
    return None
