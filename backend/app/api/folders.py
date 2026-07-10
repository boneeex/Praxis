from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_space_or_403
from app.database import get_db
from app.models import Folder, Material, User, UserRole
from app.schemas import FolderCreateIn, FolderOut, FolderPatchIn

router = APIRouter(tags=["folders"])


@router.get("/spaces/{space_id}/folders", response_model=list[FolderOut])
async def list_folders(space_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await get_space_or_403(space_id, user, db)
    result = await db.execute(select(Folder).where(Folder.space_id == space_id).order_by(Folder.name))
    return [FolderOut.model_validate(f) for f in result.scalars().all()]


@router.post("/spaces/{space_id}/folders", response_model=FolderOut)
async def create_folder(
    space_id: int,
    data: FolderCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_space_or_403(space_id, user, db)
    folder = Folder(space_id=space_id, parent_id=data.parent_id, name=data.name)
    db.add(folder)
    await db.flush()
    return FolderOut.model_validate(folder)


@router.patch("/folders/{folder_id}", response_model=FolderOut)
async def patch_folder(
    folder_id: int,
    data: FolderPatchIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Folder).where(Folder.id == folder_id))
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Folder not found"}})
    await get_space_or_403(folder.space_id, user, db)
    if data.name is not None:
        folder.name = data.name
    if data.parent_id is not None:
        folder.parent_id = data.parent_id
    await db.flush()
    return FolderOut.model_validate(folder)


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Folder).where(Folder.id == folder_id))
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Folder not found"}})
    await get_space_or_403(folder.space_id, user, db)

    materials = await db.execute(select(Material).where(Material.folder_id == folder_id))
    for m in materials.scalars().all():
        m.folder_id = None
    await db.delete(folder)
    return {"ok": True}
