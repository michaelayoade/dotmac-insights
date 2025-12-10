"""Admin API endpoints for user, role, and service token management.

Provides CRUD operations for:
- Users: List, update roles, activate/deactivate
- Roles: List, create, update, delete (non-system)
- Permissions: List available permissions
- Service Tokens: Create, list, revoke
- Current User: /me endpoint
"""

from datetime import datetime
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import (
    Principal,
    Require,
    generate_service_token,
    get_current_principal,
)
from app.database import get_db
from app.models.auth import (
    Permission,
    Role,
    RolePermission,
    ServiceToken,
    User,
    UserRole,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class UserResponse(BaseModel):
    id: int
    external_id: str
    email: str
    name: Optional[str]
    picture: Optional[str]
    is_active: bool
    is_superuser: bool
    roles: List[str]
    created_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    role_ids: Optional[List[int]] = None


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_system: bool
    permissions: List[str]
    user_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    permission_ids: List[int] = []


class RoleUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    permission_ids: Optional[List[int]] = None


class PermissionResponse(BaseModel):
    id: int
    scope: str
    description: Optional[str]
    category: Optional[str]

    class Config:
        from_attributes = True


class ServiceTokenResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    token_prefix: str
    scopes: List[str]
    is_active: bool
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    use_count: int
    created_at: datetime
    created_by_email: Optional[str]

    class Config:
        from_attributes = True


class ServiceTokenCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    scopes: List[str] = []
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class ServiceTokenCreatedResponse(BaseModel):
    id: int
    name: str
    token: str  # Only returned on creation!
    token_prefix: str
    scopes: List[str]
    expires_at: Optional[datetime]


class MeResponse(BaseModel):
    id: int
    external_id: Optional[str]
    email: Optional[str]
    name: Optional[str]
    is_superuser: bool
    principal_type: str
    roles: List[str]
    permissions: List[str]


# ============================================================================
# /me Endpoint
# ============================================================================


@router.get("/me", response_model=MeResponse)
async def get_current_user(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Get current authenticated user information."""
    roles = []
    permissions = list(principal.scopes)

    if principal.type == "user":
        user = db.query(User).filter(User.id == principal.id).first()
        if user:
            roles = user.role_names

    return MeResponse(
        id=principal.id,
        external_id=principal.external_id,
        email=principal.email,
        name=principal.name,
        is_superuser=principal.is_superuser,
        principal_type=principal.type,
        roles=roles,
        permissions=permissions,
    )


# ============================================================================
# User Management
# ============================================================================


@router.get(
    "/users",
    response_model=List[UserResponse],
    dependencies=[Depends(Require("admin:users:read"))],
)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """List all users with pagination."""
    query = db.query(User)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    users = query.offset(skip).limit(limit).all()

    return [
        UserResponse(
            id=u.id,
            external_id=u.external_id,
            email=u.email,
            name=u.name,
            picture=u.picture,
            is_active=u.is_active,
            is_superuser=u.is_superuser,
            roles=u.role_names,
            created_at=u.created_at,
            last_login_at=u.last_login_at,
        )
        for u in users
    ]


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(Require("admin:users:read"))],
)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=user.id,
        external_id=user.external_id,
        email=user.email,
        name=user.name,
        picture=user.picture,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        roles=user.role_names,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(Require("admin:users:write"))],
)
async def update_user(
    user_id: int,
    request: UserUpdateRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Update user status or roles."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Don't allow users to modify themselves via admin endpoint
    if principal.type == "user" and principal.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot modify your own account via admin API")

    if request.is_active is not None:
        user.is_active = request.is_active
        logger.info("user_status_changed", user_id=user_id, is_active=request.is_active)

    if request.is_superuser is not None:
        # Only superusers can grant/revoke superuser status
        if not principal.is_superuser:
            raise HTTPException(status_code=403, detail="Only superusers can modify superuser status")
        user.is_superuser = request.is_superuser
        logger.info("user_superuser_changed", user_id=user_id, is_superuser=request.is_superuser)

    if request.role_ids is not None:
        # Clear existing roles and add new ones
        db.query(UserRole).filter(UserRole.user_id == user_id).delete()
        for role_id in request.role_ids:
            role = db.query(Role).filter(Role.id == role_id).first()
            if role:
                user_role = UserRole(
                    user_id=user_id,
                    role_id=role_id,
                    assigned_by_id=principal.id if principal.type == "user" else None,
                )
                db.add(user_role)
        logger.info("user_roles_changed", user_id=user_id, role_ids=request.role_ids)

    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id,
        external_id=user.external_id,
        email=user.email,
        name=user.name,
        picture=user.picture,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        roles=user.role_names,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


# ============================================================================
# Role Management
# ============================================================================


@router.get(
    "/roles",
    response_model=List[RoleResponse],
    dependencies=[Depends(Require("admin:roles:read"))],
)
async def list_roles(
    db: Session = Depends(get_db),
):
    """List all roles."""
    roles = db.query(Role).all()
    return [
        RoleResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            is_system=r.is_system,
            permissions=r.permission_scopes,
            user_count=len(r.users),
            created_at=r.created_at,
        )
        for r in roles
    ]


@router.post(
    "/roles",
    response_model=RoleResponse,
    dependencies=[Depends(Require("admin:roles:write"))],
)
async def create_role(
    request: RoleCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new role."""
    # Check name uniqueness
    existing = db.query(Role).filter(Role.name == request.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Role name already exists")

    role = Role(
        name=request.name,
        description=request.description,
        is_system=False,  # User-created roles are not system roles
    )
    db.add(role)
    db.flush()  # Get the role ID

    # Add permissions
    for perm_id in request.permission_ids:
        perm = db.query(Permission).filter(Permission.id == perm_id).first()
        if perm:
            role_perm = RolePermission(role_id=role.id, permission_id=perm_id)
            db.add(role_perm)

    db.commit()
    db.refresh(role)

    logger.info("role_created", role_id=role.id, name=role.name)

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=role.permission_scopes,
        user_count=len(role.users),
        created_at=role.created_at,
    )


@router.patch(
    "/roles/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(Require("admin:roles:write"))],
)
async def update_role(
    role_id: int,
    request: RoleUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update a role (non-system roles only)."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.is_system:
        raise HTTPException(status_code=400, detail="Cannot modify system roles")

    if request.name:
        existing = db.query(Role).filter(Role.name == request.name, Role.id != role_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Role name already exists")
        role.name = request.name

    if request.description is not None:
        role.description = request.description

    if request.permission_ids is not None:
        # Clear and reset permissions
        db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
        for perm_id in request.permission_ids:
            perm = db.query(Permission).filter(Permission.id == perm_id).first()
            if perm:
                role_perm = RolePermission(role_id=role.id, permission_id=perm_id)
                db.add(role_perm)

    db.commit()
    db.refresh(role)

    logger.info("role_updated", role_id=role.id)

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=role.permission_scopes,
        user_count=len(role.users),
        created_at=role.created_at,
    )


@router.delete(
    "/roles/{role_id}",
    dependencies=[Depends(Require("admin:roles:write"))],
)
async def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
):
    """Delete a role (non-system roles only)."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system roles")

    if role.users:
        raise HTTPException(status_code=400, detail="Cannot delete role with assigned users")

    db.delete(role)
    db.commit()

    logger.info("role_deleted", role_id=role_id)

    return {"status": "deleted", "role_id": role_id}


# ============================================================================
# Permission Management
# ============================================================================


@router.get(
    "/permissions",
    response_model=List[PermissionResponse],
    dependencies=[Depends(Require("admin:roles:read"))],
)
async def list_permissions(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all available permissions."""
    query = db.query(Permission)
    if category:
        query = query.filter(Permission.category == category)
    return query.all()


# ============================================================================
# Service Token Management
# ============================================================================


@router.get(
    "/tokens",
    response_model=List[ServiceTokenResponse],
    dependencies=[Depends(Require("admin:tokens:read"))],
)
async def list_service_tokens(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """List all service tokens."""
    query = db.query(ServiceToken)
    if is_active is not None:
        query = query.filter(ServiceToken.is_active == is_active)
    tokens = query.all()

    return [
        ServiceTokenResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            token_prefix=t.token_prefix,
            scopes=t.scope_list,
            is_active=t.is_active,
            expires_at=t.expires_at,
            last_used_at=t.last_used_at,
            use_count=t.use_count,
            created_at=t.created_at,
            created_by_email=t.created_by_user.email if t.created_by_user else None,
        )
        for t in tokens
    ]


@router.post(
    "/tokens",
    response_model=ServiceTokenCreatedResponse,
    dependencies=[Depends(Require("admin:tokens:write"))],
)
async def create_service_token(
    request: ServiceTokenCreateRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Create a new service token.

    The token value is only returned once on creation!
    """
    if principal.type != "user":
        raise HTTPException(status_code=400, detail="Service tokens can only be created by users")

    # Generate token
    token_value, prefix, token_hash = generate_service_token()

    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

    service_token = ServiceToken(
        name=request.name,
        description=request.description,
        token_prefix=prefix,
        token_hash=token_hash,
        scopes=",".join(request.scopes),
        is_active=True,
        expires_at=expires_at,
        created_by_id=principal.id,
    )
    db.add(service_token)
    db.commit()
    db.refresh(service_token)

    logger.info(
        "service_token_created",
        token_id=service_token.id,
        name=service_token.name,
        created_by=principal.id,
    )

    return ServiceTokenCreatedResponse(
        id=service_token.id,
        name=service_token.name,
        token=token_value,  # Only time we return the full token!
        token_prefix=prefix,
        scopes=service_token.scope_list,
        expires_at=service_token.expires_at,
    )


@router.delete(
    "/tokens/{token_id}",
    dependencies=[Depends(Require("admin:tokens:write"))],
)
async def revoke_service_token(
    token_id: int,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Revoke a service token."""
    token = db.query(ServiceToken).filter(ServiceToken.id == token_id).first()
    if not token:
        raise HTTPException(status_code=404, detail="Service token not found")

    if not token.is_active:
        raise HTTPException(status_code=400, detail="Token already revoked")

    token.is_active = False
    token.revoked_at = datetime.utcnow()
    token.revoked_by_id = principal.id if principal.type == "user" else None
    db.commit()

    logger.info("service_token_revoked", token_id=token_id, revoked_by=principal.id)

    return {"status": "revoked", "token_id": token_id}
