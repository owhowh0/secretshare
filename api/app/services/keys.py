import logging
from datetime import datetime, timezone

import sqlalchemy as sa
from app.db.models import DeviceKey, User
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("secretshare.keys")


class KeyService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_or_create_user(
        self,
        platform_user_id: str,
        platform: str = "keycloak",
        workspace_id: str | None = None,
    ) -> User:
        query = select(User).where(
            User.platform == platform,
            User.platform_user_id == platform_user_id,
        )
        result = await self._db.execute(query)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                platform=platform,
                platform_user_id=platform_user_id,
                workspace_id=workspace_id,
            )
            self._db.add(user)
            await self._db.flush()
            logger.info("Created new user %s on platform %s", user.id, platform)

        return user

    async def register_device_key(
        self,
        user: User,
        public_key: str,
        platform: str,
        label: str | None = None,
    ) -> DeviceKey:
        now = datetime.now(timezone.utc)
        await self._db.execute(
            update(DeviceKey)
            .where(
                DeviceKey.user_id == user.id,
                DeviceKey.platform == platform,
                DeviceKey.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

        device_key = DeviceKey(
            user_id=user.id,
            platform=platform,
            public_key=public_key,
            label=label,
        )
        self._db.add(device_key)
        await self._db.commit()
        await self._db.refresh(device_key)
        return device_key

    async def get_active_keys_for_user(self, platform_user_id: str) -> list[DeviceKey]:
        query = (
            select(DeviceKey)
            .join(User, DeviceKey.user_id == User.id)
            .where(
                (User.platform_user_id == platform_user_id)
                | (User.id.cast(sa.Text) == platform_user_id),
                DeviceKey.revoked_at.is_(None),
            )
        )
        result = await self._db.execute(query)
        return list(result.scalars().all())
