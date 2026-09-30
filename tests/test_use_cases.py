"""Unit tests for end-to-end patch comparison use cases."""

from unittest.mock import call
import pytest

from app.use_cases import compare_last_patch
from app.models import ChampionDiffResult, ChampionDiffStat

GET_PATCHES_FUNCTION = "app.use_cases.get_latest_and_previous_patch"
GET_CHAMPION_DATA_FUNCTION = "app.use_cases.get_champion_data"
GET_CHAMPION_DIFF_FUNCTION = "app.use_cases.get_champion_diff"


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

    assert mock_get_champion_data.call_args_list == [call("10.0.0"), call("9.9.9")]


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
