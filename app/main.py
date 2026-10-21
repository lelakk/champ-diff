"""Main entry point for the Discord bot and slash command handlers."""

import asyncio
import logging
import os
import signal

import discord
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import ChampionEntry
from app.use_cases import dispatch_patch, resolve_champion
from services.database import (
    create_engine_and_sessionmaker,
    init_schema,
    remove_preference,
    set_preference,
    upsert_user,
)
from services.ddragon_client import get_champion_data, get_latest_and_previous_patch
from services.notifier import DMQueue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

CHECK_INTERVAL_MINUTES = float(os.getenv("CHECK_INTERVAL_MINUTES", "30"))

session_factory: async_sessionmaker[AsyncSession] | None = None
champions_cache: dict[str, ChampionEntry] = {}


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Returns the initialized database session factory or raises RuntimeError."""
    if session_factory is None:
        raise RuntimeError("Database session factory is not initialized")
    return session_factory


async def _reply_ephemeral(interaction: discord.Interaction, message: str) -> None:
    """Sends an ephemeral response message to a Discord interaction.

    Args:
        interaction: Discord interaction to respond to.
        message: Text content of the ephemeral response.
    """
    await interaction.response.send_message(message, ephemeral=True)


def refresh_champions_cache() -> None:
    """Fetches the latest champion dataset from DataDragon into memory cache."""
    patches = get_latest_and_previous_patch()
    if not patches:
        return

    latest_patch, _ = patches
    champions = get_champion_data(latest_patch)
    if champions:
        champions_cache.clear()
        champions_cache.update(champions)


async def _resolve_champion_or_reply(
    interaction: discord.Interaction, champion: str
) -> str | None:
    """Resolves a champion query or replies with an ephemeral error if not found.

    Args:
        interaction: Discord interaction triggered by the command.
        champion: Champion name or ID provided by the user.

    Returns:
        Canonical DataDragon champion ID, or None if the champion does not exist.
    """
    if not champions_cache:
        await asyncio.to_thread(refresh_champions_cache)

    champion_id = resolve_champion(champion, champions_cache)
    if champion_id is None:
        await _reply_ephemeral(interaction, f"Unknown champion: {champion}.")
    return champion_id


async def champion_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Returns up to 25 matching champion choices for slash command autocomplete.

    Args:
        interaction: Discord interaction context.
        current: Current text typed by the user.

    Returns:
        List of up to 25 matching app_commands.Choice items.
    """
    del interaction
    query = current.strip().lower()
    choices: list[app_commands.Choice[str]] = []

    for champ_key, entry in champions_cache.items():
        champion_id = entry.id or champ_key
        display_name = entry.name or champion_id
        if not query or query in champion_id.lower() or query in display_name.lower():
            choices.append(app_commands.Choice(name=display_name, value=champion_id))
        if len(choices) >= 25:
            break

    return choices


async def _set_user_preference(
    interaction: discord.Interaction, champion: str, mode: str
) -> None:
    """Resolves a champion query and saves the user preference in the database.

    Args:
        interaction: Discord interaction triggered by the slash command.
        champion: Champion name or ID provided by the user.
        mode: Preference mode ('watch' or 'ignore').
    """
    champion_id = await _resolve_champion_or_reply(interaction, champion)
    if champion_id is None:
        return

    factory = _get_session_factory()
    async with factory() as session:
        await upsert_user(session, interaction.user.id)
        await set_preference(session, interaction.user.id, champion_id, mode)
        await session.commit()

    await _reply_ephemeral(interaction, f"Preference set: {champion_id} ({mode}).")


async def watch_command(interaction: discord.Interaction, champion: str) -> None:
    """Adds a champion to the user's watch list.

    Args:
        interaction: Discord interaction triggered by the command.
        champion: Champion name or ID to watch.
    """
    await _set_user_preference(interaction, champion, "watch")


async def ignore_command(interaction: discord.Interaction, champion: str) -> None:
    """Adds a champion to the user's ignore list.

    Args:
        interaction: Discord interaction triggered by the command.
        champion: Champion name or ID to ignore.
    """
    await _set_user_preference(interaction, champion, "ignore")


async def unset_command(interaction: discord.Interaction, champion: str) -> None:
    """Removes a champion preference for the calling user.

    Args:
        interaction: Discord interaction triggered by the command.
        champion: Champion name or ID to remove from preferences.
    """
    champion_id = await _resolve_champion_or_reply(interaction, champion)
    if champion_id is None:
        return

    factory = _get_session_factory()
    async with factory() as session:
        removed = await remove_preference(session, interaction.user.id, champion_id)
        await session.commit()

    if not removed:
        await _reply_ephemeral(interaction, f"No preference found for {champion_id}.")
        return

    await _reply_ephemeral(interaction, f"Removed preference for {champion_id}.")


async def subscribe_command(interaction: discord.Interaction) -> None:
    """Subscribes the user to patch diff notifications and enables DMs.

    Args:
        interaction: Discord interaction triggered by the command.
    """
    factory = _get_session_factory()
    async with factory() as session:
        await upsert_user(session, interaction.user.id)
        await session.commit()

    await _reply_ephemeral(interaction, "Subscribed to patch diff notifications.")


async def run_patch_check(
    sessionmaker: async_sessionmaker[AsyncSession], queue: DMQueue
) -> None:
    """Refreshes the champion cache and dispatches the latest patch diff safely.

    Args:
        sessionmaker: Factory for creating async database sessions.
        queue: Rate-limited DM queue for sending embeds.
    """
    try:
        await asyncio.to_thread(refresh_champions_cache)
        await dispatch_patch(sessionmaker, queue)
    except Exception as error:
        logger.error("Error during periodic patch check: %s", error)


class ChampDiffBot(commands.Bot):
    """Discord bot managing slash commands and periodic patch diff checks."""

    def __init__(
        self,
        engine: AsyncEngine,
        sessionmaker: async_sessionmaker[AsyncSession],
        guild_id: str | None = None,
    ) -> None:
        """Initializes the bot instance, DM queue, and slash commands.

        Args:
            engine: Async SQLAlchemy database engine.
            sessionmaker: Factory for creating async database sessions.
            guild_id: Optional Discord guild ID for instant command synchronization.
        """
        super().__init__(
            command_prefix="!",
            intents=discord.Intents.default(),
            max_ratelimit_timeout=30.0,
        )
        self.engine = engine
        self.sessionmaker = sessionmaker
        self.guild_id = guild_id
        self.dm_queue = DMQueue(fetch_user=self.fetch_user)
        self._register_commands()

    def _register_commands(self) -> None:
        """Registers slash commands and autocomplete callbacks on the command tree."""
        champion_commands = [
            ("watch", "Watch stat changes for a champion", watch_command),
            ("ignore", "Ignore stat changes for a champion", ignore_command),
            ("unset", "Remove preference for a champion", unset_command),
        ]
        for name, description, callback in champion_commands:
            command = self.tree.command(name=name, description=description)(callback)
            command.autocomplete("champion")(champion_autocomplete)

        self.tree.command(
            name="subscribe",
            description="Subscribe to patch diff DM notifications",
        )(subscribe_command)

    async def setup_hook(self) -> None:
        """Initializes database schema, syncs slash commands, and starts the loop."""
        await init_schema(self.engine)

        if self.guild_id:
            guild = discord.Object(id=int(self.guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

        self.patch_check_loop.start()

    @tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
    async def patch_check_loop(self) -> None:
        """Periodic background task that checks for new patches and sends DMs."""
        await run_patch_check(self.sessionmaker, self.dm_queue)

    @patch_check_loop.before_loop
    async def before_patch_check_loop(self) -> None:
        """Waits until the bot is ready before running the first patch check."""
        await self.wait_until_ready()


async def run_bot() -> None:
    """Configures database, signal handlers, and runs the Discord bot."""
    global session_factory

    database_url = os.getenv("DATABASE_URL")
    token = os.getenv("DISCORD_BOT_TOKEN")
    guild_id = os.getenv("DISCORD_GUILD_ID") or None

    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN environment variable is required")

    engine, sessionmaker = create_engine_and_sessionmaker(database_url)
    session_factory = sessionmaker
    bot = ChampDiffBot(engine=engine, sessionmaker=sessionmaker, guild_id=guild_id)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.close()))
        except NotImplementedError:
            pass

    try:
        await bot.start(token)
    finally:
        if not bot.is_closed():
            await bot.close()
        await bot.dm_queue.stop()
        await engine.dispose()


def main() -> None:
    """Runs the asynchronous Discord bot entry point."""
    try:
        asyncio.run(run_bot())
    except (RuntimeError, KeyboardInterrupt) as error:
        logger.error("Application stopped: %s", error)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
