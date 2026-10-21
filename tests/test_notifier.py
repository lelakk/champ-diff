"""Unit tests for Discord embed builder and rate-limited DM queue."""

import discord

from app.models import ChampionDiffResult, ChampionDiffStat
from services.notifier import DMQueue, build_embeds


def _make_http_exception(
    mocker, status: int, headers: dict[str, str] | None = None
) -> discord.HTTPException:
    """Creates a mocked Discord HTTPException with the given status and headers."""
    response = mocker.MagicMock()
    response.status = status
    response.reason = "Error"
    response.headers = headers or {}
    return discord.HTTPException(response, "HTTP error")


def _make_forbidden(mocker) -> discord.Forbidden:
    """Creates a mocked Discord Forbidden exception for blocked DMs."""
    response = mocker.MagicMock()
    response.status = 403
    response.reason = "Forbidden"
    return discord.Forbidden(
        response, {"code": 50007, "message": "Cannot send messages to this user"}
    )


def test_build_embeds_line_format_and_rounding():
    """Should format stat changes with arrows, round float deltas, and include new champions."""
    diff = ChampionDiffResult(
        champion_changes={
            "Yasuo": {
                "hp": ChampionDiffStat(old=630, new=650),
                "armor": ChampionDiffStat(old=40, new=35),
                "mpperlevel": ChampionDiffStat(old=32.1, new=32.4),
            }
        },
        new_champions=["Ambessa"],
    )

    embeds = build_embeds(diff, latest="14.2.1", previous="14.1.1")

    assert len(embeds) == 1
    embed = embeds[0]
    assert embed.footer.text == "Patch 14.1.1 → 14.2.1"
    assert len(embed.fields) == 2

    yasuo_field = embed.fields[0]
    assert yasuo_field.name == "Yasuo"
    assert yasuo_field.value == (
        "hp: 630 → 650 (▲ +20)\n"
        "armor: 40 → 35 (▼ -5)\n"
        "mpperlevel: 32.1 → 32.4 (▲ +0.3)"
    )

    new_champs_field = embed.fields[1]
    assert new_champs_field.name == "New champions"
    assert new_champs_field.value == "Ambessa"


def test_build_embeds_empty_diff_returns_empty_list():
    """If diff has no changes and no new champions, should return an empty list."""
    diff = ChampionDiffResult()

    assert build_embeds(diff, latest="14.2.1", previous="14.1.1") == []


def test_build_embeds_splits_60_champions_within_discord_limits():
    """Should split 60 champions across multiple embeds while respecting all Discord limits."""
    champion_changes = {
        f"Champ{i:02d}": {
            "hp": ChampionDiffStat(old=600, new=620),
            "ad": ChampionDiffStat(old=60, new=65),
        }
        for i in range(60)
    }
    diff = ChampionDiffResult(champion_changes=champion_changes)

    embeds = build_embeds(diff, latest="14.2.1", previous="14.1.1")

    assert len(embeds) == 3
    assert len(embeds) <= 10
    assert sum(len(embed) for embed in embeds) <= 6000
    assert sum(len(embed.fields) for embed in embeds) == 60

    for embed in embeds:
        assert len(embed.fields) <= 25
        assert embed.footer.text == "Patch 14.1.1 → 14.2.1"
        for field in embed.fields:
            assert len(field.value) <= 1024


async def test_dm_queue_sleeps_between_three_messages(mocker):
    """Should call sleep with configured delay between consecutive messages."""
    sleep_mock = mocker.AsyncMock()
    on_success = mocker.AsyncMock()
    queue = DMQueue(delay=1.0, on_success=on_success, sleep=sleep_mock)
    embeds = [discord.Embed(title="Diff")]

    users = [mocker.MagicMock(id=i, send=mocker.AsyncMock()) for i in (1, 2, 3)]
    for user in users:
        await queue.enqueue(user, embeds)

    await queue.join()

    for user in users:
        user.send.assert_awaited_once_with(embeds=embeds)
    assert sleep_mock.await_args_list == [mocker.call(1.0), mocker.call(1.0)]
    assert on_success.await_args_list == [mocker.call(1), mocker.call(2), mocker.call(3)]


async def test_dm_queue_handles_rate_limited_and_retries(mocker):
    """If RateLimited is raised, should sleep for retry_after and retry sending."""
    sleep_mock = mocker.AsyncMock()
    on_success = mocker.AsyncMock()
    queue = DMQueue(delay=1.0, on_success=on_success, sleep=sleep_mock)
    embeds = [discord.Embed(title="Diff")]

    user = mocker.MagicMock(id=101)
    user.send = mocker.AsyncMock(side_effect=[discord.RateLimited(7.5), None])

    await queue.enqueue(user, embeds)
    await queue.join()

    assert user.send.await_count == 2
    sleep_mock.assert_awaited_once_with(7.5)
    on_success.assert_awaited_once_with(101)


async def test_dm_queue_handles_http_429_retry_after_header(mocker):
    """If HTTP 429 is raised, should sleep for Retry-After header duration and retry."""
    sleep_mock = mocker.AsyncMock()
    on_success = mocker.AsyncMock()
    queue = DMQueue(delay=1.0, on_success=on_success, sleep=sleep_mock)
    embeds = [discord.Embed(title="Diff")]

    exc_429 = _make_http_exception(mocker, 429, headers={"Retry-After": "3"})
    user = mocker.MagicMock(id=102)
    user.send = mocker.AsyncMock(side_effect=[exc_429, None])

    await queue.enqueue(user, embeds)
    await queue.join()

    assert user.send.await_count == 2
    sleep_mock.assert_awaited_once_with(3)
    on_success.assert_awaited_once_with(102)


async def test_dm_queue_forbidden_calls_callback_and_continues(mocker):
    """If Forbidden is raised, should call on_forbidden and continue processing the queue."""
    sleep_mock = mocker.AsyncMock()
    on_success = mocker.AsyncMock()
    on_forbidden = mocker.AsyncMock()
    queue = DMQueue(
        delay=1.0,
        on_success=on_success,
        on_forbidden=on_forbidden,
        sleep=sleep_mock,
    )
    embeds = [discord.Embed(title="Diff")]

    blocked_user = mocker.MagicMock(id=201)
    blocked_user.send = mocker.AsyncMock(side_effect=_make_forbidden(mocker))
    active_user = mocker.MagicMock(id=202)
    active_user.send = mocker.AsyncMock(return_value=None)

    await queue.enqueue(blocked_user, embeds)
    await queue.enqueue(active_user, embeds)
    await queue.join()

    blocked_user.send.assert_awaited_once_with(embeds=embeds)
    active_user.send.assert_awaited_once_with(embeds=embeds)
    on_forbidden.assert_awaited_once_with(201)
    on_success.assert_awaited_once_with(202)


async def test_dm_queue_drops_message_after_three_5xx_errors(mocker):
    """If three 5xx errors occur, should drop the message without calling on_success."""
    sleep_mock = mocker.AsyncMock()
    on_success = mocker.AsyncMock()
    queue = DMQueue(delay=1.0, on_success=on_success, sleep=sleep_mock)
    embeds = [discord.Embed(title="Diff")]

    exc_503 = _make_http_exception(mocker, 503)
    user = mocker.MagicMock(id=301)
    user.send = mocker.AsyncMock(side_effect=[exc_503, exc_503, exc_503])

    await queue.enqueue(user, embeds)
    await queue.join()

    assert user.send.await_count == 3
    on_success.assert_not_awaited()
