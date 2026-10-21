"""Unit tests for Discord slash command handlers, autocomplete, and patch check loop."""

import pytest

import app.main as main_module
from app.models import ChampionEntry


@pytest.fixture
def mock_db_session(mocker):
    """Configures a mocked async_sessionmaker and populates the champion cache."""
    session = mocker.AsyncMock()
    context_manager = mocker.AsyncMock()
    context_manager.__aenter__.return_value = session
    context_manager.__aexit__.return_value = None
    sessionmaker = mocker.MagicMock(return_value=context_manager)

    mocker.patch.object(main_module, "session_factory", sessionmaker)
    mocker.patch.dict(
        main_module.champions_cache,
        {
            "Yasuo": ChampionEntry(id="Yasuo", name="Yasuo"),
            "MonkeyKing": ChampionEntry(id="MonkeyKing", name="Wukong"),
        },
        clear=True,
    )
    return session


@pytest.fixture
def mock_repo(mocker):
    """Mocks database repository functions used by slash command handlers."""
    return {
        "upsert_user": mocker.patch("app.main.upsert_user", new=mocker.AsyncMock()),
        "set_preference": mocker.patch(
            "app.main.set_preference", new=mocker.AsyncMock()
        ),
        "remove_preference": mocker.patch(
            "app.main.remove_preference", new=mocker.AsyncMock(return_value=False)
        ),
    }


def _make_interaction(mocker, user_id: int = 12345):
    """Creates a mocked Discord Interaction with an AsyncMock response."""
    interaction = mocker.AsyncMock()
    interaction.user.id = user_id
    return interaction


async def test_watch_command_sets_preference_and_replies_ephemeral(
    mocker, mock_db_session, mock_repo
):
    """Should upsert user, set watch preference for Yasuo, and send an ephemeral reply."""
    interaction = _make_interaction(mocker, user_id=5001)

    await main_module.watch_command(interaction, "yasuo")

    mock_repo["upsert_user"].assert_awaited_once_with(mock_db_session, 5001)
    mock_repo["set_preference"].assert_awaited_once_with(
        mock_db_session, 5001, "Yasuo", "watch"
    )
    interaction.response.send_message.assert_awaited_once_with(
        "Preference set: Yasuo (watch).", ephemeral=True
    )


async def test_ignore_command_unknown_champion_skips_db_and_returns_error(
    mocker, mock_db_session, mock_repo
):
    """If champion is unknown, should not call database and should send an ephemeral error."""
    assert mock_db_session is not None
    interaction = _make_interaction(mocker, user_id=5002)

    await main_module.ignore_command(interaction, "xyz")

    mock_repo["upsert_user"].assert_not_awaited()
    mock_repo["set_preference"].assert_not_awaited()
    interaction.response.send_message.assert_awaited_once_with(
        "Unknown champion: xyz.", ephemeral=True
    )


async def test_unset_command_removes_preference_and_handles_missing_entry(
    mocker, mock_db_session, mock_repo
):
    """Should call remove_preference and inform the user when no preference existed."""
    interaction = _make_interaction(mocker, user_id=5003)

    await main_module.unset_command(interaction, "yasuo")

    mock_repo["remove_preference"].assert_awaited_once_with(
        mock_db_session, 5003, "Yasuo"
    )
    interaction.response.send_message.assert_awaited_once_with(
        "No preference found for Yasuo.", ephemeral=True
    )


async def test_subscribe_command_upserts_user_without_setting_preference(
    mocker, mock_db_session, mock_repo
):
    """Should call upsert_user without calling set_preference and reply ephemerally."""
    interaction = _make_interaction(mocker, user_id=5004)

    await main_module.subscribe_command(interaction)

    mock_repo["upsert_user"].assert_awaited_once_with(mock_db_session, 5004)
    mock_repo["set_preference"].assert_not_awaited()
    interaction.response.send_message.assert_awaited_once_with(
        "Subscribed to patch diff notifications.", ephemeral=True
    )


async def test_run_patch_check_logs_exception_without_raising(mocker):
    """If dispatch_patch raises an exception, should log the error and not crash the loop."""
    mocker.patch("app.main.refresh_champions_cache")
    mocker.patch(
        "app.main.dispatch_patch",
        new=mocker.AsyncMock(side_effect=RuntimeError("Network failure")),
    )
    mock_logger_error = mocker.patch.object(main_module.logger, "error")

    await main_module.run_patch_check(mocker.MagicMock(), mocker.MagicMock())

    mock_logger_error.assert_called_once()


async def test_champion_autocomplete_returns_at_most_25_choices(mocker):
    """Should return at most 25 matching champion choices for autocomplete."""
    many_champions = {
        f"Champ{i:02d}": ChampionEntry(id=f"Champ{i:02d}", name=f"Champion {i:02d}")
        for i in range(40)
    }
    mocker.patch.dict(main_module.champions_cache, many_champions, clear=True)
    interaction = _make_interaction(mocker)

    choices = await main_module.champion_autocomplete(interaction, "champ")

    assert len(choices) == 25
