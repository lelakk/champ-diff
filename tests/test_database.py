"""Integration tests for database models and repository functions."""

import os
import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from services.database import (
    ChampionPreference,
    DiscordUser,
    SentPatch,
    disable_dm,
    get_preferences,
    init_schema,
    is_patch_sent,
    list_pending_users,
    mark_patch_sent,
    mark_user_notified,
    remove_preference,
    set_preference,
    upsert_user,
)

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is not set")


@pytest.fixture
async def engine():
    test_engine = create_async_engine(DATABASE_URL)
    await init_schema(test_engine)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def session(engine):
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session_factory = async_sessionmaker(bind=connection, expire_on_commit=False)
        async with session_factory() as test_session:
            yield test_session
        await transaction.rollback()


async def test_init_schema_is_idempotent(engine):
    await init_schema(engine)


async def test_mark_patch_sent_and_duplicate(session):
    assert await is_patch_sent(session, "14.1.1") is False
    assert await mark_patch_sent(session, "14.1.1") is True
    assert await is_patch_sent(session, "14.1.1") is True
    assert await mark_patch_sent(session, "14.1.1") is False


async def test_set_preference_upsert_watch_to_ignore(session):
    await upsert_user(session, 1001)

    await set_preference(session, 1001, "Yasuo", "watch")
    watched, ignored = await get_preferences(session, 1001)
    assert watched == {"Yasuo"}
    assert ignored == set()

    await set_preference(session, 1001, "Yasuo", "ignore")
    watched, ignored = await get_preferences(session, 1001)
    assert watched == set()
    assert ignored == {"Yasuo"}

    stmt = select(ChampionPreference).where(
        ChampionPreference.discord_id == 1001,
        ChampionPreference.champion_id == "Yasuo",
    )
    rows = (await session.scalars(stmt)).all()
    assert len(rows) == 1
    assert rows[0].mode == "ignore"


async def test_remove_preference(session):
    await upsert_user(session, 1002)
    await set_preference(session, 1002, "Zed", "watch")

    assert await remove_preference(session, 1002, "Zed") is True
    assert await remove_preference(session, 1002, "Zed") is False

    watched, ignored = await get_preferences(session, 1002)
    assert watched == set()
    assert ignored == set()


async def test_list_pending_users_lifecycle(session):
    await upsert_user(session, 2001)
    await upsert_user(session, 2002)

    pending = await list_pending_users(session, "14.2.1")
    assert 2001 in pending and 2002 in pending

    await mark_user_notified(session, 2001, "14.2.1")
    pending = await list_pending_users(session, "14.2.1")
    assert 2001 not in pending
    assert 2002 in pending

    await disable_dm(session, 2002)
    pending = await list_pending_users(session, "14.2.1")
    assert 2002 not in pending

    await upsert_user(session, 2002)
    pending = await list_pending_users(session, "14.2.1")
    assert 2002 in pending


async def test_user_cascade_deletes_preferences(session):
    await upsert_user(session, 3001)
    await set_preference(session, 3001, "Aatrox", "watch")

    await session.execute(delete(DiscordUser).where(DiscordUser.discord_id == 3001))

    watched, ignored = await get_preferences(session, 3001)
    assert watched == set()
    assert ignored == set()


async def test_invalid_preference_mode_raises_integrity_error(session):
    await upsert_user(session, 4001)

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await set_preference(session, 4001, "Ahri", "invalid")
