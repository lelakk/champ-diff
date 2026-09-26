import responses

from services.ddragon_client import get_champion_data, get_all_versions, get_latest_and_previous_patch
from app.models import ChampionEntry

GET_VERSIONS_FUNCTION = "services.ddragon_client.get_all_versions"

#get_champion_data
@responses.activate
def test_get_champion_data_success():
    """If API returns 200 & valid JSON, should return champion data dict of models"""
    url = "https://ddragon.leagueoflegends.com/cdn/10.0.0/data/en_US/champion.json"
    responses.add(
        responses.GET,
        url,
        json={"data": {"Garen": {"id": "Garen"}}},
        status=200
    )
    result = get_champion_data("10.0.0")
    assert result == {"Garen": ChampionEntry(id="Garen")}


@responses.activate
def test_get_champion_data_failure():
    """If API returns 404, should return None"""
    url = "https://ddragon.leagueoflegends.com/cdn/10.0.0/data/en_US/champion.json"
    responses.add(
        responses.GET,
        url,
        status=404
    )
    result = get_champion_data("10.0.0")
    assert result is None


@responses.activate
def test_get_champion_data_invalid_json():
    """If API returns invalid JSON, should return None"""
    url = "https://ddragon.leagueoflegends.com/cdn/10.0.0/data/en_US/champion.json"
    responses.add(
        responses.GET,
        url,
        body="corrupted json",
        status=200
    )
    result = get_champion_data("10.0.0")
    assert result is None


@responses.activate
def test_get_champion_data_timeout():
    """If connection raises an error, should return None"""
    url = "https://ddragon.leagueoflegends.com/cdn/10.0.0/data/en_US/champion.json"
    responses.add(
        responses.GET,
        url,
        body=responses.ConnectionError("Connection timed out"),
    )
    result = get_champion_data("10.0.0")
    assert result is None


@responses.activate
def test_get_champion_data_empty_data():
    """If API returns empty JSON, should return None"""
    url = "https://ddragon.leagueoflegends.com/cdn/10.0.0/data/en_US/champion.json"
    responses.add(
        responses.GET,
        url,
        json={},
        status=200
    )
    result = get_champion_data("10.0.0")
    assert result is None


#get_all_versions
@responses.activate
def test_get_all_versions_success():
    """If versions API returns 200, should return versions list"""
    url = "https://ddragon.leagueoflegends.com/api/versions.json"
    responses.add(
        responses.GET,
        url,
        json=["10.0.0", "9.9.9"],
        status=200
    )
    result = get_all_versions()
    assert result == ["10.0.0", "9.9.9"]


@responses.activate
def test_get_all_versions_failure():
    """If versions API returns 500, should return None"""
    url = "https://ddragon.leagueoflegends.com/api/versions.json"
    responses.add(
        responses.GET,
        url,
        status=500
    )
    result = get_all_versions()
    assert result is None


#get_latest_and_previous_patch
def test_get_latest_and_previous_patch_success(mocker):
    """If versions API returns valid versions, should return tuple of latest and previous patch."""
    mocker.patch(GET_VERSIONS_FUNCTION, return_value=["10.0.0", "9.9.9"])

    result = get_latest_and_previous_patch()

    assert result == ("10.0.0", "9.9.9")


def test_get_latest_and_previous_patch_none_response(mocker):
    """If get_all_versions returns None, should return None."""
    mocker.patch(GET_VERSIONS_FUNCTION, return_value=None)

    result = get_latest_and_previous_patch()

    assert result is None


def test_get_latest_and_previous_patch_single_version(mocker):
    """If versions API returns only one version, should return None."""
    mocker.patch(GET_VERSIONS_FUNCTION, return_value=["10.0.0"])

    result = get_latest_and_previous_patch()

    assert result is None


def test_get_latest_and_previous_patch_invalid_type_versions(mocker):
    """If versions API returns invalid value types, should return None."""
    mocker.patch(GET_VERSIONS_FUNCTION, return_value=["10.0.0", 9.9, "9.9.9"])

    result = get_latest_and_previous_patch()

    assert result is None


def test_get_latest_and_previous_patch_custom_timeout(mocker):
    """Should pass custom timeout parameter to get_all_versions."""
    mock_get_all_versions = mocker.patch(GET_VERSIONS_FUNCTION, return_value=["10.0.0", "9.9.9"])

    get_latest_and_previous_patch(timeout=30)

    mock_get_all_versions.assert_called_once_with(30)