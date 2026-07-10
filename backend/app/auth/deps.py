from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_access_token
from app.database import get_db
from app.models import Space, SpaceMembership, User, UserRole

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": {"code": "unauthorized", "message": "Not authenticated"}})
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": {"code": "unauthorized", "message": "Invalid token"}})
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": {"code": "unauthorized", "message": "User not found"}})
    return user


async def require_teacher(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.teacher:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": {"code": "forbidden", "message": "Teacher only"}})
    return user


async def get_space_or_403(space_id: int, user: User, db: AsyncSession) -> Space:
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "not_found", "message": "Space not found"}})

    if space.teacher_id == user.id:
        return space

    membership = await db.execute(
        select(SpaceMembership).where(SpaceMembership.space_id == space_id, SpaceMembership.user_id == user.id)
    )
    if membership.scalar_one_or_none():
        return space

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": {"code": "forbidden", "message": "Not a space member"}})


async def user_has_space_access(user_id: int, space_id: int, db: AsyncSession) -> bool:
    result = await db.execute(
        select(Space).where(
            Space.id == space_id,
            or_(Space.teacher_id == user_id, Space.id.in_(select(SpaceMembership.space_id).where(SpaceMembership.user_id == user_id))),
        )
    )
    return result.scalar_one_or_none() is not None
