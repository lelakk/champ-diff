import logging
import requests

from typing import Any
from pydantic import ValidationError
from app.models import ChampionPayload, ChampionEntry

logger = logging.getLogger(__name__)
BASE_DDRAGON_URL = "https://ddragon.leagueoflegends.com"


def _fetch_json(url: str, timeout: int = 10) -> dict[str, Any] | None:
    """Fetches and parses JSON data from a given URL.

        Args:
            url: The URL to fetch the JSON data from.
            timeout: Timeout for the HTTP request in seconds.

        Returns:
            Parsed JSON data or None if the request fails
            or the response contains invalid JSON.
        """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as error_message:
        logger.error(f"Request failed for {url}: {error_message}")
        return None
    try:
        return response.json()
    except ValueError as error_message:
        logger.error(f"Failed to parse JSON from {url}: {error_message}")
        return None


def get_champion_data(
    patch_version: str, language: str = "en_US", timeout: int = 10
) -> dict[str, ChampionEntry] | None:
    """Fetches patch data from DataDragon for a specific patch version.

    Args:
        patch_version: Version of the patch.
        language: Language code for the champion data.
        timeout: Timeout for the HTTP request in seconds.

    Returns:
        Dictionary containing the champion data, or None if failed.
    """
    url = f"{BASE_DDRAGON_URL}/cdn/{patch_version}/data/{language}/champion.json"
    logger.info("Downloading champion data for patch %s ...", patch_version)

    data = _fetch_json(url, timeout)
    if not isinstance(data, dict):
        return None

    try:
        champ_payload = ChampionPayload.model_validate(data)
    except ValidationError as error_message:
        logger.error(f"Invalid champion payload format for patch {patch_version}: {error_message}")
        return None

    if not champ_payload.data:
        return None

    return champ_payload.data


def get_all_versions(timeout: int = 10) -> list[str] | None:
    """Fetches all available versions from DataDragon.

    Args:
        timeout: Timeout for the HTTP request in seconds.

    Returns:
        List of all version strings, or None if the request failed.
    """
    url = f"{BASE_DDRAGON_URL}/api/versions.json"
    data = _fetch_json(url, timeout)
    if isinstance(data, list):
        return data
    return None


def get_latest_and_previous_patch(timeout: int = 10) -> tuple[str, str] | None:
    """Fetches the latest and previous version patch from the available versions.

    Args:
        timeout: Timeout for the HTTP request in seconds.

    Returns:
        A tuple containing the latest and previous patch version strings, or None if unavailable.
    """
    versions = get_all_versions(timeout)
    if not versions:
        logger.error("No versions returned from DataDragon")
        return None
    if not isinstance(versions, list) or len(versions) < 2:
        logger.error("Invalid versions response, expected at least 2 versions")
        return None
    if not all(isinstance(ver, str) for ver in versions):
        logger.error("Invalid version format, expected strings")
        return None
    return versions[0], versions[1]
