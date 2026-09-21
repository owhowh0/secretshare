import ssl
from collections.abc import AsyncIterator

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str, *, tls_ca_cert: str = "") -> AsyncEngine:
    connect_args: dict = {}
    if tls_ca_cert:
        ctx = ssl.create_default_context(cafile=tls_ca_cert)
        ctx.check_hostname = False  # internal Docker; CN=db, not the hostname
        connect_args["ssl"] = ctx
    return create_async_engine(database_url, pool_pre_ping=True, connect_args=connect_args)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def dispose_engine(engine: AsyncEngine) -> None:
    await engine.dispose()


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        )
    async with session_factory() as session:
        yield session
