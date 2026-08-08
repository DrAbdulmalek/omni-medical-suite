"""
RBAC Core Module - Permission checking and role management
"""
import logging
from collections.abc import Callable
from functools import wraps

from fastapi import Depends, HTTPException, Request, status

from app.db.models.auth import Role, User, UserRoleAssignment
from app.db.session import get_db
from app.routers.auth import get_current_user

logger = logging.getLogger(__name__)

class RBACError(Exception):
    """Custom RBAC exception"""
    def __init__(self, message: str, status_code: int = status.HTTP_403_FORBIDDEN):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

async def get_user_permissions(user: User, db) -> list[str]:
    """Get all permission codenames for a user"""
    if not user:
        return []

    # Get permissions from roles
    permissions = set()
    for ura in user.user_roles:
        if ura.is_active:
            for rp in ura.role.role_permissions:
                permissions.add(rp.permission.codename)

    # Get direct permissions
    for upa in user.user_permissions:
        if upa.is_active:
            if not upa.is_denied:
                permissions.add(upa.permission.codename)
            else:
                permissions.discard(upa.permission.codename)

    return list(permissions)

async def check_permission(
    user: User,
    required_permission: str,
    db = Depends(get_db)
) -> bool:
    """Check if user has required permission"""
    permissions = await get_user_permissions(user, db)
    return required_permission in permissions

async def check_any_permission(
    user: User,
    required_permissions: list[str],
    db = Depends(get_db)
) -> bool:
    """Check if user has any of the required permissions"""
    permissions = await get_user_permissions(user, db)
    return any(perm in permissions for perm in required_permissions)

async def check_all_permissions(
    user: User,
    required_permissions: list[str],
    db = Depends(get_db)
) -> bool:
    """Check if user has all required permissions"""
    permissions = await get_user_permissions(user, db)
    return all(perm in permissions for perm in required_permissions)

async def check_role(
    user: User,
    required_role: str,
    db = Depends(get_db)
) -> bool:
    """Check if user has required role"""
    if not user:
        return False
    return any(ura.role.name == required_role and ura.is_active for ura in user.user_roles)

async def check_min_role_level(
    user: User,
    min_level: int,
    db = Depends(get_db)
) -> bool:
    """Check if user has role with minimum level"""
    if not user:
        return False
    return any(ura.role.level >= min_level and ura.is_active for ura in user.user_roles)

def require_permission(
    required_permission: str
) -> Callable:
    """Dependency to require specific permission"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract dependencies
            db = None
            current_user = None

            # Find db and current_user in kwargs
            for key, value in kwargs.items():
                if key == 'db':
                    db = value
                elif key == 'current_user':
                    current_user = value

            # If not found in kwargs, try to get from FastAPI request
            request = None
            for arg in args:
                if hasattr(arg, 'url') and hasattr(arg, 'headers'):  # Likely a Request object
                    request = arg
                    break

            if not db or not current_user:
                # Try to get from FastAPI context
                from fastapi import Request
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

                if request:
                    # This is a workaround for FastAPI dependencies
                    try:
                        # We can't easily extract dependencies here, so we'll rely on the function signature
                        pass
                    except:
                        pass

            # If we still don't have current_user, try to get it
            if not current_user:
                try:
                    current_user = await get_current_user(
                        token=kwargs.get('token'),
                        db=db
                    )
                except:
                    current_user = None

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # Check permission
            if not await check_permission(current_user, required_permission, db):
                logger.warning(
                    f"Permission denied: User {current_user.username} (ID: {current_user.id}) "
                    f"attempted to access {func.__name__} without permission '{required_permission}'"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{required_permission}' required"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_any_permission(
    required_permissions: list[str]
) -> Callable:
    """Dependency to require any of the specified permissions"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db = kwargs.get('db')
            current_user = kwargs.get('current_user')

            if not current_user:
                try:
                    current_user = await get_current_user(
                        token=kwargs.get('token'),
                        db=db
                    )
                except:
                    current_user = None

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            if not await check_any_permission(current_user, required_permissions, db):
                logger.warning(
                    f"Permission denied: User {current_user.username} (ID: {current_user.id}) "
                    f"attempted to access {func.__name__} without any of permissions: {required_permissions}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"One of these permissions required: {', '.join(required_permissions)}"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_role(
    required_role: str
) -> Callable:
    """Dependency to require specific role"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db = kwargs.get('db')
            current_user = kwargs.get('current_user')

            if not current_user:
                try:
                    current_user = await get_current_user(
                        token=kwargs.get('token'),
                        db=db
                    )
                except:
                    current_user = None

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            if not await check_role(current_user, required_role, db):
                logger.warning(
                    f"Role denied: User {current_user.username} (ID: {current_user.id}) "
                    f"attempted to access {func.__name__} without role '{required_role}'"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{required_role}' required"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_min_role_level(
    min_level: int
) -> Callable:
    """Dependency to require minimum role level"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db = kwargs.get('db')
            current_user = kwargs.get('current_user')

            if not current_user:
                try:
                    current_user = await get_current_user(
                        token=kwargs.get('token'),
                        db=db
                    )
                except:
                    current_user = None

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            if not await check_min_role_level(current_user, min_level, db):
                logger.warning(
                    f"Role level denied: User {current_user.username} (ID: {current_user.id}) "
                    f"attempted to access {func.__name__} without role level {min_level}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role level {min_level} required"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator

class RBACMiddleware:
    """FastAPI middleware for RBAC"""
    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next):
        response = await call_next(request)
        return response

async def create_default_admin(
    db,
    username: str = "admin",
    email: str = "admin@omni-medical-suite.local",
    password: str | None = None,
    full_name: str = "System Administrator"
) -> User:
    """Create default admin user if not exists"""
    import secrets

    from passlib.context import CryptContext
    from sqlalchemy import select

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # Check if user exists
    result = await db.execute(
        select(User).where(User.username == username)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        return existing_user

    # Generate password if not provided
    if not password:
        password = secrets.token_urlsafe(16)
        print(f"⚠️  Generated admin password: {password}")
        print("🔒 PLEASE CHANGE THIS PASSWORD IMMEDIATELY AFTER FIRST LOGIN!")

    # Create user
    user = User(
        username=username,
        email=email,
        hashed_password=pwd_context.hash(password),
        full_name=full_name,
        default_role=UserRole.SUPER_ADMIN,
        is_superuser=True,
        is_verified=True
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Assign Super Admin role
    result = await db.execute(
        select(Role).where(Role.name == "Super Admin")
    )
    super_admin_role = result.scalar_one_or_none()

    if super_admin_role:
        assignment = UserRoleAssignment(
            user_id=user.id,
            role_id=super_admin_role.id,
            assigned_by=None,  # System assigned
            assigned_at=datetime.utcnow(),
            is_active=True
        )
        db.add(assignment)
        await db.commit()

    return user
