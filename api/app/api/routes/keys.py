from app.core.auth import get_current_user
from app.db.session import get_db
from app.schemas.keys import DeviceKeyItem, KeyRegisterRequest, UserPublicKeysResponse
from app.services.keys import KeyService
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/keys", tags=["Keys"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=DeviceKeyItem,
)
async def register_public_key(
    payload: KeyRegisterRequest,
    claims: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeviceKeyItem:
    platform_user_id = claims.get("preferred_username") or claims.get("sub")
    if not platform_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated token missing user identifier.",
        )

    service = KeyService(db)
    user = await service.get_or_create_user(
        platform_user_id=platform_user_id,
        platform=payload.platform,
    )

    device_key = await service.register_device_key(
        user=user,
        public_key=payload.public_key,
        platform=payload.platform,
        label=payload.label,
    )

    return DeviceKeyItem(
        device_id=device_key.id,
        platform=device_key.platform,
        public_key=device_key.public_key,
        label=device_key.label,
        created_at=device_key.created_at,
    )


@router.get(
    "/{user_id}",
    response_model=UserPublicKeysResponse,
)
async def get_user_public_keys(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> UserPublicKeysResponse:
    service = KeyService(db)
    keys = await service.get_active_keys_for_user(user_id)
    if not keys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active device keys found for recipient '{user_id}'.",
        )

    return UserPublicKeysResponse(
        user_id=user_id,
        keys=[
            DeviceKeyItem(
                device_id=k.id,
                platform=k.platform,
                public_key=k.public_key,
                label=k.label,
                created_at=k.created_at,
            )
            for k in keys
        ],
    )
