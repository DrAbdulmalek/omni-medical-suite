# app/routers/auth.py
"""
Authentication Router - with RBAC endpoints
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.auth import (
    User, Permission, Role, RolePermission, UserRoleAssignment, UserPermissionAssignment, UserRole
)
from app.core.rbac import (
    require_permission, require_any_permission, require_role, require_min_role_level,
    get_user_permissions, check_permission, RBACError
)

router = APIRouter()
security = HTTPBearer()

# --- Placeholder for get_current_user (depends on existing auth implementation) ---
async def get_current_user(
    token: str = None,
    db: AsyncSession = None
) -> User:
    """Get current authenticated user - placeholder"""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not implemented"
    )

# --- Placeholder for log_audit_event ---
async def log_audit_event(
    db, user_id: int, action: str, entity_type: str,
    entity_id: str = None, success: bool = True,
    details: dict = None, request: Request = None
):
    """Log an audit event - placeholder"""
    pass

@router.get("/me/permissions", response_model=List[str])
async def get_my_permissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's permissions"""
    permissions = await get_user_permissions(current_user, db)
    return permissions

@router.get("/me/roles", response_model=List[str])
async def get_my_roles(
    current_user: User = Depends(get_current_user)
):
    """Get current user's roles"""
    return current_user.roles

@router.post("/me/check-permission", response_model=dict)
async def check_my_permission(
    permission: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Check if current user has specific permission"""
    has_permission = await check_permission(current_user, permission, db)
    return {
        "permission": permission,
        "has_permission": has_permission
    }

# Admin endpoints for RBAC management
@router.post("/roles", response_model=dict)
@require_permission("user.role.manage")
async def create_role(
    name: str,
    description: str = "",
    level: int = 0,
    is_default: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Create new role (Admin only)"""
    from sqlalchemy import select

    # Check if role exists
    result = await db.execute(
        select(Role).where(Role.name == name)
    )
    existing_role = result.scalar_one_or_none()

    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role already exists"
        )

    # Create role
    role = Role(
        name=name,
        description=description,
        level=level,
        is_default=is_default,
        is_system=False
    )

    db.add(role)
    await db.commit()
    await db.refresh(role)

    # Log creation
    await log_audit_event(
        db=db,
        user_id=current_user.id,
        action="role_create",
        entity_type="role",
        entity_id=str(role.id),
        success=True,
        details={"name": name, "level": level},
        request=request
    )

    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "level": role.level,
        "is_default": role.is_default
    }

@router.get("/roles", response_model=List[dict])
@require_permission("user.role.manage")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all roles (Admin only)"""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Role).options(
            selectinload(Role.role_permissions).selectinload(RolePermission.permission)
        ).order_by(Role.level.desc())
    )
    roles = result.scalars().all()

    roles_data = []
    for role in roles:
        permissions = [rp.permission.codename for rp in role.role_permissions]
        roles_data.append({
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "level": role.level,
            "is_default": role.is_default,
            "is_system": role.is_system,
            "permissions": permissions,
            "permission_count": len(permissions)
        })

    return roles_data

@router.post("/roles/{role_id}/permissions/{permission_id}", response_model=dict)
@require_permission("user.role.manage")
async def add_permission_to_role(
    role_id: int,
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Add permission to role (Admin only)"""
    from sqlalchemy import select

    # Check if role exists
    result = await db.execute(
        select(Role).where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Check if permission exists
    result = await db.execute(
        select(Permission).where(Permission.id == permission_id)
    )
    permission = result.scalar_one_or_none()

    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )

    # Check if already assigned
    result = await db.execute(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permission already assigned to role"
        )

    # Create assignment
    assignment = RolePermission(
        role_id=role_id,
        permission_id=permission_id,
        assigned_by=current_user.id,
        assigned_at=datetime.utcnow()
    )

    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    # Log assignment
    await log_audit_event(
        db=db,
        user_id=current_user.id,
        action="role_permission_add",
        entity_type="role_permission",
        entity_id=f"{role_id}-{permission_id}",
        success=True,
        details={
            "role_id": role_id,
            "role_name": role.name,
            "permission_id": permission_id,
            "permission_codename": permission.codename
        },
        request=request
    )

    return {
        "role_id": role_id,
        "permission_id": permission_id,
        "role_name": role.name,
        "permission_codename": permission.codename
    }

@router.get("/permissions", response_model=List[dict])
@require_permission("user.role.manage")
async def list_permissions(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all permissions (Admin only)"""
    from sqlalchemy import select

    query = select(Permission)
    if category:
        query = query.where(Permission.category == category)

    result = await db.execute(query.order_by(Permission.category, Permission.name))
    permissions = result.scalars().all()

    return [{
        "id": p.id,
        "name": p.name,
        "codename": p.codename,
        "description": p.description,
        "category": p.category.value,
        "is_system": p.is_system
    } for p in permissions]

@router.post("/users/{user_id}/roles/{role_id}", response_model=dict)
@require_permission("user.role.manage")
async def assign_role_to_user(
    user_id: int,
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Assign role to user (Admin only)"""
    from sqlalchemy import select

    # Check if user exists
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if role exists
    result = await db.execute(
        select(Role).where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Check if already assigned
    result = await db.execute(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == role_id
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role already assigned to user"
        )

    # Create assignment
    assignment = UserRoleAssignment(
        user_id=user_id,
        role_id=role_id,
        assigned_by=current_user.id,
        assigned_at=datetime.utcnow(),
        is_active=True
    )

    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    # Log assignment
    await log_audit_event(
        db=db,
        user_id=current_user.id,
        action="user_role_assign",
        entity_type="user_role",
        entity_id=f"{user_id}-{role_id}",
        success=True,
        details={
            "user_id": user_id,
            "username": user.username,
            "role_id": role_id,
            "role_name": role.name
        },
        request=request
    )

    return {
        "user_id": user_id,
        "username": user.username,
        "role_id": role_id,
        "role_name": role.name
    }