# app/db/models/auth.py - Updated with complete RBAC
"""
Authentication Database Models - Complete RBAC Implementation
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List
import uuid

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    ForeignKey, Enum as SQLEnum, JSON, Index, LargeBinary
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY

Base = declarative_base()

class UserRole(str, Enum):
    """User roles for granular RBAC"""
    SUPER_ADMIN = "super_admin"      # Full access to everything
    ADMIN = "admin"                 # Administrative access
    EDITOR = "editor"                # Can create/edit content
    USER = "user"                   # Basic user access
    VIEWER = "viewer"               # Read-only access
    GUEST = "guest"                 # Limited access

class UserStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    BANNED = "banned"

class PermissionCategory(str, Enum):
    """Permission categories"""
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
    """User model with complete RBAC support"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))

    # Authentication
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # Profile
    full_name = Column(String(100))
    avatar_url = Column(String(500))
    bio = Column(String(500))

    # Default role (can be overridden by UserRoleAssignment)
    default_role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    status = Column(SQLEnum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # Security
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    last_failed_login = Column(DateTime(timezone=True))
    locked_until = Column(DateTime(timezone=True))
    last_password_change = Column(DateTime(timezone=True))
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(255))

    # Preferences
    preferred_language = Column(String(10), default="en")
    timezone = Column(String(50), default="UTC")
    theme = Column(String(20), default="light")

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=False)
    last_login = Column(DateTime(timezone=True))

    # Relationships
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")
    jobs = relationship("Job", back_populates="owner")
    user_roles = relationship("UserRoleAssignment", back_populates="user")
    user_permissions = relationship("UserPermissionAssignment", back_populates="user")
    owned_datasets = relationship("Dataset", back_populates="owner")
    owned_models = relationship("Model", back_populates="owner")
    sessions = relationship("UserSession", back_populates="user")

    # Indexes
    __table_args__ = (
        Index('ix_users_email', 'email'),
        Index('ix_users_username', 'username'),
        Index('ix_users_uuid', 'uuid'),
        Index('ix_users_status', 'status'),
        Index('ix_users_created_at', 'created_at'),
    )

    @property
    def roles(self) -> List[UserRole]:
        """Get all roles for this user"""
        return [ura.role.name for ura in self.user_roles]

    @property
    def permissions(self) -> List[str]:
        """Get all permission codenames for this user"""
        permissions = set()
        for ura in self.user_roles:
            for rp in ura.role.role_permissions:
                permissions.add(rp.permission.codename)
        # Add direct permissions
        for upa in self.user_permissions:
            permissions.add(upa.permission.codename)
        return list(permissions)

    @property
    def is_active(self) -> bool:
        """Check if user is active"""
        if self.status != UserStatus.ACTIVE:
            return False
        if self.locked_until and self.locked_until > datetime.utcnow():
            return False
        return True

    def has_permission(self, permission_codename: str) -> bool:
        """Check if user has specific permission"""
        return permission_codename in self.permissions

    def has_role(self, role_name: str) -> bool:
        """Check if user has specific role"""
        return role_name in self.roles

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', roles={self.roles})>"

class RefreshToken(Base):
    """Refresh token model with complete revocation support"""
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    jti = Column(String(36), unique=True, index=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)

    # Metadata
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    device_info = Column(JSON)
    device_fingerprint = Column(String(255))

    # Security
    is_revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime(timezone=True))
    revoked_reason = Column(String(255))
    revoked_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_used_at = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")
    revoker = relationship("User", foreign_keys=[revoked_by])

    # Indexes
    __table_args__ = (
        Index('ix_refresh_tokens_user_id', 'user_id'),
        Index('ix_refresh_tokens_jti', 'jti'),
        Index('ix_refresh_tokens_token_hash', 'token_hash'),
        Index('ix_refresh_tokens_expires', 'expires_at'),
        Index('ix_refresh_tokens_revoked', 'is_revoked'),
    )

    def is_active(self) -> bool:
        """Check if token is active"""
        return not self.is_revoked and self.expires_at > datetime.utcnow()

    def revoke(self, reason: str = "User logout", revoked_by: Optional[int] = None) -> None:
        """Revoke this refresh token"""
        self.is_revoked = True
        self.revoked_at = datetime.utcnow()
        self.revoked_reason = reason
        self.revoked_by = revoked_by

    def __repr__(self):
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, active={self.is_active()})>"

class Permission(Base):
    """Permission model for granular RBAC"""
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    codename = Column(String(100), unique=True, nullable=False)
    description = Column(String(500))
    category = Column(SQLEnum(PermissionCategory), nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    is_sensitive = Column(Boolean, default=False, nullable=False)

    # Relationships
    role_permissions = relationship("RolePermission", back_populates="permission")
    user_permissions = relationship("UserPermissionAssignment", back_populates="permission")

    # Indexes
    __table_args__ = (
        Index('ix_permissions_codename', 'codename'),
        Index('ix_permissions_category', 'category'),
    )

    def __repr__(self):
        return f"<Permission(id={self.id}, codename='{self.codename}', category={self.category.value})>"

class Role(Base):
    """Role model for RBAC"""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(500))
    level = Column(Integer, default=0, nullable=False)  # Higher level = more privileges
    is_default = Column(Boolean, default=False, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    is_assignable = Column(Boolean, default=True, nullable=False)

    # Relationships
    role_permissions = relationship("RolePermission", back_populates="role")
    user_roles = relationship("UserRoleAssignment", back_populates="role")

    # Indexes
    __table_args__ = (
        Index('ix_roles_name', 'name'),
        Index('ix_roles_level', 'level'),
    )

    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}', level={self.level})>"

class RolePermission(Base):
    """Many-to-many relationship between roles and permissions"""
    __tablename__ = "role_permissions"

    role_id = Column(Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)
    permission_id = Column(Integer, ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True)

    # Additional metadata
    assigned_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    role = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")
    assigner = relationship("User", foreign_keys=[assigned_by])

    # Indexes
    __table_args__ = (
        Index('ix_role_permissions_role', 'role_id'),
        Index('ix_role_permissions_permission', 'permission_id'),
    )

    def __repr__(self):
        return f"<RolePermission(role_id={self.role_id}, permission_id={self.permission_id})>"

class UserRoleAssignment(Base):
    """Many-to-many relationship between users and roles"""
    __tablename__ = "user_role_assignments"

    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    role_id = Column(Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)

    # Additional metadata
    assigned_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")
    assigner = relationship("User", foreign_keys=[assigned_by])

    # Indexes
    __table_args__ = (
        Index('ix_user_role_assignments_user', 'user_id'),
        Index('ix_user_role_assignments_role', 'role_id'),
        Index('ix_user_role_assignments_active', 'is_active'),
    )

    def __repr__(self):
        return f"<UserRoleAssignment(user_id={self.user_id}, role_id={self.role_id}, active={self.is_active})>"

class UserPermissionAssignment(Base):
    """Direct permission assignment to users (overrides role permissions)"""
    __tablename__ = "user_permission_assignments"

    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    permission_id = Column(Integer, ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True)
    is_denied = Column(Boolean, default=False, nullable=False)  # If True, explicitly denies permission

    # Additional metadata
    assigned_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="user_permissions")
    permission = relationship("Permission", back_populates="user_permissions")
    assigner = relationship("User", foreign_keys=[assigned_by])

    # Indexes
    __table_args__ = (
        Index('ix_user_permission_assignments_user', 'user_id'),
        Index('ix_user_permission_assignments_permission', 'permission_id'),
    )

    def __repr__(self):
        return f"<UserPermissionAssignment(user_id={self.user_id}, permission_id={self.permission_id})>"

class AuditLog(Base):
    """Enhanced audit log with RBAC context"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(50))

    # RBAC Context
    user_roles = Column(ARRAY(String))  # Roles at time of action
    user_permissions = Column(ARRAY(String))  # Permissions at time of action

    # Details
    details = Column(JSON)
    old_values = Column(JSON)
    new_values = Column(JSON)

    # Context
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    request_id = Column(String(36))
    session_id = Column(String(36))

    # Result
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(String(1000))
    error_code = Column(String(50))

    # Timestamps
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    # Indexes
    __table_args__ = (
        Index('ix_audit_logs_user_id', 'user_id'),
        Index('ix_audit_logs_action', 'action'),
        Index('ix_audit_logs_entity', 'entity_type', 'entity_id'),
        Index('ix_audit_logs_timestamp', 'timestamp'),
        Index('ix_audit_logs_request_id', 'request_id'),
        Index('ix_audit_logs_success', 'success'),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, action='{self.action}')>"

class Job(Base):
    """Job model with RBAC context"""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))

    # Job details
    job_type = Column(String(100), nullable=False)
    title = Column(String(255))
    description = Column(String(1000))

    # Status
    status = Column(String(50), default="pending", nullable=False)
    progress = Column(Integer, default=0, nullable=False)
    result = Column(JSON)

    # Input/Output
    input_data = Column(JSON)
    output_data = Column(JSON)
    error_data = Column(JSON)

    # Files
    input_files = Column(ARRAY(String), default=[])
    output_files = Column(ARRAY(String), default=[])

    # Ownership and RBAC
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    created_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    assigned_to = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))

    # Priority and Scheduling
    priority = Column(Integer, default=0, nullable=False)
    scheduled_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # Retry logic
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    last_error = Column(String(2000))

    # RBAC Context
    required_permission = Column(String(100))  # Permission required to access this job

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=False)

    # Relationships
    owner = relationship("User", back_populates="jobs", foreign_keys=[owner_id])
    creator = relationship("User", foreign_keys=[created_by])
    assignee = relationship("User", foreign_keys=[assigned_to])

    # Indexes
    __table_args__ = (
        Index('ix_jobs_uuid', 'uuid'),
        Index('ix_jobs_status', 'status'),
        Index('ix_jobs_owner_id', 'owner_id'),
        Index('ix_jobs_job_type', 'job_type'),
        Index('ix_jobs_created_at', 'created_at'),
        Index('ix_jobs_priority', 'priority'),
        Index('ix_jobs_required_permission', 'required_permission'),
    )

    def __repr__(self):
        return f"<Job(id={self.id}, uuid='{self.uuid[:8]}...', type='{self.job_type}', status='{self.status}')>"

class UserSession(Base):
    """User session model for session management"""
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    # Session data
    data = Column(JSON)
    ip_address = Column(String(45))
    user_agent = Column(String(500))

    # Security
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_activity = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", back_populates="sessions")

    # Indexes
    __table_args__ = (
        Index('ix_user_sessions_user_id', 'user_id'),
        Index('ix_user_sessions_session_id', 'session_id'),
        Index('ix_user_sessions_expires', 'expires_at'),
        Index('ix_user_sessions_active', 'is_active'),
    )

    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id}, active={self.is_active})>"

def create_default_roles_and_permissions(session):
    """Create default roles and permissions on startup"""
    from sqlalchemy import select

    # Check if roles already exist
    existing_roles = session.execute(select(Role)).scalars().all()
    if existing_roles:
        return

    # Define all permissions
    permissions_data = [
        # User Management
        {"name": "Create Users", "codename": "user.create", "category": PermissionCategory.USER_MANAGEMENT, "description": "Create new user accounts"},
        {"name": "Read Users", "codename": "user.read", "category": PermissionCategory.USER_MANAGEMENT, "description": "View user information"},
        {"name": "Update Users", "codename": "user.update", "category": PermissionCategory.USER_MANAGEMENT, "description": "Update user information"},
        {"name": "Delete Users", "codename": "user.delete", "category": PermissionCategory.USER_MANAGEMENT, "description": "Delete user accounts"},
        {"name": "Manage User Roles", "codename": "user.role.manage", "category": PermissionCategory.USER_MANAGEMENT, "description": "Assign and remove user roles"},
        {"name": "Manage User Permissions", "codename": "user.permission.manage", "category": PermissionCategory.USER_MANAGEMENT, "description": "Assign and remove user permissions"},

        # Authentication
        {"name": "Authenticate", "codename": "auth.authenticate", "category": PermissionCategory.AUTHENTICATION, "description": "Login and authenticate"},
        {"name": "Manage Tokens", "codename": "auth.token.manage", "category": PermissionCategory.AUTHENTICATION, "description": "Create and manage authentication tokens"},
        {"name": "Revoke Tokens", "codename": "auth.token.revoke", "category": PermissionCategory.AUTHENTICATION, "description": "Revoke user tokens"},
        {"name": "Manage Sessions", "codename": "auth.session.manage", "category": PermissionCategory.AUTHENTICATION, "description": "Manage user sessions"},

        # Content Management
        {"name": "Create Content", "codename": "content.create", "category": PermissionCategory.CONTENT_MANAGEMENT, "description": "Create new content"},
        {"name": "Read Content", "codename": "content.read", "category": PermissionCategory.CONTENT_MANAGEMENT, "description": "View content"},
        {"name": "Update Content", "codename": "content.update", "category": PermissionCategory.CONTENT_MANAGEMENT, "description": "Update content"},
        {"name": "Delete Content", "codename": "content.delete", "category": PermissionCategory.CONTENT_MANAGEMENT, "description": "Delete content"},

        # Job Management
        {"name": "Create Jobs", "codename": "job.create", "category": PermissionCategory.JOB_MANAGEMENT, "description": "Create new jobs"},
        {"name": "Read Jobs", "codename": "job.read", "category": PermissionCategory.JOB_MANAGEMENT, "description": "View job information"},
        {"name": "Update Jobs", "codename": "job.update", "category": PermissionCategory.JOB_MANAGEMENT, "description": "Update job information"},
        {"name": "Delete Jobs", "codename": "job.delete", "category": PermissionCategory.JOB_MANAGEMENT, "description": "Delete jobs"},
        {"name": "Manage All Jobs", "codename": "job.manage_all", "category": PermissionCategory.JOB_MANAGEMENT, "description": "Manage all jobs regardless of ownership"},

        # OCR Processing
        {"name": "Run OCR", "codename": "ocr.run", "category": PermissionCategory.OCR_PROCESSING, "description": "Run OCR processing"},
        {"name": "Configure OCR", "codename": "ocr.configure", "category": PermissionCategory.OCR_PROCESSING, "description": "Configure OCR settings"},
        {"name": "Batch OCR", "codename": "ocr.batch", "category": PermissionCategory.OCR_PROCESSING, "description": "Run batch OCR processing"},

        # Training
        {"name": "Train Models", "codename": "training.train", "category": PermissionCategory.TRAINING, "description": "Train new models"},
        {"name": "Configure Training", "codename": "training.configure", "category": PermissionCategory.TRAINING, "description": "Configure training settings"},
        {"name": "Manage Datasets", "codename": "training.dataset.manage", "category": PermissionCategory.TRAINING, "description": "Manage training datasets"},

        # Dataset Management
        {"name": "Create Datasets", "codename": "dataset.create", "category": PermissionCategory.DATASET_MANAGEMENT, "description": "Create new datasets"},
        {"name": "Read Datasets", "codename": "dataset.read", "category": PermissionCategory.DATASET_MANAGEMENT, "description": "View dataset information"},
        {"name": "Update Datasets", "codename": "dataset.update", "category": PermissionCategory.DATASET_MANAGEMENT, "description": "Update dataset information"},
        {"name": "Delete Datasets", "codename": "dataset.delete", "category": PermissionCategory.DATASET_MANAGEMENT, "description": "Delete datasets"},

        # Model Management
        {"name": "Create Models", "codename": "model.create", "category": PermissionCategory.MODEL_MANAGEMENT, "description": "Create new models"},
        {"name": "Read Models", "codename": "model.read", "category": PermissionCategory.MODEL_MANAGEMENT, "description": "View model information"},
        {"name": "Update Models", "codename": "model.update", "category": PermissionCategory.MODEL_MANAGEMENT, "description": "Update model information"},
        {"name": "Delete Models", "codename": "model.delete", "category": PermissionCategory.MODEL_MANAGEMENT, "description": "Delete models"},
        {"name": "Deploy Models", "codename": "model.deploy", "category": PermissionCategory.MODEL_MANAGEMENT, "description": "Deploy models to production"},

        # System Administration
        {"name": "View System Status", "codename": "system.status", "category": PermissionCategory.SYSTEM_ADMIN, "description": "View system status and health"},
        {"name": "Manage System Config", "codename": "system.config.manage", "category": PermissionCategory.SYSTEM_ADMIN, "description": "Manage system configuration"},
        {"name": "Manage System Users", "codename": "system.user.manage", "category": PermissionCategory.SYSTEM_ADMIN, "description": "Manage system-level user settings"},
        {"name": "View Audit Logs", "codename": "system.audit.view", "category": PermissionCategory.SYSTEM_ADMIN, "description": "View audit logs"},
        {"name": "Manage Audit Logs", "codename": "system.audit.manage", "category": PermissionCategory.SYSTEM_ADMIN, "description": "Manage audit log settings"},

        # Audit
        {"name": "View Own Audit Logs", "codename": "audit.view_own", "category": PermissionCategory.AUDIT, "description": "View own audit logs"},
        {"name": "View All Audit Logs", "codename": "audit.view_all", "category": PermissionCategory.AUDIT, "description": "View all audit logs"},
    ]

    # Create permissions
    db_permissions = []
    for perm_data in permissions_data:
        perm = Permission(
            name=perm_data["name"],
            codename=perm_data["codename"],
            description=perm_data["description"],
            category=perm_data["category"],
            is_system=True
        )
        session.add(perm)
        db_permissions.append(perm)

    session.commit()

    # Define roles with their permissions
    roles_data = [
        {
            "name": "Super Admin",
            "description": "Full access to all features and data",
            "level": 100,
            "is_default": False,
            "is_system": True,
            "permissions": [p.codename for p in db_permissions]  # All permissions
        },
        {
            "name": "Admin",
            "description": "Administrative access with most permissions",
            "level": 80,
            "is_default": False,
            "is_system": False,
            "permissions": [
                "user.create", "user.read", "user.update", "user.role.manage", "user.permission.manage",
                "auth.authenticate", "auth.token.manage", "auth.token.revoke", "auth.session.manage",
                "job.create", "job.read", "job.update", "job.delete", "job.manage_all",
                "ocr.run", "ocr.configure", "ocr.batch",
                "training.train", "training.configure", "training.dataset.manage",
                "dataset.create", "dataset.read", "dataset.update", "dataset.delete",
                "model.create", "model.read", "model.update", "model.delete", "model.deploy",
                "system.status", "system.config.manage", "system.audit.view", "system.audit.manage",
                "audit.view_all"
            ]
        },
        {
            "name": "Editor",
            "description": "Can create and manage content, run jobs",
            "level": 60,
            "is_default": False,
            "is_system": False,
            "permissions": [
                "user.read",
                "auth.authenticate", "auth.token.manage",
                "content.create", "content.read", "content.update", "content.delete",
                "job.create", "job.read", "job.update", "job.delete",
                "ocr.run", "ocr.configure",
                "training.dataset.manage",
                "dataset.read", "dataset.update",
                "model.read",
                "system.status",
                "audit.view_own"
            ]
        },
        {
            "name": "User",
            "description": "Basic user access",
            "level": 40,
            "is_default": True,
            "is_system": False,
            "permissions": [
                "user.read",
                "auth.authenticate", "auth.token.manage",
                "content.read",
                "job.create", "job.read", "job.update",
                "ocr.run",
                "dataset.read",
                "model.read",
                "system.status",
                "audit.view_own"
            ]
        },
        {
            "name": "Viewer",
            "description": "Read-only access",
            "level": 20,
            "is_default": False,
            "is_system": False,
            "permissions": [
                "user.read",
                "auth.authenticate",
                "content.read",
                "job.read",
                "ocr.run",
                "dataset.read",
                "model.read",
                "system.status",
                "audit.view_own"
            ]
        },
        {
            "name": "Guest",
            "description": "Limited access for demo purposes",
            "level": 10,
            "is_default": False,
            "is_system": False,
            "permissions": [
                "auth.authenticate",
                "content.read",
                "ocr.run",
                "system.status"
            ]
        }
    ]

    # Create roles
    db_roles = []
    for role_data in roles_data:
        role = Role(
            name=role_data["name"],
            description=role_data["description"],
            level=role_data["level"],
            is_default=role_data["is_default"],
            is_system=role_data["is_system"]
        )
        session.add(role)
        db_roles.append(role)

    session.commit()

    # Map permissions to roles
    for role in db_roles:
        role_perms = [p for p in db_permissions if p.codename in role_data["permissions"]]
        for perm in role_perms:
            assignment = RolePermission(
                role_id=role.id,
                permission_id=perm.id,
                assigned_by=None,  # System assigned
                assigned_at=datetime.utcnow()
            )
            session.add(assignment)

    session.commit()

    print("✅ Created default roles and permissions")