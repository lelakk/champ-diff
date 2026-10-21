"""Discord embed builder and rate-limited direct message queue."""

import asyncio
from collections.abc import Awaitable, Callable
import inspect
import logging
import os
from typing import Any

import discord

from app.models import ChampionDiffResult, ChampionDiffStat

logger = logging.getLogger(__name__)

MAX_FIELD_VALUE_LENGTH = 1024
MAX_FIELDS_PER_EMBED = 25
MAX_EMBEDS_PER_MESSAGE = 10
MAX_TOTAL_EMBED_CHARS = 6000
DEFAULT_RETRY_AFTER_SECONDS = 5.0
MAX_SERVER_ERROR_RETRIES = 3
HEXTECH_GOLD_COLOR = 0xC8AA6E
ANSI_GREEN = "\x1b[32m"
ANSI_RED = "\x1b[31m"
ANSI_RESET = "\x1b[0m"
CODE_BLOCK_OVERHEAD = len("```ansi\n\n```")
EMBED_DESCRIPTION = "Changes:"


def _format_number(value: float | int) -> str:
    """Formats a numeric stat value or delta, stripping trailing .0 on integers.

    Args:
        value: Numeric statistic value or calculated delta.

    Returns:
        Formatted number string rounded to at most 4 decimal places.
    """
    rounded = round(value, 4)
    if isinstance(rounded, float) and rounded.is_integer():
        return str(int(rounded))
    return str(rounded)


def _stat_delta(stat: ChampionDiffStat) -> float:
    """Calculates the rounded numeric difference for a changed statistic.

    Args:
        stat: Object holding the old and new statistic values.

    Returns:
        Rounded numeric delta, or 0.0 if values are non-numeric.
    """
    if isinstance(stat.old, (int, float)) and isinstance(stat.new, (int, float)):
        return round(stat.new - stat.old, 4)
    return 0.0


def _champion_sort_priority(stat_changes: dict[str, ChampionDiffStat]) -> int:
    """Determines sort priority for a champion so buffs appear before nerfs.

    Args:
        stat_changes: Mapping of changed stat names to their diff objects.

    Returns:
        0 for pure buffs, 1 for mixed changes, 2 for pure nerfs.
    """
    deltas = [_stat_delta(stat) for stat in stat_changes.values()]
    has_buff = any(delta > 0 for delta in deltas)
    has_nerf = any(delta < 0 for delta in deltas)
    if has_buff and not has_nerf:
        return 0
    if has_buff and has_nerf:
        return 1
    return 2


def _format_stat_line(stat_name: str, stat: ChampionDiffStat) -> str:
    """Formats a single changed champion statistic line with ANSI color after the colon.

    Args:
        stat_name: Name of the statistic (e.g., 'hp', 'armor').
        stat: Object holding the old and new statistic values.

    Returns:
        Formatted string with white stat name and green/red value change.
    """
    if isinstance(stat.old, (int, float)) and isinstance(stat.new, (int, float)):
        delta = _stat_delta(stat)
        old_str = _format_number(stat.old)
        new_str = _format_number(stat.new)
        delta_str = _format_number(delta)
        if delta > 0:
            return f"{stat_name}: {ANSI_GREEN}{old_str} → {new_str} (▲ +{delta_str}){ANSI_RESET}"
        if delta < 0:
            return f"{stat_name}: {ANSI_RED}{old_str} → {new_str} (▼ {delta_str}){ANSI_RESET}"
    return f"{stat_name}: {stat.old} → {stat.new}"


def _split_lines_to_chunks(lines: list[str], max_length: int) -> list[str]:
    """Splits a list of text lines into newline-joined chunks within max_length.

    Args:
        lines: Individual text lines to join.
        max_length: Maximum character length allowed per chunk.

    Returns:
        List of newline-joined strings, each at most max_length characters long.
    """
    chunks: list[str] = []
    current_lines: list[str] = []
    current_length = 0

    for line in lines:
        trimmed_line = line[:max_length]
        added_length = len(trimmed_line) if not current_lines else len(trimmed_line) + 1
        if current_lines and current_length + added_length > max_length:
            chunks.append("\n".join(current_lines))
            current_lines = [trimmed_line]
            current_length = len(trimmed_line)
        else:
            current_lines.append(trimmed_line)
            current_length += added_length

    if current_lines:
        chunks.append("\n".join(current_lines))

    return chunks


def build_embeds(
    diff: ChampionDiffResult,
    latest: str,
    previous: str,
    champion_names: dict[str, str] | None = None,
) -> list[discord.Embed]:
    """Builds Discord embeds representing champion stat changes and new champions.

    Args:
        diff: Calculated champion stat changes and new champions.
        latest: Latest patch version string.
        previous: Previous patch version string.
        champion_names: Optional mapping from internal champion IDs to display names.

    Returns:
        A list of Discord embeds respecting Discord size and count limits.
    """
    fields: list[tuple[str, str]] = []
    max_chunk_len = MAX_FIELD_VALUE_LENGTH - CODE_BLOCK_OVERHEAD

    sorted_champions = sorted(
        diff.champion_changes.items(),
        key=lambda item: _champion_sort_priority(item[1]),
    )

    for champion_id, stat_changes in sorted_champions:
        if not stat_changes:
            continue
        display_name = (
            champion_names.get(champion_id, champion_id)
            if champion_names
            else champion_id
        )
        sorted_stats = sorted(
            stat_changes.items(),
            key=lambda item: 0 if _stat_delta(item[1]) > 0 else 1,
        )
        lines = [
            _format_stat_line(stat_name, stat_diff)
            for stat_name, stat_diff in sorted_stats
        ]
        for chunk in _split_lines_to_chunks(lines, max_chunk_len):
            fields.append((display_name, f"```ansi\n{chunk}\n```"))

    if diff.new_champions:
        new_names = [
            champion_names.get(champ_id, champ_id) if champion_names else champ_id
            for champ_id in diff.new_champions
        ]
        new_champions_text = ", ".join(new_names)
        for chunk in _split_lines_to_chunks(
            [new_champions_text], MAX_FIELD_VALUE_LENGTH
        ):
            fields.append(("New champions", chunk))

    if not fields:
        return []

    title_text = f"Patch {previous} → {latest}"
    embed_overhead = len(title_text) + len(EMBED_DESCRIPTION)
    embeds: list[discord.Embed] = []
    total_chars = 0

    for name, value in fields:
        field_chars = len(name) + len(value)
        needs_new_embed = (
            not embeds or len(embeds[-1].fields) >= MAX_FIELDS_PER_EMBED
        )

        if needs_new_embed:
            if len(embeds) >= MAX_EMBEDS_PER_MESSAGE:
                break
            if total_chars + embed_overhead + field_chars > MAX_TOTAL_EMBED_CHARS:
                break
            embed = discord.Embed(
                title=title_text,
                description=EMBED_DESCRIPTION,
                color=HEXTECH_GOLD_COLOR,
            )
            embeds.append(embed)
            total_chars += embed_overhead
        elif total_chars + field_chars > MAX_TOTAL_EMBED_CHARS:
            break

        embeds[-1].add_field(name=name, value=value, inline=False)
        total_chars += field_chars

    return embeds


def _extract_retry_after(exc: discord.HTTPException) -> float:
    """Extracts the retry delay in seconds from a 429 HTTPException response.

    Args:
        exc: The Discord HTTPException raised on status 429.

    Returns:
        Number of seconds to wait before retrying, defaulting to 5.0 seconds.
    """
    headers = getattr(exc.response, "headers", None) or {}
    raw_value = headers.get("Retry-After") or headers.get("retry-after")
    if raw_value is None:
        raw_value = getattr(exc, "retry_after", None)
    if raw_value is not None:
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            pass
    return DEFAULT_RETRY_AFTER_SECONDS


async def _invoke_callback(
    callback: Callable[[int], Any] | None, user_id: int
) -> None:
    """Invokes a synchronous or asynchronous user callback if provided.

    Args:
        callback: Optional callable accepting a Discord user ID.
        user_id: The Discord user ID to pass to the callback.
    """
    if callback is None:
        return
    result = callback(user_id)
    if inspect.isawaitable(result):
        await result


class DMQueue:
    """Asynchronous sequential queue for sending Discord direct messages."""

    def __init__(
        self,
        delay: float | None = None,
        on_success: Callable[[int], Any] | None = None,
        on_forbidden: Callable[[int], Any] | None = None,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        fetch_user: Callable[[int], Awaitable[Any]] | None = None,
    ) -> None:
        """Initializes the direct message queue.

        Args:
            delay: Delay in seconds between consecutive messages.
            on_success: Callback invoked with user_id after successful delivery.
            on_forbidden: Callback invoked with user_id when DMs are blocked.
            sleep: Async sleep function used for rate limiting and backoff.
            fetch_user: Optional async callable resolving a user ID to a user object.
        """
        if delay is None:
            delay = float(os.getenv("DM_DELAY_SECONDS", "1.0"))
        self._delay = delay
        self._on_success = on_success
        self._on_forbidden = on_forbidden
        self._sleep = sleep
        self._fetch_user = fetch_user
        self._queue: asyncio.Queue[tuple[Any, list[discord.Embed]]] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None

    async def enqueue(self, user: Any, embeds: list[discord.Embed]) -> None:
        """Adds a direct message delivery task to the queue.

        Args:
            user: Discord user object or integer user ID.
            embeds: List of Discord embeds to send.
        """
        if not embeds:
            return
        self._queue.put_nowait((user, embeds))
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

    async def join(self) -> None:
        """Waits until all queued direct messages have been processed."""
        await self._queue.join()
        if self._worker_task is not None and not self._worker_task.done():
            await self._worker_task

    async def stop(self) -> None:
        """Cancels the background worker task if it is running."""
        if self._worker_task is not None and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def _worker(self) -> None:
        """Processes queued messages sequentially with a fixed delay between them."""
        while not self._queue.empty():
            user, embeds = await self._queue.get()
            try:
                await self._send_with_retry(user, embeds)
            finally:
                self._queue.task_done()
            if not self._queue.empty():
                await self._sleep(self._delay)

    async def _send_with_retry(
        self, user: Any, embeds: list[discord.Embed]
    ) -> None:
        """Sends embeds to a user, handling rate limits, Forbidden, and 5xx errors.

        Args:
            user: Discord user object or integer user ID.
            embeds: List of Discord embeds to send.
        """
        user_id = user if isinstance(user, int) else getattr(user, "id", 0)
        target = user
        server_errors = 0

        while True:
            try:
                if isinstance(target, int):
                    if self._fetch_user is None:
                        raise RuntimeError("fetch_user callback is required for user IDs")
                    target = await self._fetch_user(target)
                await target.send(embeds=embeds)
                await _invoke_callback(self._on_success, user_id)
                return
            except discord.RateLimited as exc:
                await self._sleep(exc.retry_after)
            except discord.Forbidden:
                logger.warning("Cannot send DM to user %s: forbidden", user_id)
                await _invoke_callback(self._on_forbidden, user_id)
                return
            except discord.HTTPException as exc:
                if exc.status == 429:
                    await self._sleep(_extract_retry_after(exc))
                    continue
                if 500 <= exc.status < 600:
                    server_errors += 1
                    if server_errors >= MAX_SERVER_ERROR_RETRIES:
                        logger.error(
                            "Dropping DM to user %s after %d server errors",
                            user_id,
                            server_errors,
                        )
                        return
                    await self._sleep(float(2 ** (server_errors - 1)))
                    continue
                logger.error("Failed to send DM to user %s: %s", user_id, exc)
                return
