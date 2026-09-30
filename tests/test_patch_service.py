"""Unit tests for patch version selection logic."""

from services.patch_service import get_latest_and_previous_patch

GET_VERSIONS_FUNCTION = "services.patch_service.get_all_versions"


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
