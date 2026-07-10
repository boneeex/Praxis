from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user, get_space_or_403, require_teacher
from app.database import get_db
from app.models import Space, SpaceKind, SpaceMembership, User, UserRole
from app.schemas import JoinIn, MemberOut, SpaceCreateIn, SpaceOut, SpacePatchIn
from app.services.storage import generate_invite_code

router = APIRouter(tags=["spaces"])


@router.post("/spaces", response_model=SpaceOut)
async def create_space(
    data: SpaceCreateIn,
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    for _ in range(5):
        code = generate_invite_code()
        existing = await db.execute(select(Space).where(Space.invite_code == code))
        if not existing.scalar_one_or_none():
            break
    else:
        raise HTTPException(status_code=500, detail={"error": {"code": "server_error", "message": "Could not generate invite code"}})

    space = Space(
        teacher_id=user.id,
        kind=data.kind,
        title=data.title,
        rate_cents=data.rate_cents,
        invite_code=code,
    )
    db.add(space)
    await db.flush()
    return SpaceOut.model_validate(space)


@router.get("/spaces", response_model=list[SpaceOut])
async def list_spaces(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role == UserRole.teacher:
        result = await db.execute(select(Space).where(Space.teacher_id == user.id).order_by(Space.created_at.desc()))
    else:
        result = await db.execute(
            select(Space)
            .join(SpaceMembership, SpaceMembership.space_id == Space.id)
            .where(SpaceMembership.user_id == user.id)
            .order_by(Space.created_at.desc())
        )
    return [SpaceOut.model_validate(s) for s in result.scalars().all()]


@router.get("/spaces/{space_id}", response_model=SpaceOut)
async def get_space(space_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    space = await get_space_or_403(space_id, user, db)
    return SpaceOut.model_validate(space)


@router.patch("/spaces/{space_id}", response_model=SpaceOut)
async def patch_space(
    space_id: int,
    data: SpacePatchIn,
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Space).where(Space.id == space_id, Space.teacher_id == user.id))
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Space not found"}})
    if data.title is not None:
        space.title = data.title
    if data.rate_cents is not None:
        space.rate_cents = data.rate_cents
    await db.flush()
    return SpaceOut.model_validate(space)


@router.delete("/spaces/{space_id}")
async def delete_space(space_id: int, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Space).where(Space.id == space_id, Space.teacher_id == user.id))
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Space not found"}})
    await db.delete(space)
    return {"ok": True}


@router.post("/spaces/{space_id}/invite/rotate", response_model=SpaceOut)
async def rotate_invite(space_id: int, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Space).where(Space.id == space_id, Space.teacher_id == user.id))
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Space not found"}})
    space.invite_code = generate_invite_code()
    await db.flush()
    return SpaceOut.model_validate(space)


@router.get("/spaces/{space_id}/members", response_model=list[MemberOut])
async def list_members(space_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await get_space_or_403(space_id, user, db)
    result = await db.execute(
        select(SpaceMembership, User)
        .join(User, User.id == SpaceMembership.user_id)
        .where(SpaceMembership.space_id == space_id)
    )
    return [
        MemberOut(user_id=u.id, display_name=u.display_name, joined_at=m.joined_at)
        for m, u in result.all()
    ]


@router.delete("/spaces/{space_id}/members/{user_id}")
async def remove_member(
    space_id: int,
    user_id: int,
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Space).where(Space.id == space_id, Space.teacher_id == user.id))
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Space not found"}})
    membership = await db.execute(
        select(SpaceMembership).where(SpaceMembership.space_id == space_id, SpaceMembership.user_id == user_id)
    )
    row = membership.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Member not found"}})
    await db.delete(row)
    return {"ok": True}


@router.post("/join", response_model=SpaceOut)
async def join_space(data: JoinIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != UserRole.student:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Only students can join"}})

    result = await db.execute(select(Space).where(Space.invite_code == data.invite_code.upper()))
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=404, detail={"error": {"code": "invalid_code", "message": "Invalid invite code"}})

    if space.kind == SpaceKind.single:
        count_result = await db.execute(
            select(func.count()).select_from(SpaceMembership).where(SpaceMembership.space_id == space.id)
        )
        if count_result.scalar() >= 1:
            existing = await db.execute(
                select(SpaceMembership).where(SpaceMembership.space_id == space.id, SpaceMembership.user_id == user.id)
            )
            if existing.scalar_one_or_none():
                return SpaceOut.model_validate(space)
            raise HTTPException(status_code=422, detail={"error": {"code": "space_full", "message": "This space is for one student only"}})

    existing = await db.execute(
        select(SpaceMembership).where(SpaceMembership.space_id == space.id, SpaceMembership.user_id == user.id)
    )
    if existing.scalar_one_or_none():
        return SpaceOut.model_validate(space)

    db.add(SpaceMembership(space_id=space.id, user_id=user.id))
    await db.flush()
    return SpaceOut.model_validate(space)
