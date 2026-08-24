# app/routers/auth.py
"""Authentication and RBAC management endpoints."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import check_permission, get_user_permissions, require_permission
from app.core.security import get_current_user
from app.db.models.auth import Permission, Role, RolePermission, User, UserRoleAssignment
from app.db.session import get_db

router = APIRouter()


async def log_audit_event(
    db,
    user_id: int,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    success: bool = True,
    details: dict | None = None,
    request: Request | None = None,
):
    """Best-effort audit hook kept as a compatibility boundary.

    The existing audit service can replace this implementation without coupling
    authentication dependencies back to the router.
    """
    return None


@router.get("/me/permissions", response_model=list[str])
async def get_my_permissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    permissions = await get_user_permissions(current_user, db)
    return permissions


@router.get("/me/roles", response_model=list[str])
async def get_my_roles(current_user: User = Depends(get_current_user)):
    return current_user.roles


@router.post("/me/check-permission", response_model=dict)
async def check_my_permission(
    permission: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {
        "permission": permission,
        "has_permission": await check_permission(current_user, permission, db),
    }


@router.post("/roles", response_model=dict)
@require_permission("user.role.manage")
async def create_role(
    name: str,
    description: str = "",
    level: int = 0,
    is_default: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request | None = None,
):
    from sqlalchemy import select

    result = await db.execute(select(Role).where(Role.name == name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role already exists")

    role = Role(
        name=name,
        description=description,
        level=level,
        is_default=is_default,
        is_system=False,
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)

    await log_audit_event(
        db=db,
        user_id=current_user.id,
        action="role_create",
        entity_type="role",
        entity_id=str(role.id),
        details={"name": name, "level": level},
        request=request,
    )
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "level": role.level,
        "is_default": role.is_default,
    }


@router.get("/roles", response_model=list[dict])
@require_permission("user.role.manage")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Role)
        .options(selectinload(Role.role_permissions).selectinload(RolePermission.permission))
        .order_by(Role.level.desc())
    )
    roles = result.scalars().all()
    return [
        {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "level": role.level,
            "is_default": role.is_default,
            "is_system": role.is_system,
            "permissions": [rp.permission.codename for rp in role.role_permissions],
            "permission_count": len(role.role_permissions),
        }
        for role in roles
    ]


@router.post("/roles/{role_id}/permissions/{permission_id}", response_model=dict)
@require_permission("user.role.manage")
async def add_permission_to_role(
    role_id: int,
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request | None = None,
):
    from sqlalchemy import select

    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    permission = (await db.execute(select(Permission).where(Permission.id == permission_id))).scalar_one_or_none()
    if not permission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")

    existing = (
        await db.execute(
            select(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission already assigned to role")

    assignment = RolePermission(
        role_id=role_id,
        permission_id=permission_id,
        assigned_by=current_user.id,
        assigned_at=datetime.utcnow(),
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    await log_audit_event(
        db=db,
        user_id=current_user.id,
        action="role_permission_add",
        entity_type="role_permission",
        entity_id=f"{role_id}-{permission_id}",
        details={
            "role_id": role_id,
            "role_name": role.name,
            "permission_id": permission_id,
            "permission_codename": permission.codename,
        },
        request=request,
    )
    return {
        "role_id": role_id,
        "permission_id": permission_id,
        "role_name": role.name,
        "permission_codename": permission.codename,
    }


@router.get("/permissions", response_model=list[dict])
@require_permission("user.role.manage")
async def list_permissions(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select

    query = select(Permission)
    if category:
        query = query.where(Permission.category == category)
    result = await db.execute(query.order_by(Permission.category, Permission.name))
    return [
        {
            "id": p.id,
            "name": p.name,
            "codename": p.codename,
            "description": p.description,
            "category": p.category.value,
            "is_system": p.is_system,
        }
        for p in result.scalars().all()
    ]


@router.post("/users/{user_id}/roles/{role_id}", response_model=dict)
@require_permission("user.role.manage")
async def assign_role_to_user(
    user_id: int,
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request | None = None,
):
    from sqlalchemy import select

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    existing = (
        await db.execute(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.role_id == role_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role already assigned to user")

    assignment = UserRoleAssignment(
        user_id=user_id,
        role_id=role_id,
        assigned_by=current_user.id,
        assigned_at=datetime.utcnow(),
        is_active=True,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    await log_audit_event(
        db=db,
        user_id=current_user.id,
        action="user_role_assign",
        entity_type="user_role",
        entity_id=f"{user_id}-{role_id}",
        details={
            "user_id": user_id,
            "username": user.username,
            "role_id": role_id,
            "role_name": role.name,
        },
        request=request,
    )
    return {
        "user_id": user_id,
        "username": user.username,
        "role_id": role_id,
        "role_name": role.name,
    }
