"""PostgreSQL models and repository operations."""

from datetime import datetime
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    delete,
    func,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative model."""


class SentPatch(Base):
    """Stores processed patch versions."""

    __tablename__ = "sent_patches"

    version: Mapped[str] = mapped_column(primary_key=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DiscordUser(Base):
    """Stores discord user notification settings."""

    __tablename__ = "discord_users"

    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dm_enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    last_notified_patch: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    preferences: Mapped[list["ChampionPreference"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class ChampionPreference(Base):
    """Stores champion watch and ignore preferences per user."""

    __tablename__ = "champion_preferences"
    __table_args__ = (
        CheckConstraint("mode IN ('watch', 'ignore')", name="check_mode_valid"),
    )

    discord_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("discord_users.discord_id", ondelete="CASCADE"),
        primary_key=True,
    )
    champion_id: Mapped[str] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column()

    user: Mapped["DiscordUser"] = relationship(back_populates="preferences")


def create_engine_and_sessionmaker(
    database_url: str, pool_size: int = 5
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Creates an async engine and sessionmaker."""
    engine = create_async_engine(database_url, pool_size=pool_size)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    return engine, sessionmaker


async def init_schema(engine: AsyncEngine) -> None:
    """Creates database tables if they do not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def is_patch_sent(session: AsyncSession, version: str) -> bool:
    """Checks whether a patch version was already sent."""
    stmt = select(SentPatch.version).where(SentPatch.version == version)
    result = await session.scalar(stmt)
    return result is not None


async def mark_patch_sent(session: AsyncSession, version: str) -> bool:
    """Marks a patch as sent. Returns True if inserted, False if existed."""
    stmt = (
        pg_insert(SentPatch)
        .values(version=version)
        .on_conflict_do_nothing(index_elements=["version"])
        .returning(SentPatch.version)
    )
    result = await session.scalar(stmt)
    return result is not None


async def upsert_user(session: AsyncSession, discord_id: int) -> None:
    """Inserts user or re-enables DMs if user exists."""
    stmt = (
        pg_insert(DiscordUser)
        .values(discord_id=discord_id, dm_enabled=True)
        .on_conflict_do_update(
            index_elements=["discord_id"],
            set_={"dm_enabled": True},
        )
    )
    await session.execute(stmt)


async def set_preference(
    session: AsyncSession, discord_id: int, champion_id: str, mode: str
) -> None:
    """Inserts or updates a champion preference for user."""
    stmt = (
        pg_insert(ChampionPreference)
        .values(discord_id=discord_id, champion_id=champion_id, mode=mode)
        .on_conflict_do_update(
            index_elements=["discord_id", "champion_id"],
            set_={"mode": mode},
        )
    )
    await session.execute(stmt)


async def remove_preference(
    session: AsyncSession, discord_id: int, champion_id: str
) -> bool:
    """Removes a champion preference. Returns True if deleted."""
    stmt = (
        delete(ChampionPreference)
        .where(
            ChampionPreference.discord_id == discord_id,
            ChampionPreference.champion_id == champion_id,
        )
        .returning(ChampionPreference.champion_id)
    )
    result = await session.scalar(stmt)
    return result is not None


async def get_preferences(
    session: AsyncSession, discord_id: int
) -> tuple[set[str], set[str]]:
    """Returns watched and ignored champion sets for user."""
    stmt = select(ChampionPreference.champion_id, ChampionPreference.mode).where(
        ChampionPreference.discord_id == discord_id
    )
    rows = (await session.execute(stmt)).all()
    watched = {champ_id for champ_id, mode in rows if mode == "watch"}
    ignored = {champ_id for champ_id, mode in rows if mode == "ignore"}
    return watched, ignored


async def list_pending_users(session: AsyncSession, version: str) -> list[int]:
    """Returns users with enabled DMs awaiting notification for version."""
    stmt = (
        select(DiscordUser.discord_id)
        .where(
            DiscordUser.dm_enabled.is_(True),
            DiscordUser.last_notified_patch.is_distinct_from(version),
        )
        .order_by(DiscordUser.created_at)
    )
    result = await session.scalars(stmt)
    return list(result.all())


async def mark_user_notified(
    session: AsyncSession, discord_id: int, version: str
) -> None:
    """Updates user last notified patch version."""
    stmt = (
        update(DiscordUser)
        .where(DiscordUser.discord_id == discord_id)
        .values(last_notified_patch=version)
    )
    await session.execute(stmt)


async def disable_dm(session: AsyncSession, discord_id: int) -> None:
    """Disables direct message notifications for user."""
    stmt = (
        update(DiscordUser)
        .where(DiscordUser.discord_id == discord_id)
        .values(dm_enabled=False)
    )
    await session.execute(stmt)
