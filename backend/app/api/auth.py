from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    hash_password,
    revoke_refresh_token,
    rotate_refresh_token,
    store_refresh_token,
    verify_password,
)
from app.database import get_db
from app.models import User, UserRole
from app.schemas import (
    AuthOut,
    LoginIn,
    ProfilePatchIn,
    RefreshIn,
    RefreshOut,
    RegisterIn,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthOut)
async def register(data: RegisterIn, db: AsyncSession = Depends(get_db)):
    if data.role not in (UserRole.teacher, UserRole.student):
        raise HTTPException(status_code=400, detail={"error": {"code": "invalid_role", "message": "Invalid role"}})

    existing = await db.execute(select(User).where(User.email == data.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail={"error": {"code": "email_taken", "message": "Email already registered"}})

    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        role=data.role,
        timezone=data.timezone,
    )
    db.add(user)
    await db.flush()

    refresh = create_refresh_token()
    await store_refresh_token(db, user.id, refresh)
    access = create_access_token(user.id)
    return AuthOut(access=access, refresh=refresh, user=UserOut.model_validate(user))


@router.post("/login", response_model=AuthOut)
async def login(data: LoginIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"error": {"code": "invalid_credentials", "message": "Invalid email or password"}})

    refresh = create_refresh_token()
    await store_refresh_token(db, user.id, refresh)
    access = create_access_token(user.id)
    return AuthOut(access=access, refresh=refresh, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=RefreshOut)
async def refresh(data: RefreshIn, db: AsyncSession = Depends(get_db)):
    result = await rotate_refresh_token(db, data.refresh)
    if not result:
        raise HTTPException(status_code=401, detail={"error": {"code": "invalid_refresh", "message": "Invalid refresh token"}})
    access, new_refresh, _ = result
    return RefreshOut(access=access, refresh=new_refresh)


@router.post("/logout")
async def logout(data: RefreshIn, db: AsyncSession = Depends(get_db)):
    await revoke_refresh_token(db, data.refresh)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def patch_me(data: ProfilePatchIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.timezone is not None:
        user.timezone = data.timezone
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    await db.flush()
    return UserOut.model_validate(user)
