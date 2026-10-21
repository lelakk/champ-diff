"""Unit tests for end-to-end patch comparison, filtering, and dispatch use cases."""

import pytest

from app.models import ChampionDiffResult, ChampionDiffStat, ChampionEntry
from app.use_cases import (
    compare_last_patch,
    dispatch_patch,
    filter_diff,
    resolve_champion,
)

GET_PATCHES_FUNCTION = "app.use_cases.get_latest_and_previous_patch"
GET_CHAMPION_DATA_FUNCTION = "app.use_cases.get_champion_data"
GET_CHAMPION_DIFF_FUNCTION = "app.use_cases.get_champion_diff"
IS_PATCH_SENT_FUNCTION = "app.use_cases.is_patch_sent"
LIST_PENDING_USERS_FUNCTION = "app.use_cases.list_pending_users"
GET_PREFERENCES_FUNCTION = "app.use_cases.get_preferences"
MARK_USER_NOTIFIED_FUNCTION = "app.use_cases.mark_user_notified"
MARK_PATCH_SENT_FUNCTION = "app.use_cases.mark_patch_sent"


def _make_sessionmaker(mocker):
    """Creates a mocked async_sessionmaker yielding an AsyncMock session."""
    session = mocker.AsyncMock()
    context_manager = mocker.AsyncMock()
    context_manager.__aenter__.return_value = session
    context_manager.__aexit__.return_value = None
    sessionmaker = mocker.MagicMock(return_value=context_manager)
    return sessionmaker, session


def test_compare_last_patch_success(mocker):
    """If all dependencies return valid data, should return computed diff output."""
    mocker.patch(GET_PATCHES_FUNCTION, return_value=("10.0.0", "9.9.9"))

    mock_get_champion_data = mocker.patch(
        GET_CHAMPION_DATA_FUNCTION,
        side_effect=[{"Garen": ...}, {"Garen": ..., "Yasuo": ...}]
    )

    expected_diff_result = ChampionDiffResult(
        champion_changes={"Garen": {"hp": ChampionDiffStat(new=1000, old=900)}},
        new_champions=["Yasuo"]
    )

    mock_get_champion_diff = mocker.patch(
        GET_CHAMPION_DIFF_FUNCTION,
        return_value=expected_diff_result
    )

    result = compare_last_patch()

    assert result == expected_diff_result
    assert mock_get_champion_data.call_count == 2
    assert mock_get_champion_diff.call_count == 1


def test_compare_last_patch_failed_fetching_versions(mocker):
    """If patch versions fetch fails, should raise RuntimeError."""
    mocker.patch(GET_PATCHES_FUNCTION, return_value=None)

    with pytest.raises(RuntimeError, match="Failed to fetch patch versions"):
        compare_last_patch()


def test_compare_last_patch_empty_champion_dictionaries(mocker):
    """If champion data is empty for both patches, should raise RuntimeError."""
    mocker.patch(GET_PATCHES_FUNCTION, return_value=("10.0.0", "9.9.9"))

    mock_get_champion_data = mocker.patch(GET_CHAMPION_DATA_FUNCTION, side_effect=[{}, {}])

    with pytest.raises(RuntimeError, match="Failed to fetch champion data"):
        compare_last_patch()
    assert mock_get_champion_data.call_count == 2


def test_compare_last_patch_failed_fetching_champion_data(mocker):
    """If one champion data fetch fails, should raise RuntimeError."""
    mocker.patch(GET_PATCHES_FUNCTION, return_value=("10.0.0", "9.9.9"))

    mock_get_champion_data = mocker.patch(
        GET_CHAMPION_DATA_FUNCTION,
        side_effect=[{"Garen": ...}, None]
    )

    with pytest.raises(RuntimeError, match="Failed to fetch champion data"):
        compare_last_patch()
    assert mock_get_champion_data.call_count == 2


def test_compare_last_patch_calls_get_champion_data_in_patch_order(mocker):
    """Should fetch champion data first for latest patch, then previous patch."""
    mocker.patch(GET_PATCHES_FUNCTION, return_value=("10.0.0", "9.9.9"))

    mock_get_champion_data = mocker.patch(
        GET_CHAMPION_DATA_FUNCTION,
        side_effect=[{"Garen": ...}, {"Garen": ...}],
    )
    mocker.patch(GET_CHAMPION_DIFF_FUNCTION, return_value=ChampionDiffResult())

    compare_last_patch()

    assert mock_get_champion_data.call_args_list == [
        mocker.call("10.0.0"),
        mocker.call("9.9.9"),
    ]


def test_compare_last_patch_passes_fetched_data_to_diff(mocker):
    """Should pass fetched latest and previous champion data to diff service."""
    mocker.patch(GET_PATCHES_FUNCTION, return_value=("10.0.0", "9.9.9"))

    latest_data = {"Garen": ...}
    previous_data = {"Garen": ...}

    mocker.patch(
        GET_CHAMPION_DATA_FUNCTION,
        side_effect=[latest_data, previous_data]
    )

    mock_get_champion_diff = mocker.patch(
        GET_CHAMPION_DIFF_FUNCTION,
        return_value=ChampionDiffResult()
    )

    compare_last_patch()

    mock_get_champion_diff.assert_called_once_with(latest_data, previous_data)


def test_resolve_champion_matches_id_and_display_name():
    """Should resolve case-insensitive display name or ID to DataDragon ID, or None if unknown."""
    champions = {
        "MonkeyKing": ChampionEntry(id="MonkeyKing", name="Wukong"),
        "Yasuo": ChampionEntry(id="Yasuo", name="Yasuo"),
    }

    assert resolve_champion("wukong", champions) == "MonkeyKing"
    assert resolve_champion("MONKEYKING", champions) == "MonkeyKing"
    assert resolve_champion("yasuo", champions) == "Yasuo"
    assert resolve_champion("unknown_champ", champions) is None


def test_filter_diff_watch_and_ignore_precedence():
    """Should keep only watched champions and always exclude ignored champions."""
    diff = ChampionDiffResult(
        champion_changes={
            "Yasuo": {"hp": ChampionDiffStat(old=600, new=620)},
            "Garen": {"hp": ChampionDiffStat(old=700, new=750)},
        },
        new_champions=["Ambessa", "Yone"],
    )

    watched_only = filter_diff(diff, watched=["Yasuo", "Ambessa"], ignored=[])
    assert list(watched_only.champion_changes.keys()) == ["Yasuo"]
    assert watched_only.new_champions == ["Ambessa"]

    ignore_wins = filter_diff(diff, watched=["Yasuo", "Ambessa"], ignored=["Yasuo", "Ambessa"])
    assert ignore_wins.champion_changes == {}
    assert ignore_wins.new_champions == []


async def test_dispatch_patch_already_sent_skips_champion_fetch(mocker):
    """If latest patch was already sent, should not fetch champion data or enqueue DMs."""
    mocker.patch(GET_PATCHES_FUNCTION, return_value=("14.2.1", "14.1.1"))
    mocker.patch(IS_PATCH_SENT_FUNCTION, new=mocker.AsyncMock(return_value=True))
    mock_get_champion_data = mocker.patch(GET_CHAMPION_DATA_FUNCTION)

    sessionmaker, _ = _make_sessionmaker(mocker)
    queue = mocker.MagicMock()
    queue.enqueue = mocker.AsyncMock()
    queue.join = mocker.AsyncMock()

    await dispatch_patch(sessionmaker, queue)

    mock_get_champion_data.assert_not_called()
    queue.enqueue.assert_not_awaited()
    queue.join.assert_not_awaited()


async def test_dispatch_patch_sends_only_watched_champion_embed(mocker):
    """If user watches only Yasuo, should enqueue an embed containing only Yasuo changes."""
    mocker.patch(GET_PATCHES_FUNCTION, return_value=("14.2.1", "14.1.1"))
    mocker.patch(IS_PATCH_SENT_FUNCTION, new=mocker.AsyncMock(return_value=False))
    mocker.patch(
         "app.use_cases.compare_patches",
        return_value=ChampionDiffResult(
            champion_changes={
                "Yasuo": {"hp": ChampionDiffStat(old=600, new=630)},
                "Garen": {"hp": ChampionDiffStat(old=700, new=720)},
            }
        ),
    )
    mocker.patch(LIST_PENDING_USERS_FUNCTION, new=mocker.AsyncMock(return_value=[1001]))
    mocker.patch(
        GET_PREFERENCES_FUNCTION,
        new=mocker.AsyncMock(return_value=({"Yasuo"}, set())),
    )
    mocker.patch(MARK_PATCH_SENT_FUNCTION, new=mocker.AsyncMock())

    sessionmaker, _ = _make_sessionmaker(mocker)
    queue = mocker.MagicMock()
    queue.enqueue = mocker.AsyncMock()
    queue.join = mocker.AsyncMock()

    await dispatch_patch(sessionmaker, queue)

    queue.enqueue.assert_awaited_once()
    user_id, embeds = queue.enqueue.await_args.args
    assert user_id == 1001
    assert len(embeds) == 1
    assert [field.name for field in embeds[0].fields] == ["Yasuo"]


async def test_dispatch_patch_empty_filtered_result_marks_user_notified_without_dm(mocker):
    """If user's filtered diff is empty, should mark user notified immediately and skip DM."""
    mocker.patch(GET_PATCHES_FUNCTION, return_value=("14.2.1", "14.1.1"))
    mocker.patch(IS_PATCH_SENT_FUNCTION, new=mocker.AsyncMock(return_value=False))
    mocker.patch(
        "app.use_cases.compare_patches",
        return_value=ChampionDiffResult(
            champion_changes={"Garen": {"hp": ChampionDiffStat(old=700, new=720)}}
        ),
    )
    mocker.patch(LIST_PENDING_USERS_FUNCTION, new=mocker.AsyncMock(return_value=[2002]))
    mocker.patch(
        GET_PREFERENCES_FUNCTION,
        new=mocker.AsyncMock(return_value=({"Yasuo"}, set())),
    )
    mock_mark_notified = mocker.patch(MARK_USER_NOTIFIED_FUNCTION, new=mocker.AsyncMock())
    mocker.patch(MARK_PATCH_SENT_FUNCTION, new=mocker.AsyncMock())

    sessionmaker, session = _make_sessionmaker(mocker)
    queue = mocker.MagicMock()
    queue.enqueue = mocker.AsyncMock()
    queue.join = mocker.AsyncMock()

    await dispatch_patch(sessionmaker, queue)

    queue.enqueue.assert_not_awaited()
    mock_mark_notified.assert_awaited_once_with(session, 2002, "14.2.1")


async def test_dispatch_patch_marks_patch_sent_only_after_queue_join(mocker):
    """Should call mark_patch_sent only after queue.join() has completed."""
    mocker.patch(GET_PATCHES_FUNCTION, return_value=("14.2.1", "14.1.1"))
    mocker.patch(IS_PATCH_SENT_FUNCTION, new=mocker.AsyncMock(return_value=False))
    mocker.patch(
        "app.use_cases.compare_patches",
        return_value=ChampionDiffResult(
            champion_changes={"Yasuo": {"hp": ChampionDiffStat(old=600, new=630)}}
        ),
    )
    mocker.patch(LIST_PENDING_USERS_FUNCTION, new=mocker.AsyncMock(return_value=[3003]))
    mocker.patch(
        GET_PREFERENCES_FUNCTION,
        new=mocker.AsyncMock(return_value=(set(), set())),
    )

    events: list[str] = []

    async def fake_join():
        events.append("join")

    async def fake_mark_patch_sent(_session, _version):
        events.append("mark_patch_sent")

    mocker.patch(MARK_PATCH_SENT_FUNCTION, side_effect=fake_mark_patch_sent)

    sessionmaker, _ = _make_sessionmaker(mocker)
    queue = mocker.MagicMock()
    queue.enqueue = mocker.AsyncMock()
    queue.join = mocker.AsyncMock(side_effect=fake_join)

    await dispatch_patch(sessionmaker, queue)

    assert events == ["join", "mark_patch_sent"]
