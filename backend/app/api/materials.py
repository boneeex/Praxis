from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_space_or_403
from app.database import get_db
from app.models import CreatorRole, Material, MaterialType, Space, User, UserRole
from app.schemas import (
    ContentOut,
    MaterialCreateIn,
    MaterialOut,
    MaterialPatchIn,
    MaterialUploadUrlIn,
    UploadUrlOut,
)
from app.services.storage import (
    copy_object,
    delete_object,
    empty_ydoc_snapshot,
    generate_storage_key,
    presigned_get_url,
    presigned_put_url,
    put_bytes,
)

router = APIRouter(tags=["materials"])


async def _get_material_with_access(material_id: int, user: User, db: AsyncSession) -> Material:
    result = await db.execute(select(Material).where(Material.id == material_id))
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Material not found"}})
    await get_space_or_403(material.space_id, user, db)
    return material


def _default_config(mtype: MaterialType) -> dict | None:
    if mtype == MaterialType.code_snippet:
        return {"language": "python", "code": ""}
    if mtype == MaterialType.graph:
        return {"expressions": [], "viewport": {"xmin": -10, "xmax": 10, "ymin": -10, "ymax": 10}}
    if mtype == MaterialType.lesson_template:
        return {"items": []}
    return None


@router.get("/spaces/{space_id}/materials", response_model=list[MaterialOut])
async def list_materials(
    space_id: int,
    type: MaterialType | None = None,
    folder_id: int | None = None,
    q: str | None = None,
    sort: str = "recent",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_space_or_403(space_id, user, db)
    query = select(Material).where(Material.space_id == space_id)
    if type:
        query = query.where(Material.type == type)
    if folder_id is not None:
        query = query.where(Material.folder_id == folder_id)
    if q:
        query = query.where(Material.title.ilike(f"%{q}%"))
    if sort == "name":
        query = query.order_by(Material.title)
    else:
        query = query.order_by(Material.updated_at.desc())
    result = await db.execute(query)
    return [MaterialOut.model_validate(m) for m in result.scalars().all()]


@router.post("/spaces/{space_id}/materials", response_model=MaterialOut)
async def create_material(
    space_id: int,
    data: MaterialCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    space = await get_space_or_403(space_id, user, db)
    if data.type in (MaterialType.pdf, MaterialType.image):
        raise HTTPException(status_code=400, detail={"error": {"code": "use_upload", "message": "Use upload-url for files"}})

    config = data.config or _default_config(data.type)
    storage_ref = None
    size_bytes = 0

    if data.type == MaterialType.board:
        storage_ref = generate_storage_key("boards", ".ydoc")
        size_bytes = put_bytes(storage_ref, empty_ydoc_snapshot(), "application/octet-stream")

    creator_role = CreatorRole.teacher if user.role == UserRole.teacher else CreatorRole.student
    material = Material(
        space_id=space_id,
        folder_id=data.folder_id,
        type=data.type,
        title=data.title,
        created_by=user.id,
        created_by_role=creator_role,
        config=config,
        storage_ref=storage_ref,
        size_bytes=size_bytes,
    )
    db.add(material)
    await db.flush()

    if size_bytes > 0:
        teacher = await db.get(User, space.teacher_id)
        if teacher:
            teacher.storage_bytes_used += size_bytes

    return MaterialOut.model_validate(material)


@router.post("/spaces/{space_id}/materials/upload-url", response_model=UploadUrlOut)
async def upload_url(
    space_id: int,
    data: MaterialUploadUrlIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    space = await get_space_or_403(space_id, user, db)
    if data.type not in (MaterialType.pdf, MaterialType.image):
        raise HTTPException(status_code=400, detail={"error": {"code": "invalid_type", "message": "Only pdf/image"}})

    teacher = await db.get(User, space.teacher_id)
    if teacher and teacher.storage_bytes_used + data.size_bytes > teacher.storage_quota_bytes:
        raise HTTPException(status_code=422, detail={"error": {"code": "quota_exceeded", "message": "Storage quota exceeded"}})

    ext = ".pdf" if data.type == MaterialType.pdf else ""
    storage_ref = generate_storage_key("uploads", ext)
    creator_role = CreatorRole.teacher if user.role == UserRole.teacher else CreatorRole.student
    material = Material(
        space_id=space_id,
        folder_id=data.folder_id,
        type=data.type,
        title=data.title,
        created_by=user.id,
        created_by_role=creator_role,
        storage_ref=storage_ref,
        size_bytes=0,
    )
    db.add(material)
    await db.flush()
    url = presigned_put_url(storage_ref, data.content_type)
    return UploadUrlOut(material_id=material.id, put_url=url)


@router.post("/materials/{material_id}/complete-upload", response_model=MaterialOut)
async def complete_upload(
    material_id: int,
    size_bytes: int = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    material = await _get_material_with_access(material_id, user, db)
    if material.type not in (MaterialType.pdf, MaterialType.image):
        raise HTTPException(status_code=400, detail={"error": {"code": "invalid_type", "message": "Not a file material"}})

    space = await db.get(Space, material.space_id)
    teacher = await db.get(User, space.teacher_id) if space else None
    if teacher and teacher.storage_bytes_used + size_bytes > teacher.storage_quota_bytes:
        raise HTTPException(status_code=422, detail={"error": {"code": "quota_exceeded", "message": "Storage quota exceeded"}})

    material.size_bytes = size_bytes
    if teacher:
        teacher.storage_bytes_used += size_bytes
    await db.flush()
    return MaterialOut.model_validate(material)


@router.get("/materials/{material_id}", response_model=MaterialOut)
async def get_material(material_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    material = await _get_material_with_access(material_id, user, db)
    return MaterialOut.model_validate(material)


@router.get("/materials/{material_id}/content", response_model=ContentOut)
async def get_content(material_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    material = await _get_material_with_access(material_id, user, db)
    if material.type in (MaterialType.board, MaterialType.pdf, MaterialType.image):
        if not material.storage_ref:
            raise HTTPException(status_code=404, detail={"error": {"code": "no_content", "message": "No content"}})
        return ContentOut(type=material.type.value, url=presigned_get_url(material.storage_ref))
    return ContentOut(type=material.type.value, config=material.config)


@router.patch("/materials/{material_id}", response_model=MaterialOut)
async def patch_material(
    material_id: int,
    data: MaterialPatchIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    material = await _get_material_with_access(material_id, user, db)
    space = await db.get(Space, material.space_id)
    can_edit = material.created_by == user.id or (space and space.teacher_id == user.id)
    if not can_edit:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Cannot edit this material"}})

    if data.title is not None:
        material.title = data.title
    if data.folder_id is not None:
        material.folder_id = data.folder_id
    if data.config is not None:
        material.config = data.config
    await db.flush()
    return MaterialOut.model_validate(material)


@router.post("/materials/{material_id}/duplicate", response_model=MaterialOut)
async def duplicate_material(
    material_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    material = await _get_material_with_access(material_id, user, db)
    space = await db.get(Space, material.space_id)
    storage_ref = None
    size_bytes = material.size_bytes
    if material.storage_ref:
        storage_ref = generate_storage_key("dup")
        copy_object(material.storage_ref, storage_ref)

    creator_role = CreatorRole.teacher if user.role == UserRole.teacher else CreatorRole.student
    dup = Material(
        space_id=material.space_id,
        folder_id=material.folder_id,
        type=material.type,
        title=f"{material.title} (копия)",
        created_by=user.id,
        created_by_role=creator_role,
        config=material.config.copy() if material.config else None,
        storage_ref=storage_ref,
        size_bytes=size_bytes,
    )
    db.add(dup)
    await db.flush()
    if space and size_bytes:
        teacher = await db.get(User, space.teacher_id)
        if teacher:
            teacher.storage_bytes_used += size_bytes
    return MaterialOut.model_validate(dup)


@router.delete("/materials/{material_id}")
async def delete_material(material_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    material = await _get_material_with_access(material_id, user, db)
    space = await db.get(Space, material.space_id)
    can_delete = material.created_by == user.id or (space and space.teacher_id == user.id)
    if not can_delete:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Cannot delete this material"}})

    if material.storage_ref:
        delete_object(material.storage_ref)
    if material.size_bytes and space:
        teacher = await db.get(User, space.teacher_id)
        if teacher:
            teacher.storage_bytes_used = max(0, teacher.storage_bytes_used - material.size_bytes)
    await db.delete(material)
    return {"ok": True}
