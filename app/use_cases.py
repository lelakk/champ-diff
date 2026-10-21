"""Use cases for patch comparison, preference filtering, and DM dispatch."""

import asyncio
from collections.abc import Iterable
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ChampionDiffResult, ChampionEntry
from services.database import (
    disable_dm,
    get_preferences,
    is_patch_sent,
    list_pending_users,
    mark_patch_sent,
    mark_user_notified,
)
from services.ddragon_client import get_champion_data, get_latest_and_previous_patch
from services.diff_service import get_champion_diff
from services.notifier import DMQueue, build_embeds

logger = logging.getLogger(__name__)


def compare_patches(latest_patch: str, previous_patch: str) -> ChampionDiffResult:
    """Compares two specific patch versions and returns the champion stat differences.

    Args:
        latest_patch: Latest patch version string.
        previous_patch: Previous patch version string.

    Returns:
        A ChampionDiffResult object containing the champion changes and new champions.
    """
    latest_champions = get_champion_data(latest_patch)
    previous_champions = get_champion_data(previous_patch)

    if not latest_champions or not previous_champions:
        raise RuntimeError("Failed to fetch champion data for patch versions")

    return get_champion_diff(latest_champions, previous_champions)


def compare_last_patch() -> ChampionDiffResult:
    """Compares the latest and previous patch versions and returns the differences.

    Returns:
        A ChampionDiffResult object containing the champion changes and new champions.
    """
    patches = get_latest_and_previous_patch()
    if not patches:
        raise RuntimeError("Failed to fetch patch versions")

    latest_patch, previous_patch = patches
    logger.info("Latest patch: %s", latest_patch)
    logger.info("Previous patch: %s", previous_patch)

    return compare_patches(latest_patch, previous_patch)


def resolve_champion(
    query: str, champions: dict[str, ChampionEntry]
) -> str | None:
    """Resolves a user query to a canonical DataDragon champion ID case-insensitively.

    Args:
        query: Champion ID or display name provided by the user.
        champions: Dictionary mapping champion IDs to their ChampionEntry models.

    Returns:
        Canonical DataDragon champion ID if matched, or None if not found.
    """
    normalized_query = query.strip().lower()
    if not normalized_query:
        return None

    for champ_key, entry in champions.items():
        champion_id = entry.id or champ_key
        if normalized_query == champ_key.lower() or normalized_query == champion_id.lower():
            return champion_id
        if entry.name and normalized_query == entry.name.lower():
            return champion_id

    return None


def filter_diff(
    diff: ChampionDiffResult,
    watched: Iterable[str],
    ignored: Iterable[str],
) -> ChampionDiffResult:
    """Filters champion stat changes and new champions based on user preferences.

    Args:
        diff: Full calculated patch difference result.
        watched: Champion IDs explicitly watched by the user.
        ignored: Champion IDs explicitly ignored by the user.

    Returns:
        A filtered ChampionDiffResult containing only allowed champions.
    """
    watched_set = set(watched)
    ignored_set = set(ignored)

    def is_allowed(champion_id: str) -> bool:
        if champion_id in ignored_set:
            return False
        if watched_set and champion_id not in watched_set:
            return False
        return True

    filtered_changes = {
        champion_id: stats
        for champion_id, stats in diff.champion_changes.items()
        if is_allowed(champion_id)
    }
    filtered_new = [
        champion_id
        for champion_id in diff.new_champions
        if is_allowed(champion_id)
    ]

    return ChampionDiffResult(
        champion_changes=filtered_changes,
        new_champions=filtered_new,
    )


async def dispatch_patch(
    sessionmaker: async_sessionmaker[AsyncSession],
    queue: DMQueue,
) -> None:
    """Fetches the latest patch diff, filters it per user, and dispatches DMs via queue.

    Args:
        sessionmaker: Factory for creating async database sessions.
        queue: Rate-limited DM queue used to send embeds to users.
    """
    patches = await asyncio.to_thread(get_latest_and_previous_patch)
    if not patches:
        raise RuntimeError("Failed to fetch patch versions")

    latest_patch, previous_patch = patches

    async with sessionmaker() as session:
        if await is_patch_sent(session, latest_patch):
            logger.info("Patch %s already sent", latest_patch)
            return

    diff = await asyncio.to_thread(compare_patches, latest_patch, previous_patch)

    async def on_success(user_id: int) -> None:
        async with sessionmaker() as callback_session:
            await mark_user_notified(callback_session, user_id, latest_patch)
            await callback_session.commit()

    async def on_forbidden(user_id: int) -> None:
        async with sessionmaker() as callback_session:
            await disable_dm(callback_session, user_id)
            await callback_session.commit()

    queue._on_success = on_success
    queue._on_forbidden = on_forbidden

    async with sessionmaker() as session:
        pending_users = await list_pending_users(session, latest_patch)
        for user_id in pending_users:
            watched, ignored = await get_preferences(session, user_id)
            user_diff = filter_diff(diff, watched, ignored)
            embeds = build_embeds(user_diff, latest_patch, previous_patch)
            if not embeds:
                await mark_user_notified(session, user_id, latest_patch)
                continue
            await queue.enqueue(user_id, embeds)
        await session.commit()

    await queue.join()

    async with sessionmaker() as session:
        await mark_patch_sent(session, latest_patch)
        await session.commit()
